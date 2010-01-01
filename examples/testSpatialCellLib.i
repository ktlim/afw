// -*- lsst-c++ -*-
%define testSpatialCellLib_DOCSTRING
"
Various swigged-up C++ classes for testing
"
%enddef

%feature("autodoc", "1");
%module(package="testSpatialCellLib", docstring=testSpatialCellLib_DOCSTRING) testSpatialCellLib

%pythonnondynamic;
%naturalvar;  // use const reference typemaps

%include "lsst/p_lsstSwig.i"

%lsst_exceptions()

%{
#include "lsst/pex/policy.h"
#include "lsst/afw/geom.h"
#include "lsst/afw/math.h"
#include "testSpatialCell.h"
%}

%import "lsst/afw/image/imageLib.i"
%import "lsst/afw/math/mathLib.i"

SWIG_SHARED_PTR_DERIVED(ExampleCandidate,
                        lsst::afw::math::SpatialCellImageCandidate<lsst::afw::image::Image<float> >,
                        ExampleCandidate);

%include "testSpatialCell.h"

%inline %{
    ExampleCandidate *cast_ExampleCandidate(lsst::afw::math::SpatialCellCandidate* candidate) {
        return dynamic_cast<ExampleCandidate *>(candidate);
    }
%}