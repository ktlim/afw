/*
 * LSST Data Management System
 * Copyright 2014 LSST Corporation.
 *
 * This product includes software developed by the
 * LSST Project (http://www.lsst.org/).
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the LSST License Statement and
 * the GNU General Public License along with this program.  If not,
 * see <http://www.lsstcorp.org/LegalNotices/>.
 */

#include <sstream>
#include <utility>
#include "lsst/afw/cameraGeom/Detector.h"

namespace lsst {
namespace afw {
namespace cameraGeom {

Detector::Detector(std::string const &name, int id, DetectorType type, std::string const &serial,
                   lsst::geom::Box2I const &bbox, table::AmpInfoCatalog const &ampInfoCatalog,
                   Orientation const &orientation, lsst::geom::Extent2D const &pixelSize,
                   TransformMap::Transforms const &transforms, CrosstalkMatrix const &crosstalk) :
    Detector(name, id, type, serial, bbox, ampInfoCatalog, orientation, pixelSize,
             TransformMap::make(CameraSys(PIXELS, name), transforms),
             crosstalk)
{}

Detector::Detector(std::string const &name, int id, DetectorType type, std::string const &serial,
                   lsst::geom::Box2I const &bbox, table::AmpInfoCatalog const &ampInfoCatalog,
                   Orientation const &orientation, lsst::geom::Extent2D const &pixelSize,
                   std::shared_ptr<TransformMap const> transformMap, CrosstalkMatrix const &crosstalk) :
    _name(name),
    _id(id),
    _type(type),
    _serial(serial),
    _bbox(bbox),
    _ampInfoCatalog(ampInfoCatalog),
    _ampNameIterMap(),
    _orientation(orientation),
    _pixelSize(pixelSize),
    _nativeSys(CameraSys(PIXELS, name)),
    _transformMap(std::move(transformMap)),
    _crosstalk(crosstalk)
{
    // make _ampNameIterMap
    for (auto ampIter = _ampInfoCatalog.begin(); ampIter != _ampInfoCatalog.end(); ++ampIter) {
        _ampNameIterMap.insert(std::make_pair(ampIter->getName(), ampIter));
    }
    if (_ampNameIterMap.size() != _ampInfoCatalog.size()) {
        throw LSST_EXCEPT(pexExcept::InvalidParameterError,
                          "Invalid ampInfoCatalog: not all amplifier names are unique");
    }

    // ensure crosstalk coefficients matrix is square
    if (hasCrosstalk()) {
        auto shape = _crosstalk.getShape();
        assert(shape.size() == 2);  // we've declared this as a 2D array
        if (shape[0] != shape[1]) {
            std::ostringstream os;
            os << "Non-square crosstalk matrix: " << _crosstalk << " for detector \"" << _name << "\"";
            throw LSST_EXCEPT(pexExcept::InvalidParameterError, os.str());
        }
        if (shape[0] != _ampInfoCatalog.size()) {
            std::ostringstream os;
            os << "Wrong size crosstalk matrix: " << _crosstalk << " for detector \"" << _name << "\"";
            throw LSST_EXCEPT(pexExcept::InvalidParameterError, os.str());
        }
    }
}

std::vector<lsst::geom::Point2D> Detector::getCorners(CameraSys const &cameraSys) const {
    std::vector<lsst::geom::Point2D> nativeCorners = lsst::geom::Box2D(_bbox).getCorners();
    auto nativeToCameraSys = _transformMap->getTransform(_nativeSys, cameraSys);
    return nativeToCameraSys->applyForward(nativeCorners);
}

std::vector<lsst::geom::Point2D> Detector::getCorners(CameraSysPrefix const &cameraSysPrefix) const {
    return getCorners(makeCameraSys(cameraSysPrefix));
}

lsst::geom::Point2D Detector::getCenter(CameraSys const &cameraSys) const {
    auto ctrPix = lsst::geom::Box2D(_bbox).getCenter();
    auto transform = getTransform(PIXELS, cameraSys);
    return transform->applyForward(ctrPix);
}

lsst::geom::Point2D Detector::getCenter(CameraSysPrefix const &cameraSysPrefix) const {
    return getCenter(makeCameraSys(cameraSysPrefix));
}

const table::AmpInfoRecord &Detector::operator[](std::string const &name) const { return *(_get(name)); }

std::shared_ptr<table::AmpInfoRecord const> Detector::_get(int i) const {
    if (i < 0) {
        i = _ampInfoCatalog.size() + i;
    };
    return _ampInfoCatalog.get(i);
}

std::shared_ptr<table::AmpInfoRecord const> Detector::_get(std::string const &name) const {
    _AmpInfoMap::const_iterator ampIter = _ampNameIterMap.find(name);
    if (ampIter == _ampNameIterMap.end()) {
        std::ostringstream os;
        os << "Unknown amplifier \"" << name << "\"";
        throw LSST_EXCEPT(pexExcept::InvalidParameterError, os.str());
    }
    return ampIter->second;
}

bool Detector::hasTransform(CameraSys const &cameraSys) const { return _transformMap->contains(cameraSys); }

bool Detector::hasTransform(CameraSysPrefix const &cameraSysPrefix) const {
    return hasTransform(makeCameraSys(cameraSysPrefix));
}

template <typename FromSysT, typename ToSysT>
std::shared_ptr<geom::TransformPoint2ToPoint2> Detector::getTransform(FromSysT const &fromSys,
                                                                      ToSysT const &toSys) const {
    return _transformMap->getTransform(makeCameraSys(fromSys), makeCameraSys(toSys));
}

template <typename FromSysT, typename ToSysT>
lsst::geom::Point2D Detector::transform(lsst::geom::Point2D const &point, FromSysT const &fromSys,
                                        ToSysT const &toSys) const {
    return _transformMap->transform(point, makeCameraSys(fromSys), makeCameraSys(toSys));
}

template <typename FromSysT, typename ToSysT>
std::vector<lsst::geom::Point2D> Detector::transform(std::vector<lsst::geom::Point2D> const &points,
                                                     FromSysT const &fromSys, ToSysT const &toSys) const {
    return _transformMap->transform(points, makeCameraSys(fromSys), makeCameraSys(toSys));
}

//
// Explicit instantiations
//
#define INSTANTIATE(FROMSYS, TOSYS)                                                                         \
    template std::shared_ptr<geom::TransformPoint2ToPoint2> Detector::getTransform(FROMSYS const &,         \
                                                                                   TOSYS const &) const;    \
    template lsst::geom::Point2D Detector::transform(lsst::geom::Point2D const &, FROMSYS const &,          \
                                                     TOSYS const &) const;                                  \
    template std::vector<lsst::geom::Point2D> Detector::transform(std::vector<lsst::geom::Point2D> const &, \
                                                                  FROMSYS const &, TOSYS const &) const;

INSTANTIATE(CameraSys, CameraSys);
INSTANTIATE(CameraSys, CameraSysPrefix);
INSTANTIATE(CameraSysPrefix, CameraSys);
INSTANTIATE(CameraSysPrefix, CameraSysPrefix);

}  // namespace cameraGeom
}  // namespace afw
}  // namespace lsst
