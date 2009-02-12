#!/usr/bin/env python
"""
Tests for C++ DiaSource and PersistableDiaSourceVector Python wrappers (including persistence)

Run with:
   python Source_2.py
or
   python
   >>> import unittest; T=load("Source_2"); unittest.TextTestRunner(verbosity=1).run(T.suite())
"""
import pdb
import unittest
import random
import time

import lsst.daf.base as dafBase
import lsst.pex.policy as dafPolicy
import lsst.daf.persistence as dafPers
import lsst.utils.tests as utilsTests
import lsst.afw.detection as afwDet

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class DiaSourceTestCase(unittest.TestCase):
    """A test case for DiaSource and DiaSourceVec"""

    def setUp(self):
        self.container1 = afwDet.DiaSourceContainer(16)
        self.container2 = afwDet.DiaSourceContainer()
        
        for m in xrange(16):
            ds = afwDet.DiaSource()
            ds.setId(m + 1)
            self.container1[m] = ds
            
            ds = afwDet.DiaSource()
            ds.setId(m)
            ds.setRa(m*20)
            self.container2.push_back(ds)

        self.dsv1 = afwDet.DiaSourceVec(self.container1)
        self.dsv2 = afwDet.DiaSourceVec(self.container2)

    def tearDown(self):
        del self.dsv1
        del self.dsv2

    def testIterable(self):
        """Check that we can iterate over a SourceContainer"""
        j = 1
        container = self.container1[:]
        for s in xrange(container.size()):
            assert container[s].getId() == j
            j += 1

    def testCopyAndCompare(self):
        dsv1Copy = afwDet.DiaSourceContainer()
        self.dsv1.getSources(dsv1Copy)
        dsv2Copy = afwDet.DiaSourceContainer()
        self.dsv2.getSources(dsv2Copy)
        
        assert dsv1Copy.size() == self.container1.size()
        for i in xrange(dsv1Copy.size()):
            assert dsv1Copy[i] == self.container1[i]        
        assert dsv2Copy.size() == self.container2.size()
        for i in xrange(dsv2Copy.size()):
            assert dsv2Copy[i] == self.container2[i]

        dsv1Copy.swap(dsv2Copy)
        assert dsv2Copy.size() == self.container1.size()
        for i in xrange(dsv2Copy.size()):
            assert dsv2Copy[i] == self.container1[i]           
        assert dsv1Copy.size() == self.container2.size()
        for i in xrange(dsv1Copy.size()):
            assert dsv1Copy[i] == self.container2[i]
            
        dsv1Copy.swap(dsv2Copy)

        ds = afwDet.DiaSource()        
        if dsv1Copy.size() == 0:
            dsv1Copy.append(ds)
        else:
            dsv1Copy.pop()
        dsv2Copy.append(ds)
        
        assert dsv1Copy.size() != self.container1.size()
        assert dsv2Copy.size() != self.container2.size()

    def testInsertErase(self):
        container = afwDet.DiaSourceContainer()
        self.dsv1.getSources(container)

        
        front = container[:8]
        back = container[8:]

        copy = afwDet.DiaSourceContainer()
        
        for i in xrange(front.size()):
            copy.append(front[i])
            
        ds = afwDet.DiaSource()
        for i in xrange(4):
            copy.append(ds)
        
        for i in xrange(back.size()):
            copy.append(back[i])
                    
        del copy[8]
        del copy[8:11]
        assert copy.size() == self.container1.size()
        for i in xrange(copy.size()):
            assert copy[i] == self.container1[i]       

    def testSlice(self):
        containerSlice = afwDet.DiaSourceContainer()
        self.dsv1.getSources(containerSlice)
        containerSlice = containerSlice[0:3]
        
        j = 1
        for i in xrange(containerSlice.size()):
            assert containerSlice[i].getId() == j
            j += 1

    def testPersistence(self):
        if dafPers.DbAuth.available():
            pol  = dafPolicy.Policy()
            pers = dafPers.Persistence.getPersistence(pol)
            loc  = dafPers.LogicalLocation("mysql://lsst10.ncsa.uiuc.edu:3306/source_test")
            dp = dafBase.PropertySet()
            dp.addInt("visitId", int(time.clock())*16384 + random.randint(0,16383))
            dp.addInt("sliceId", 0)
            dp.addInt("numSlices", 1)
            dp.addString("itemName", "DiaSource")
            stl = dafPers.StorageList()
            stl.append(pers.getPersistStorage("DbStorage", loc))
            pers.persist(self.dsv1, stl, dp)
            stl = dafPers.StorageList()
            stl.append(pers.getRetrieveStorage("DbStorage", loc))
            persistable = pers.unsafeRetrieve("PersistableDiaSourceVector", stl, dp)
            res = afwDet.DiaSourceVec.swigConvert(persistable)
            afwDet.dropAllVisitSliceTables(loc, pol, dp)
            assert(res == self.dsv1)
        else:
            print "skipping database tests"


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(DiaSourceTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

if __name__ == "__main__":
    utilsTests.run(suite())
