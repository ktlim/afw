#!/usr/bin/env python

# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

"""Test lsst.afwMath.convolve

Tests convolution of various kernels with Images and MaskedImages.
"""
import math
import os
import unittest

import numpy

import eups
import lsst.utils.tests as utilsTests
import lsst.pex.logging as pexLog
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.afw.image.testUtils as imTestUtils

VERBOSITY = 0   # increase to see trace; 3 will show the convolutions specializations being used

pexLog.Debug("lsst.afw", VERBOSITY)

try:
    display
except NameError:
    display = False

import lsst.afw.display.ds9 as ds9
import lsst.afw.display.utils as displayUtils

dataDir = eups.productDir("afwdata")
if not dataDir:
    raise RuntimeError("Must set up afwdata to run these tests")

# input image contains a saturated star, a bad column, and a faint star
InputMaskedImagePath = os.path.join(dataDir, "med")
InputBBox = afwImage.BBox(afwImage.PointI(52, 574), 76, 80)
# the shifted BBox is for a same-sized region containing different pixels;
# this is used to initialize the convolved image, to make sure convolve fully overwrites it
ShiftedBBox = afwImage.BBox(afwImage.PointI(0, 460), 76, 80)
FullMaskedImage = afwImage.MaskedImageF(InputMaskedImagePath)

EdgeMaskPixel = 1 << afwImage.MaskU.getMaskPlane("EDGE")

# Ignore kernel pixels whose value is exactly 0 when smearing the mask plane?
# Set this to match the afw code
IgnoreKernelZeroPixels = True

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def refConvolve(imMaskVar, xy0, kernel, doNormalize, doCopyEdge):
    """Reference code to convolve a kernel with a masked image.

    Warning: slow (especially for spatially varying kernels).
    
    Inputs:
    - imMaskVar: (image, mask, variance) numpy arrays
    - xy0: xy offset of imMaskVar relative to parent image
    - kernel: lsst::afw::Core.Kernel object
    - doNormalize: normalize the kernel
    - doCopyEdge: if True: copy edge pixels from input image to convolved image;
                if False: set edge pixels to the standard edge pixel (image=nan, var=inf, mask=EDGE)
    """
    image, mask, variance = imMaskVar
    
    if doCopyEdge:
        # copy input arrays to output arrays and set EDGE bit of mask; non-edge pixels are overwritten below
        retImage = imMaskVar[0].copy()
        retMask = imMaskVar[1].copy()
        retMask += EdgeMaskPixel
        retVariance = imMaskVar[2].copy()
    else:
        # initialize output arrays to all edge pixels; non-edge pixels will be overwritten below
        retImage = numpy.zeros(image.shape, dtype=image.dtype)
        retImage[:, :] = numpy.nan
        retMask = numpy.zeros(mask.shape, dtype=mask.dtype)
        retMask[:, :] = EdgeMaskPixel
        retVariance = numpy.zeros(variance.shape, dtype=image.dtype)
        retVariance[:, :] = numpy.inf
    
    kCols = kernel.getWidth()
    kRows = kernel.getHeight()
    numCols = image.shape[0] + 1 - kCols
    numRows = image.shape[1] + 1 - kRows
    if numCols < 0 or numRows < 0:
        raise RuntimeError("image must be larger than kernel in both dimensions")
    colRange = range(numCols)


    kImage = afwImage.ImageD(kCols, kRows)
    isSpatiallyVarying = kernel.isSpatiallyVarying()
    if not isSpatiallyVarying:
        kernel.computeImage(kImage, doNormalize)
        kImArr = imTestUtils.arrayFromImage(kImage)

    retRow = kernel.getCtrY()
    for inRowBeg in range(numRows):
        inRowEnd = inRowBeg + kRows
        retCol = kernel.getCtrX()
        if isSpatiallyVarying:
            rowPos = afwImage.indexToPosition(retRow) + xy0[1]
        for inColBeg in colRange:
            if isSpatiallyVarying:
                colPos = afwImage.indexToPosition(retCol) + xy0[0]
                kernel.computeImage(kImage, doNormalize, colPos, rowPos)
                kImArr = imTestUtils.arrayFromImage(kImage)
            inColEnd = inColBeg + kCols
            subImage = image[inColBeg:inColEnd, inRowBeg:inRowEnd]
            subVariance = variance[inColBeg:inColEnd, inRowBeg:inRowEnd]
            subMask = mask[inColBeg:inColEnd, inRowBeg:inRowEnd]
            retImage[retCol, retRow] = numpy.add.reduce((kImArr * subImage).flat)
            retVariance[retCol, retRow] = numpy.add.reduce((kImArr * kImArr * subVariance).flat)
            if IgnoreKernelZeroPixels:
                retMask[retCol, retRow] = numpy.bitwise_or.reduce((subMask * (kImArr != 0)).flat)
            else:
                retMask[retCol, retRow] = numpy.bitwise_or.reduce(subMask.flat)
            

            retCol += 1
        retRow += 1
    return (retImage, retMask, retVariance)

def makeGaussianKernelVec(kCols, kRows):
    """Create a list of gaussian kernels.

    This is useful for constructing a LinearCombinationKernel.
    """
    gaussParamsList = [
        (1.5, 1.5, 0.0),
        (2.5, 1.5, 0.0),
        (2.5, 1.5, math.pi / 2.0),
    ]
    kVec = afwMath.KernelList()
    for majorSigma, minorSigma, angle in gaussParamsList:
        kFunc = afwMath.GaussianFunction2D(majorSigma, minorSigma, angle)
        kVec.append(afwMath.AnalyticKernel(kCols, kRows, kFunc))
    return kVec

def makeDeltaFunctionKernelVec(kCols, kRows):
    """Create a list of delta function kernels
    """
    kVec = afwMath.KernelList()
    for activeCol in range(kCols):
        for activeRow in range(kRows):
            kVec.append(afwMath.DeltaFunctionKernel(kCols, kRows, afwImage.PointI(activeCol, activeRow)))
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
    def setUp(self):
        tmp = afwImage.MaskU()          # clearMaskPlaneDict isn't static
        tmp.clearMaskPlaneDict()        # reset so tests will be deterministic

        for p in ("BAD", "SAT", "INTRP", "CR", "EDGE"):
            afwImage.MaskU_addMaskPlane(p)
            
        del tmp
        
        self.maskedImage = afwImage.MaskedImageF(FullMaskedImage, InputBBox, True)
        # use a huge XY0 to make emphasize any errors related to not handling xy0 correctly.
        self.maskedImage.setXY0(300, 200)
        self.xy0 = self.maskedImage.getXY0()

        # provide destinations for the convolved MaskedImage and Image that contain junk
        # to verify that convolve overwrites all pixels;
        # make them deep copies so we can mess with them without affecting self.inImage
        self.cnvMaskedImage = afwImage.MaskedImageF(FullMaskedImage, ShiftedBBox, True)
        self.cnvImage = afwImage.ImageF(FullMaskedImage.getImage(), ShiftedBBox, True)

        self.width = self.maskedImage.getWidth()
        self.height = self.maskedImage.getHeight()
#         smask = afwImage.MaskU(self.maskedImage.getMask(), afwImage.BBox(afwImage.PointI(15, 17), 10, 5))
#         smask.set(0x8)

    def tearDown(self):
        del self.maskedImage
        del self.cnvMaskedImage
        del self.cnvImage

    def runBasicTest(self, kernel, convControl, refKernel=None, kernelDescr="", rtol=1.0e-05, atol=1e-08): 
        """Assert that afwMath::convolve gives the same result as reference convolution for a given kernel.
        
        Inputs:
        - kernel: convolution kernel
        - convControl: convolution control parameters (afwMath.ConvolutionControl)
        - refKernel: kernel to use for refConvolve (if None then kernel is used)
        - kernelDescr: description of kernel
        - rtol: relative tolerance (see below)
        - atol: absolute tolerance (see below)
        - maxInterpErr: maximum allowed interpolation error
        
        rtol and atol are positive, typically very small numbers.
        The relative difference (rtol * abs(b)) and the absolute difference "atol" are added together
        to compare against the absolute difference between "a" and "b".
        """
        if refKernel == None:
            refKernel = kernel
        shortKernelDescr = kernelDescr.replace(" ", "")

        doNormalize = convControl.getDoNormalize()
        doCopyEdge = convControl.getDoCopyEdge()
        maxInterpErr = convControl.getMaxInterpolationError()

        imMaskVar = imTestUtils.arraysFromMaskedImage(self.maskedImage)
        xy0 = self.maskedImage.getXY0()
        
        refCnvImMaskVarArr = refConvolve(imMaskVar, xy0, refKernel, doNormalize, doCopyEdge)

        afwMath.convolve(self.cnvImage, self.maskedImage.getImage(), kernel, convControl)
        self.assertEqual(self.cnvImage.getXY0(), self.xy0)
        cnvImArr = imTestUtils.arrayFromImage(self.cnvImage)

        afwMath.convolve(self.cnvMaskedImage, self.maskedImage, kernel, convControl)
        cnvImMaskVarArr = imTestUtils.arraysFromMaskedImage(self.cnvMaskedImage)

        if display and False:
            refMaskedImage = imTestUtils.maskedImageFromArrays(refCnvImMaskVarArr)
            ds9.mtv(displayUtils.Mosaic().makeMosaic([
                self.maskedImage, refMaskedImage, self.cnvMaskedImage]), frame=0)
            if False:
                for (x, y) in ((0, 0), (1, 0), (0, 1), (50, 50)):
                    print "Mask(%d,%d) 0x%x 0x%x" % (x, y, refMaskedImage.getMask().get(x, y),
                    self.cnvMaskedImage.getMask().get(x, y))

        errStr = imTestUtils.imagesDiffer(cnvImArr, refCnvImMaskVarArr[0], rtol=rtol, atol=atol)
        if errStr:
            self.cnvImage.writeFits("act%s.fits" % (shortKernelDescr,))
            refMaskedImage = imTestUtils.maskedImageFromArrays(refCnvImMaskVarArr)
            refMaskedImage.getImage().writeFits("des%s.fits" % (shortKernelDescr,))
            self.fail("convolve(Image, kernel=%s, doNormalize=%s, doCopyEdge=%s, maxInterpErr=%s) failed:\n%s" % \
                (kernelDescr, doNormalize, doCopyEdge, maxInterpErr, errStr))

        errStr = imTestUtils.maskedImagesDiffer(cnvImMaskVarArr, refCnvImMaskVarArr,
            doVariance = True, rtol=rtol, atol=atol)
        if errStr:
            self.cnvMaskedImage.writeFits("act%s" % (shortKernelDescr,))
            refMaskedImage = imTestUtils.maskedImageFromArrays(refCnvImMaskVarArr)
            refMaskedImage.writeFits("des%s" % (shortKernelDescr,))
            self.fail("convolve(MaskedImage, kernel=%s, doNormalize=%s, doCopyEdge=%s, maxInterpErr=%s) failed:\n%s" % \
                (kernelDescr, doNormalize, doCopyEdge, maxInterpErr, errStr))

        if not sameMaskPlaneDicts(self.cnvMaskedImage, self.maskedImage):
            self.cnvMaskedImage.writeFits("act%s" % (shortKernelDescr,))
            refMaskedImage = imTestUtils.maskedImageFromArrays(refCnvImMaskVarArr)
            refMaskedImage.writeFits("des%s" % (shortKernelDescr,))
            self.fail("convolve(MaskedImage, kernel=%s, doNormalize=%s, doCopyEdge=%s, maxInterpErr=%s) failed:\n%s" % \
                (kernelDescr, doNormalize, doCopyEdge, maxInterpErr, "convolved mask dictionary does not match input"))

    def runStdTest(self, kernel, refKernel=None, kernelDescr="", rtol=1.0e-05, atol=1e-08,
        maxInterpErr=1.0e-9):
        """Assert that afwMath::convolve gives the same result as reference convolution for a given kernel.
        
        Inputs:
        - kernel: convolution kernel
        - refKernel: kernel to use for refConvolve (if None then kernel is used)
        - kernelDescr: description of kernel
        - rtol: relative tolerance (see below)
        - atol: absolute tolerance (see below)
        - maxInterpErr: maximum allowed interpolation error
        
        rtol and atol are positive, typically very small numbers.
        The relative difference (rtol * abs(b)) and the absolute difference "atol" are added together
        to compare against the absolute difference between "a" and "b".
        """
        if VERBOSITY > 0:
            print "Test convolution with", kernelDescr
        
        convControl = afwMath.ConvolutionControl()
        convControl.setMaxInterpolationError(maxInterpErr)
        
        # verify dimension assertions:
        # - output image dimensions = input image dimensions
        # - input image width and height >= kernel width and height
        # Note: the assertion kernel size > 0 is tested elsewhere
        for inWidth in (kernel.getWidth() - 1, self.width-1, self.width, self.width + 1):
            for inHeight in (kernel.getHeight() - 1, self.width-1, self.width, self.width + 1):
                if (inWidth == self.width) and (inHeight == self.height):
                    continue
                inMaskedImage = afwImage.MaskedImageF(inWidth, inHeight)
                self.assertRaises(Exception, afwMath.convolve, self.cnvMaskedImage, inMaskedImage, kernel)

        for doNormalize in (True,): # (False, True):
            convControl.setDoNormalize(doNormalize)
            for doCopyEdge in (False,): # (False, True):
                convControl.setDoCopyEdge(doCopyEdge)
                self.runBasicTest(kernel, convControl=convControl, refKernel=refKernel,
                    kernelDescr=kernelDescr, rtol=rtol, atol=atol)

    def testConvolutionControl(self):
        """Test the ConvolutionControl object
        """
        convControl = afwMath.ConvolutionControl()
        self.assert_(convControl.getDoNormalize())
        for doNormalize in (False, True):
            convControl.setDoNormalize(doNormalize)
            self.assert_(convControl.getDoNormalize() == doNormalize)
        
        self.assert_(not convControl.getDoCopyEdge())
        for doCopyEdge in (False, True):
            convControl.setDoCopyEdge(doCopyEdge)
            self.assert_(convControl.getDoCopyEdge() == doCopyEdge)

        self.assert_(convControl.getMaxInterpolationError() == 1.0e-3)
        for maxInterpErr in (0.0, 1.0e-99, 1.1e-5, 2.0e99):
            convControl.setMaxInterpolationError(maxInterpErr)
            self.assert_(convControl.getMaxInterpolationError() == maxInterpErr)
        
    def testUnityConvolution(self):
        """Verify that convolution with a centered delta function reproduces the original.
        """
        # create a delta function kernel that has 1,1 in the center
        kFunc = afwMath.IntegerDeltaFunction2D(0.0, 0.0)
        kernel = afwMath.AnalyticKernel(3, 3, kFunc)
        doNormalize = False
        doCopyEdge = False

        afwMath.convolve(self.cnvImage, self.maskedImage.getImage(), kernel, doNormalize, doCopyEdge)
        cnvImArr = imTestUtils.arrayFromImage(self.cnvImage)
        
        afwMath.convolve(self.cnvMaskedImage, self.maskedImage, kernel, doNormalize, doCopyEdge)
        cnvImMaskVarArr = imTestUtils.arraysFromMaskedImage(self.cnvMaskedImage)

        refCnvImMaskVarArr = imTestUtils.arraysFromMaskedImage(self.maskedImage)
        
        skipMaskArr = numpy.isnan(cnvImMaskVarArr[0])

        kernelDescr = "Centered DeltaFunctionKernel (testing unity convolution)"
        errStr = imTestUtils.imagesDiffer(cnvImArr, refCnvImMaskVarArr[0], skipMaskArr=skipMaskArr)
        if errStr:
            self.fail("convolve(Image, kernel=%s, doNormalize=%s, doCopyEdge=%s) failed:\n%s" % \
                (kernelDescr, doNormalize, doCopyEdge, errStr))
        errStr = imTestUtils.maskedImagesDiffer(cnvImMaskVarArr, refCnvImMaskVarArr, skipMaskArr=skipMaskArr)
        if errStr:
            self.fail("convolve(MaskedImage, kernel=%s, doNormalize=%s, doCopyEdge=%s) failed:\n%s" % \
                (kernelDescr, doNormalize, doCopyEdge, errStr))
        self.assert_(sameMaskPlaneDicts(self.cnvMaskedImage, self.maskedImage),
            "convolve(MaskedImage, kernel=%s, doNormalize=%s, doCopyEdge=%s) failed:\n%s" % \
            (kernelDescr, doNormalize, doCopyEdge, "convolved mask dictionary does not match input"))


    def testFixedKernelConvolve(self):
        """Test convolve with a fixed kernel
        """
        kCols = 6
        kRows = 7

        kFunc =  afwMath.GaussianFunction2D(2.5, 1.5, 0.5)
        analyticKernel = afwMath.AnalyticKernel(kCols, kRows, kFunc)
        kernelImage = afwImage.ImageD(kCols, kRows)
        analyticKernel.computeImage(kernelImage, False)
        fixedKernel = afwMath.FixedKernel(kernelImage)
        
        self.runStdTest(fixedKernel, kernelDescr="Gaussian FixedKernel")

    def testSeparableConvolve(self):
        """Test convolve of a separable kernel with a spatially invariant Gaussian function
        """
        kCols = 7
        kRows = 6

        gaussFunc1 = afwMath.GaussianFunction1D(1.0)
        gaussFunc2 = afwMath.GaussianFunction2D(1.0, 1.0, 0.0)
        separableKernel = afwMath.SeparableKernel(kCols, kRows, gaussFunc1, gaussFunc1)
        analyticKernel = afwMath.AnalyticKernel(kCols, kRows, gaussFunc2)
        
        self.runStdTest(separableKernel, refKernel=analyticKernel,
            kernelDescr="Gaussian Separable Kernel (compared to AnalyticKernel equivalent)")

    def testSpatiallyInvariantConvolve(self):
        """Test convolution with a spatially invariant Gaussian function
        """
        kCols = 6
        kRows = 7

        kFunc =  afwMath.GaussianFunction2D(2.5, 1.5, 0.5)
        kernel = afwMath.AnalyticKernel(kCols, kRows, kFunc)
        
        self.runStdTest(kernel, kernelDescr="Gaussian Analytic Kernel")

    def testSpatiallyVaryingAnalyticConvolve(self):
        """Test in-place convolution with a spatially varying AnalyticKernel
        """
        kCols = 7
        kRows = 6

        # create spatial model
        sFunc = afwMath.PolynomialFunction2D(1)
        
        minSigma = 1.5
        maxSigma = 1.501

        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (minSigma, (maxSigma - minSigma) / self.width, 0.0),
            (minSigma, 0.0,  (maxSigma - minSigma) / self.height),
            (0.0, 0.0, 0.0),
        )

        kFunc =  afwMath.GaussianFunction2D(1.0, 1.0, 0.0)
        kernel = afwMath.AnalyticKernel(kCols, kRows, kFunc, sFunc)
        kernel.setSpatialParameters(sParams)
        
        for maxInterpErr, rtol, methodStr in (
            (0.0,     1.0e-5, "brute force with no iteration"),
            (1.0e-99, 1.0e5,  "brute force after iteration"),
            (1.0e-9,  0.01,   "interpolation"),
        ):
            self.runStdTest(
                kernel,
                kernelDescr="Spatially Varying Gaussian Analytic Kernel with %s" % (methodStr,),
                maxInterpErr=maxInterpErr,
                rtol=rtol)

    def testSpatiallyVaryingSeparableConvolve(self):
        """Test convolution with a spatially varying SeparableKernel
        """
        kCols = 7
        kRows = 6

        # create spatial model
        sFunc = afwMath.PolynomialFunction2D(1)

        minSigma = 0.1
        maxSigma = 3.0
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (minSigma, (maxSigma - minSigma) / self.width, 0.0),
            (minSigma, 0.0,  (maxSigma - minSigma) / self.height),
            (0.0, 0.0, 0.0),
        )

        gaussFunc1 = afwMath.GaussianFunction1D(1.0)
        gaussFunc2 = afwMath.GaussianFunction2D(1.0, 1.0, 0.0)
        separableKernel = afwMath.SeparableKernel(kCols, kRows, gaussFunc1, gaussFunc1, sFunc)
        analyticKernel = afwMath.AnalyticKernel(kCols, kRows, gaussFunc2, sFunc)
        separableKernel.setSpatialParameters(sParams[0:2])
        analyticKernel.setSpatialParameters(sParams)

        self.runStdTest(separableKernel, refKernel=analyticKernel,
            kernelDescr="Spatially Varying Gaussian Separable Kernel")
    
    def testDeltaConvolve(self):
        """Test convolution with various delta function kernels using optimized code
        """
        for kCols in range(1, 4):
            for kRows in range(1, 4):
                for activeCol in range(kCols):
                    for activeRow in range(kRows):
                        kernel = afwMath.DeltaFunctionKernel(kCols, kRows,
                            afwImage.PointI(activeCol, activeRow))
                        if display and False:
                            kim = afwImage.ImageD(kCols, kRows); kernel.computeImage(kim, False)
                            ds9.mtv(kim, frame=1)

                        self.runStdTest(kernel, kernelDescr="Delta Function Kernel")

    def testSpatiallyVaryingGaussianLinerCombination(self):
        """Test convolution with a spatially varying LinearCombinationKernel of two Gaussian basis kernels.
        """
        kCols = 5
        kRows = 5

        # create spatial model
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, -0.01/self.width, -0.01/self.height),
            (0.0,  0.01/self.width,  0.0/self.height),
            (0.0,  0.0/self.width,  0.01/self.height),
        )
        
        kVec = makeGaussianKernelVec(kCols, kRows)
        kernel = afwMath.LinearCombinationKernel(kVec, sFunc)
        kernel.setSpatialParameters(sParams)

        for maxInterpErr, rtol, methodStr in (
            (0.0,     1.0e-5, "brute force with no iteration"),
            (1.0e-99, 1.0e5,  "brute force after iteration"),
            (1.0e-9,  0.02,   "interpolation"),
        ):
            self.runStdTest(
                kernel,
                kernelDescr="Spatially Varying Gaussian Analytic Kernel with %s" % (methodStr,),
                maxInterpErr=maxInterpErr,
                rtol=rtol)

    def testSpatiallyVaryingDeltaFunctionLinearCombination(self):
        """Test convolution with a spatially varying LinearCombinationKernel of delta function basis kernels.
        """
        kCols = 2
        kRows = 2

        # create spatially model
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, -0.5/self.width, -0.5/self.height),
            (0.0,  1.0/self.width,  0.0/self.height),
            (0.0,  0.0/self.width,  1.0/self.height),
            (0.5, 0.0, 0.0),
            )
        
        kVec = makeDeltaFunctionKernelVec(kCols, kRows)
        kernel = afwMath.LinearCombinationKernel(kVec, sFunc)
        kernel.setSpatialParameters(sParams)

        self.runStdTest(kernel,
            kernelDescr="Spatially varying LinearCombinationKernel of delta function basis kernels")

    def testZeroWidthKernel(self):
        """Convolution by a 0x0 kernel should raise an exception.
        
        The only way to produce a 0x0 kernel is to use the default constructor
        (which exists only to support persistence; it does not produce a useful kernel).
        """
        kernelList = [
            afwMath.FixedKernel(),
            afwMath.AnalyticKernel(),
            afwMath.SeparableKernel(),
#            afwMath.DeltaFunctionKernel(),  # DeltaFunctionKernel has no default constructor
            afwMath.LinearCombinationKernel(),
        ]
        convolutionControl = afwMath.ConvolutionControl()
        for kernel in kernelList:
            self.assertRaises(Exception, afwMath.convolve, self.cnvMaskedImage, self.maskedImage, kernel,
                convolutionControl)

    def testTicket873(self):
        """Demonstrate ticket 873: convolution of a MaskedImage with a spatially varying
        LinearCombinationKernel of basis kernels with low covariance gives incorrect variance.
        """
        # create spatial model
        sFunc = afwMath.PolynomialFunction2D(1)
        
        # spatial parameters are a list of entries, one per kernel parameter;
        # each entry is a list of spatial parameters
        sParams = (
            (1.0, -0.5/self.width, -0.5/self.height),
            (0.0,  1.0/self.width,  0.0/self.height),
            (0.0,  0.0/self.width,  1.0/self.height),
        )
        
        # create three kernels with some non-overlapping pixels
        # (non-zero pixels in one kernel vs. zero pixels in other kernels);
        # note: the extreme example of this is delta function kernels, but this is less extreme
        kVec = afwMath.KernelList()
        kImArr = numpy.zeros([5, 5], dtype=float)
        kImArr[1:4, 1:4] = 0.5
        kImArr[2, 2] = 1.0
        kImage = imTestUtils.imageFromArray(kImArr, afwImage.ImageD)
        kVec.append(afwMath.FixedKernel(kImage))
        kImArr[:, :] = 0.0
        kImArr[0:2, 0:2] = 0.125
        kImArr[3:5, 3:5] = 0.125
        kImage = imTestUtils.imageFromArray(kImArr, afwImage.ImageD)
        kVec.append(afwMath.FixedKernel(kImage))
        kImArr[:, :] = 0.0
        kImArr[0:2, 3:5] = 0.125
        kImArr[3:5, 0:2] = 0.125
        kImage = imTestUtils.imageFromArray(kImArr, afwImage.ImageD)
        kVec.append(afwMath.FixedKernel(kImage))

        kernel = afwMath.LinearCombinationKernel(kVec, sFunc)
        kernel.setSpatialParameters(sParams)

        self.runStdTest(kernel,
            kernelDescr="Spatially varying LinearCombinationKernel of basis kernels with low covariance")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""
    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(ConvolveTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)

    return unittest.TestSuite(suites)

def run(doExit=False):
    """Run the tests"""
    utilsTests.run(suite(), doExit)

if __name__ == "__main__":
    run(True)