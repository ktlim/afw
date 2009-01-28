
// -*- lsst-c++ -*-
//
//##====----------------                                ----------------====##/
//
//! \file
//! \brief  Does Wcs class in Wcs.cc correctly transform pixel coords <--> ra/dec coords
//
//##====----------------                                ----------------====##/




#include <iostream>
#include <cmath>
#include <vector>

#define BOOST_TEST_DYN_LINK
#define BOOST_TEST_MODULE Wcs test

#include "boost/test/unit_test.hpp"
#include "boost/test/floating_point_comparison.hpp"

#include "boost/numeric/ublas/matrix.hpp"

#include "lsst/afw/image/Image.h"
#include "lsst/afw/image/Wcs.h"
#include "lsst/afw/math/Interpolate.h"
#include "lsst/afw/math/Background.h"

namespace image = lsst::afw::image;
typedef boost::numeric::ublas::matrix<double> matrixD;


BOOST_AUTO_TEST_CASE(constructors_test) {
    image::PointD crval(30.0, 80.9);
    image::PointD crpix(127,127);
    matrixD CD(2,2);

    //An identity matrix
    CD(0,0) = CD(1,0) = 1;
    CD(1,0) = CD(0,1) = 0;


    image::Wcs wcs();

    image::Wcs wcs2(crval, crpix, CD);
    
}


BOOST_AUTO_TEST_CASE(radec_to_xy) {
    image::PointD crval(80.159679, 30.806568);
    image::PointD crpix(891.500000, 893.500000);
    matrixD CD(2,2);

    CD(0,0) = -0.0002802350;
    CD(0,1) = -0.0000021800;
    CD(1,0) = -0.0000022507;
    CD(1,1) = 0.0002796878;

    image::Wcs wcs(crval, crpix, CD);

    //check the trivial case
    image::PointD xy = wcs.raDecToXY(80.159679, 30.80656);
    BOOST_CHECK_CLOSE(xy.getX(), 891.5, .1);
    BOOST_CHECK_CLOSE(xy.getY(), 893.5, .1);  
        
    xy = wcs.raDecToXY(80.258354, +30.810147);
    BOOST_CHECK_CLOSE(xy.getX(), 589., .1);
    BOOST_CHECK_CLOSE(xy.getY(), 904., .1);

    xy = wcs.raDecToXY(80.382829, +31.0287389);
    BOOST_CHECK_CLOSE(xy.getX(), 203., .1);
    BOOST_CHECK_CLOSE(xy.getY(), 1683., .1);

    xy = wcs.raDecToXY(79.900717, +31.0046556);
    BOOST_CHECK_CLOSE(xy.getX(), 1678., .1);
    BOOST_CHECK_CLOSE(xy.getY(), 1609., .1);

    xy = wcs.raDecToXY(79.987550, +30.6272333);
    BOOST_CHECK_CLOSE(xy.getX(), 1425., .1);
    BOOST_CHECK_CLOSE(xy.getY(), 257., .1);


}
    

BOOST_AUTO_TEST_CASE(xy_to_radec) {
    image::PointD crval(80.159679, 30.806568);
    image::PointD crpix(891.500000, 893.500000);
    matrixD CD(2,2);

    CD(0,0) = -0.0002802350;
    CD(0,1) = -0.0000021800;
    CD(1,0) = -0.0000022507;
    CD(1,1) = 0.0002796878;

    image::Wcs wcs(crval, crpix, CD);

    //check the trivial case
    image::PointD ad = wcs.xyToRaDec(891.5, 893.5);
    BOOST_CHECK_CLOSE(ad.getX(), 80.15967 , 3e-5);  //2e-5 is <0.01 arcsec in ra
    BOOST_CHECK_CLOSE(ad.getY(), 30.80656 ,3e-5);  // 2e-5 is <0.1 arcsec in dec

    ad = wcs.xyToRaDec(141., 117.);
    BOOST_CHECK_CLOSE(ad.getX(), 80.405963 , 3e-5);
    BOOST_CHECK_CLOSE(ad.getY(),  +30.5908500 , 3e-5);  

    ad = wcs.xyToRaDec(397., 1482.);
    BOOST_CHECK_CLOSE(ad.getX(), 80.319804 , 3e-5);
    BOOST_CHECK_CLOSE(ad.getY(), +30.9721778 , 3e-5 );  

    ad = wcs.xyToRaDec(1488., 1755.);
    BOOST_CHECK_CLOSE(ad.getX(), 79.962379 , 3e-5);
    BOOST_CHECK_CLOSE(ad.getY(), +31.0460250 , 3e-5);  

    ad = wcs.xyToRaDec(1715., 187.);
    BOOST_CHECK_CLOSE(ad.getX(), 79.893342 , 3e-5);
    BOOST_CHECK_CLOSE(ad.getY(), +30.6068444 , 3e-5);  

    std::printf("T'end\n");
}

BOOST_AUTO_TEST_CASE(test_closure) {
    image::PointD crval(80.159679, 30.806568);
    image::PointD crpix(891.500000, 893.500000);
    matrixD CD(2,2);

    CD(0,0) = -0.0002802350;
    CD(0,1) = -0.0000021800;
    CD(1,0) = -0.0000022507;
    CD(1,1) = 0.0002796878;

    image::Wcs wcs(crval, crpix, CD);

    double x = 252;
    double y = 911;
    image::PointD xy(252., 911.);
    image::PointD ad = wcs.xyToRaDec(xy);
    BOOST_CHECK_CLOSE(wcs.raDecToXY(ad).getX(), x, 1e-6);
    BOOST_CHECK_CLOSE(wcs.raDecToXY(ad).getY(), y, 1e-6);
}


BOOST_AUTO_TEST_CASE(linearMatrix) {
    
    image::PointD crval(80.159679, 30.806568);
    image::PointD crpix(891.500000, 893.500000);
    matrixD CD(2,2);

    CD(0,0) = -0.0002802350;
    CD(0,1) = -0.0000021800;
    CD(1,0) = -0.0000022507;
    CD(1,1) = 0.0002796878;

    image::Wcs wcs(crval, crpix, CD);
    
    matrixD M = wcs.getLinearTransformMatrix();
    BOOST_CHECK_CLOSE(CD(0,0), M(0,0), 1e-6);
    BOOST_CHECK_CLOSE(CD(0,1), M(0,1), 1e-6);
    BOOST_CHECK_CLOSE(CD(1,0), M(1,0), 1e-6);
    BOOST_CHECK_CLOSE(CD(1,1), M(1,1), 1e-6);
}