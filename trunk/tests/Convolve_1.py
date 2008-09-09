"""Test lsst.afwMath.convolve

The convolve function is overloaded in two flavors:
- in-place convolve: user supplies the output image as an argument
- new-image convolve: the convolve function returns the convolved image

All tests use the new-image version unless otherwise noted.
"""
import os
import math
import pdb                          # we may want to say pdb.set_trace()
import sys
import unittest

import numpy

import eups
import lsst.utils.tests as utilsTest
import lsst.pex.logging as pexLog
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.afw.image.testUtils as imTestUtils

Verbosity = 0 # increase to see trace
pexLog.Trace_setVerbosity("lsst.afw", Verbosity)

dataDir = eups.productDir("afwdata")
if not dataDir:
    raise RuntimeError("Must set up afwdata to run these tests")
InputMaskedImagePath = os.path.join(dataDir, "871034p_1_MI")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def refConvolve(imVarMask, kernel, edgeBit, doNormalize, ignoreKernelZeroPixels=True):
    """Reference code to convolve a kernel with masked image data.
    
    Does NOT normalize the kernel.

    Warning: slow (especially for spatially varying kernels).
    
    Inputs:
    - imVarMask: (image, variance, mask) numpy arrays
    - kernel: lsst::afw::Core.Kernel object
    - edgeBit: this bit is set in the output mask for border pixels; no bit set if < 0
    - doNormalize: normalize the kernel
    
    Border pixels (pixels too close to the edge to compute) are copied from the input,
    and if edgeBit >= 0 then border mask pixels have the edgeBit bit set
    """
    image, variance, mask = imVarMask
    
    # copy input data, handling the outer border and edge bit
    retImage = image.copy()
    retVariance = variance.copy()
    retMask = mask.copy()
    if (edgeBit >= 0):
         retMask |= 2 ** edgeBit
    
    kCols = kernel.getCols()
    kRows = kernel.getRows()
    numCols = image.shape[0] + 1 - kCols
    numRows = image.shape[1] + 1 - kRows
    if numCols < 0 or numRows < 0:
        raise RuntimeError("image must be larger than kernel in both dimensions")
    colRange = range(numCols)

    isSpatiallyVarying = kernel.isSpatiallyVarying()
    if not isSpatiallyVarying:
        kImArr = imTestUtils.arrayFromImage(kernel.computeNewImage(doNormalize)[0])
    else:
        kImage = afwImage.ImageD(kCols, kRows)

    retRow = kernel.getCtrRow()
    for inRowBeg in range(numRows):
        inRowEnd = inRowBeg + kRows
        retCol = kernel.getCtrCol()
        if isSpatiallyVarying:
            rowPos = afwImage.indexToPosition(retRow)
        for inColBeg in colRange:
            if isSpatiallyVarying:
                colPos = afwImage.indexToPosition(retCol)
                kernel.computeImage(kImage, doNormalize, colPos, rowPos)
                kImArr = imTestUtils.arrayFromImage(kImage)
            inColEnd = inColBeg + kCols
            subImage = image[inColBeg:inColEnd, inRowBeg:inRowEnd]
            subVariance = variance[inColBeg:inColEnd, inRowBeg:inRowEnd]
            subMask = mask[inColBeg:inColEnd, inRowBeg:inRowEnd]
            retImage[retCol, retRow] = numpy.add.reduce((kImArr * subImage).flat)
            retVariance[retCol, retRow] = numpy.add.reduce((kImArr * kImArr * subVariance).flat)
            if ignoreKernelZeroPixels:
                retMask[retCol, retRow] = numpy.bitwise_or.reduce((subMask * (kImArr != 0)).flat)
            else:
                retMask[retCol, retRow] = numpy.bitwise_or.reduce(subMask.flat)
            

            retCol += 1
        retRow += 1
    return (retImage, retVariance, retMask)

def makeGaussianKernelVec(kCols, kRows):
    """Create a afwImage.VectorKernel of gaussian kernels.

    This is useful for constructing a LinearCombinationKernel.
    """
    xySigmaList = [
        (1.5, 1.5),
        (1.5, 2.5),
        (2.5, 1.5),
    ]
    kVec = afwMath.KernelListD()
    for xSigma, ySigma in xySigmaList:
        kFunc = afwMath.GaussianFunction2D(1.5, 2.5)
        basisKernelPtr = afwMath.KernelPtr(afwMath.AnalyticKernel(kFunc, kCols, kRows))
        kVec.append(basisKernelPtr)
    return kVec

def sameMaskPlaneDicts(maskedImageA, maskedImageB):
    """Return True if the mask plane dicts are the same, False otherwise.

    Handles the fact that one cannot directly compare maskPlaneDicts using ==
    """
    mpDictA = maskedImageA.getMask().getMaskPlaneDict()
    mpDictB = maskedImageB.getMask().getMaskPlaneDict()
    if mpDictA.keys() != mpDictB.keys():
        print "mpDictA.keys()  ", mpDictA.keys()
        print "mpDictB.keys()  ", mpDictB.keys()
        return False
    if mpDictA.values() != mpDictB.values():
        print "mpDictA.values()", mpDictA.values()
        print "mpDictB.values()", mpDictB.values()
        return False
    return True

class ConvolveTestCase(unittest.TestCase):
    def testUnityConvolution(self):
        """Verify that convolution with a centered delta function reproduces the original.

        Note: the test for masks is disabled because at present afwMath.convolve
        smears the mask. If that is changed in convolution then re-enable the mask test.
        """
        imCols = 45
        imRows = 55
        edgeBit = -1
        
        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        # create a delta function kernel that has 1,1 in the center
        kFunc = afwMath.IntegerDeltaFunction2D(0.0, 0.0)
        k = afwMath.AnalyticKernel(kFunc, 3, 3)
        
        cnvMaskedImage = afwMath.convolve(maskedImage, k, edgeBit, True)
    
        origImVarMaskArrays = imTestUtils.arraysFromMaskedImage(maskedImage)
        cnvImVarMaskArrays = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
        for name, ind in (("image", 0), ("variance", 1)): # , ("mask", 2)):
            if not numpy.allclose(origImVarMaskArrays[ind], cnvImVarMaskArrays[ind]):
                self.fail("Convolved %s does not match reference" % (name,))

    def testSpatiallyInvariantInPlaceConvolve(self):
        """Test in-place version of convolve with a spatially invariant Gaussian function
        """
        kCols = 6
        kRows = 7
        imCols = 45
        imRows = 55
        edgeBit = 7
        doNormalize = False

        kFunc =  afwMath.GaussianFunction2D(1.5, 2.5)
        k = afwMath.AnalyticKernel(kFunc, kCols, kRows)
        
        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        cnvMaskedImage = afwImage.MaskedImageF(imCols, imRows)
        for doNormalize in (False, True):
            afwMath.convolve(cnvMaskedImage, maskedImage, k, edgeBit, doNormalize)
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)

            imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
            refCnvImage, refCnvVariance, refCnvMask = \
                refConvolve(imVarMask, k, edgeBit, doNormalize)
    
            if not numpy.allclose(cnvImage, refCnvImage):
                self.fail("Convolved image does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvVariance, refCnvVariance):
                self.fail("Convolved variance does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvMask, refCnvMask):
                self.fail("Convolved mask does not match reference for doNormalize=%s" % doNormalize)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)
                
    
    def testSpatiallyInvariantConvolve(self):
        """Test convolution with a spatially invariant Gaussian function
        """
        kCols = 7
        kRows = 6
        imCols = 55
        imRows = 45
        edgeBit = 7

        kFunc =  afwMath.GaussianFunction2D(1.5, 2.5)
        k = afwMath.AnalyticKernel(kFunc, kCols, kRows)
        
        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        for doNormalize in (False, True):
            cnvMaskedImage = afwMath.convolve(maskedImage, k, edgeBit, doNormalize)
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
    
            imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
            refCnvImage, refCnvVariance, refCnvMask = \
                refConvolve(imVarMask, k, edgeBit, doNormalize)
    
            if not numpy.allclose(cnvImage, refCnvImage):
                self.fail("Convolved image does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvVariance, refCnvVariance):
                self.fail("Convolved variance does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvMask, refCnvMask):
                self.fail("Convolved mask does not match reference for doNormalize=%s" % doNormalize)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)

    def testSpatiallyVaryingInPlaceConvolve(self):
        """Test in-place convolution with a spatially varying Gaussian function
        """
        kCols = 7
        kRows = 6
        imCols = 55
        imRows = 45
        edgeBit = 7

        # create spatially varying linear combination kernel
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, 1.0 / imCols, 0.0),
            (1.0, 0.0,  1.0 / imRows),
        )
   
        kFunc =  afwMath.GaussianFunction2D(1.0, 1.0)
        k = afwMath.AnalyticKernel(kFunc, kCols, kRows, sFunc)
        k.setSpatialParameters(sParams)
        
        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        cnvMaskedImage = afwImage.MaskedImageF(imCols, imRows)
        for doNormalize in (False, True):
            afwMath.convolve(cnvMaskedImage, maskedImage, k, edgeBit, doNormalize)
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
    
            imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
            refCnvImage, refCnvVariance, refCnvMask = \
                refConvolve(imVarMask, k, edgeBit, doNormalize)
    
            if not numpy.allclose(cnvImage, refCnvImage):
                self.fail("Convolved image does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvVariance, refCnvVariance):
                self.fail("Convolved variance does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvMask, refCnvMask):
                self.fail("Convolved mask does not match reference for doNormalize=%s" % doNormalize)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)

    def testSpatiallyVaryingSeparableInPlaceConvolve(self):
        """Test in-place separable convolution with a spatially varying Gaussian function
        """
        sys.stderr.write("Test convolution with SeparableKernel\n")
        kCols = 7
        kRows = 6
        imCols = 55
        imRows = 45
        edgeBit = 7

        # create spatially varying linear combination kernel
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, 1.0 / imCols, 0.0),
            (1.0, 0.0,  1.0 / imRows),
        )

        gaussFunc1 = afwMath.GaussianFunction1D(1.0)
        gaussFunc2 = afwMath.GaussianFunction2D(1.0, 1.0)
        separableKernel = afwMath.SeparableKernel(gaussFunc1, gaussFunc1, kCols, kRows, sFunc)
        analyticKernel = afwMath.AnalyticKernel(gaussFunc2, kCols, kRows, sFunc)
        separableKernel.setSpatialParameters(sParams)
        analyticKernel.setSpatialParameters(sParams)
        
        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        isFirst = True
        cnvMaskedImage = afwImage.MaskedImageF(imCols, imRows)
        for doNormalize in (False, True):
            if isFirst and Verbosity < 3:
                pexLog.Trace_setVerbosity("lsst.afw", 3)
            afwMath.convolve(cnvMaskedImage, maskedImage, separableKernel, edgeBit, doNormalize)
            if isFirst:
                pexLog.Trace_setVerbosity("lsst.afw", Verbosity)
                isFirst = False
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
    
            imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
            refCnvImage, refCnvVariance, refCnvMask = \
                refConvolve(imVarMask, analyticKernel, edgeBit, doNormalize)
    
            if not numpy.allclose(cnvImage, refCnvImage):
                self.fail("Convolved image does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvVariance, refCnvVariance):
                self.fail("Convolved variance does not match reference for doNormalize=%s" % doNormalize)
            if not numpy.allclose(cnvMask, refCnvMask):
                self.fail("Convolved mask does not match reference for doNormalize=%s" % doNormalize)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)
    
    def testDeltaConvolve(self):
        """Test convolution with various delta function kernels using optimized code
        """
        sys.stderr.write("Test convolution with DeltaFunctionKernel\n")
        edgeBit = 7
        imCols = 20
        imRows = 12
        doNormalize = True

        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)
        
        isFirst = True
        for kCols in range(1, 4):
            for kRows in range(1, 4):
                for activeCol in range(kCols):
                    for activeRow in range(kRows):
                        kernel = afwMath.DeltaFunctionKernel(activeCol, activeRow, kCols, kRows)
                        
                        if isFirst and Verbosity < 3:
                            pexLog.Trace_setVerbosity("lsst.afw", 3)
                        refCnvMaskedImage = afwMath.convolve(maskedImage, kernel, edgeBit, doNormalize)
                        if isFirst:
                            pexLog.Trace_setVerbosity("lsst.afw", Verbosity)
                            isFirst = False
                        refCnvImage, refCnvVariance, refCnvMask = \
                            imTestUtils.arraysFromMaskedImage(refCnvMaskedImage)
                
                        imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
                        ref2CnvImage, ref2CnvVariance, ref2CnvMask = \
                           refConvolve(imVarMask, kernel, edgeBit, doNormalize, True)
                
                        if not numpy.allclose(refCnvImage, ref2CnvImage):
                            self.fail("Image from afwMath.convolve does not match image from refConvolve")
                        if not numpy.allclose(refCnvVariance, ref2CnvVariance):
                            self.fail("Variance from afwMath.convolve does not match image from refConvolve")
                        if not numpy.allclose(refCnvMask, ref2CnvMask):
                            self.fail("Mask from afwMath.convolve does not match image from refCconvolve")
        

    def testConvolveLinear(self):
        """Test convolution with a spatially varying LinearCombinationKernel
        by comparing the results of convolveLinear to afwMath.convolve or refConvolve,
        depending on the value of compareToFwConvolve.
        """
        kCols = 5
        kRows = 5
        edgeBit = 7
        imCols = 50
        imRows = 55
        doNormalize = False # must be false because convolveLinear cannot normalize

        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)

        # create spatially varying linear combination kernel
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, -0.5 / imCols, -0.5 / imRows),
            (0.0,  1.0 / imCols,  0.0 / imRows),
            (0.0,  0.0 / imCols,  1.0 / imRows),
        )
        
        kVec = makeGaussianKernelVec(kCols, kRows)
        lcKernel = afwMath.LinearCombinationKernel(kVec, sFunc)
        lcKernel.setSpatialParameters(sParams)

        refCnvMaskedImage = afwMath.convolve(maskedImage, lcKernel, edgeBit, doNormalize)
        refCnvImage, refCnvVariance, refCnvMask = \
            imTestUtils.arraysFromMaskedImage(refCnvMaskedImage)

        imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
        ref2CnvImage, ref2CnvVariance, ref2CnvMask = \
           refConvolve(imVarMask, lcKernel, edgeBit, doNormalize)

        if not numpy.allclose(refCnvImage, ref2CnvImage):
            self.fail("Image from afwMath.convolve does not match image from refConvolve")
        if not numpy.allclose(refCnvVariance, ref2CnvVariance):
            self.fail("Variance from afwMath.convolve does not match image from refConvolve")
        if not numpy.allclose(refCnvMask, ref2CnvMask):
            self.fail("Mask from afwMath.convolve does not match image from refCconvolve")

        # compute twice, to be sure cnvMaskedImage is properly reset
        cnvMaskedImage = afwImage.MaskedImageF(imCols, imRows)
        for ii in range(2):        
            afwMath.convolveLinear(cnvMaskedImage, maskedImage, lcKernel, edgeBit)
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
    
            if not numpy.allclose(cnvImage, ref2CnvImage):
                self.fail("Image from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            if not numpy.allclose(cnvVariance, ref2CnvVariance):
                self.fail("Variance from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            if not numpy.allclose(cnvMask, ref2CnvMask):
                self.fail("Mask from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)

    def testConvolveLinearNewImage(self):
        """Test variant of convolveLinear that returns a new image
        """
        kCols = 5
        kRows = 5
        edgeBit = 7
        imCols = 50
        imRows = 55
        doNormalize = False # must be false because convolveLinear cannot normalize

        fullMaskedImage = afwImage.MaskedImageF()
        fullMaskedImage.readFits(InputMaskedImagePath)
        
        # pick a small piece of the image to save time
        bbox = afwImage.BBox2i(50, 50, imCols, imRows)
        subMaskedImagePtr = fullMaskedImage.getSubImage(bbox)
        maskedImage = subMaskedImagePtr.get()
        maskedImage.this.disown()
        maskedImage.getMask().setMaskPlaneValues(0, 5, 7, 5)

        # create spatially varying linear combination kernel
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, -0.5 / imCols, -0.5 / imRows),
            (0.0,  1.0 / imCols,  0.0 / imRows),
            (0.0,  0.0 / imCols,  1.0 / imRows),
        )
        
        kVec = makeGaussianKernelVec(kCols, kRows)
        lcKernel = afwMath.LinearCombinationKernel(kVec, sFunc)
        lcKernel.setSpatialParameters(sParams)

        refCnvMaskedImage = afwMath.convolve(maskedImage, lcKernel, edgeBit, doNormalize)
        refCnvImage, refCnvVariance, refCnvMask = \
            imTestUtils.arraysFromMaskedImage(refCnvMaskedImage)

        imVarMask = imTestUtils.arraysFromMaskedImage(maskedImage)
        ref2CnvImage, ref2CnvVariance, ref2CnvMask = \
           refConvolve(imVarMask, lcKernel, edgeBit, doNormalize)

        if not numpy.allclose(refCnvImage, ref2CnvImage):
            self.fail("Image from afwMath.convolve does not match image from refConvolve")
        if not numpy.allclose(refCnvVariance, ref2CnvVariance):
            self.fail("Variance from afwMath.convolve does not match image from refConvolve")
        if not numpy.allclose(refCnvMask, ref2CnvMask):
            self.fail("Mask from afwMath.convolve does not match image from refCconvolve")

        # compute twice, to be sure cnvMaskedImage is properly reset
        for ii in range(2):        
            cnvMaskedImage = afwMath.convolveLinear(maskedImage, lcKernel, edgeBit)
            cnvImage, cnvVariance, cnvMask = imTestUtils.arraysFromMaskedImage(cnvMaskedImage)
    
            if not numpy.allclose(cnvImage, ref2CnvImage):
                self.fail("Image from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            if not numpy.allclose(cnvVariance, ref2CnvVariance):
                self.fail("Variance from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            if not numpy.allclose(cnvMask, ref2CnvMask):
                self.fail("Mask from afwMath.convolveLinear does not match image from refConvolve in iter %d" % ii)
            self.assert_(sameMaskPlaneDicts(cnvMaskedImage, maskedImage),
                "Convolved mask dictionary does not match input for doNormalize=%s" % doNormalize)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""
    utilsTest.init()

    suites = []
    suites += unittest.makeSuite(ConvolveTestCase)
    suites += unittest.makeSuite(utilsTest.MemoryTestCase)

    return unittest.TestSuite(suites)

def run(exit=False):
    """Run the tests"""
    utilsTest.run(suite(), exit)

if __name__ == "__main__":
    run(True)