#if !defined(LSST_AFW_CAMERAGEOM_DETECTORMOSAIC_H)
#define LSST_AFW_CAMERAGEOM_DETECTORMOSAIC_H

#include <string>
#include "lsst/afw/geom.h"
#include "lsst/afw/image/Utils.h"
#include "lsst/afw/cameraGeom/Detector.h"
#include "lsst/afw/cameraGeom/Orientation.h"

/**
 * @file
 *
 * Describe a Mosaic of Detectors
 */
namespace lsst {
namespace afw {
namespace cameraGeom {

namespace afwGeom = lsst::afw::geom;

/**
 * Describe a set of Detectors that are physically closely related (e.g. on the same invar support)
 */
class DetectorMosaic : public Detector {
public:
    typedef boost::shared_ptr<DetectorMosaic> Ptr;
    typedef boost::shared_ptr<const DetectorMosaic> ConstPtr;

    typedef std::vector<Detector::Ptr> DetectorSet;
#if 0                                   // N.b. don't say "DetectorSet::iterator" for swig's sake
    typedef detectorSet::iterator iterator;
#else
    typedef std::vector<boost::shared_ptr<Detector> >::iterator iterator;
#endif
    typedef std::vector<Detector::Ptr>::const_iterator const_iterator;

    DetectorMosaic(Id id,               ///< ID for Mosaic
                   int const nCol,      ///< Number of columns of detectors
                   int const nRow       ///< Number of rows of detectors
                  ) : Detector(id, false), _nDetector(nCol, nRow) {}
    virtual ~DetectorMosaic() {}
    //
    // Provide iterators for all the Ccd's Detectors
    //
    iterator begin() { return _detectors.begin(); }
    const_iterator begin() const { return _detectors.begin(); }
    iterator end() { return _detectors.end(); }
    const_iterator end() const { return _detectors.end(); }
    //
    // Geometry of Detector --- i.e. mm not pixels
    //
    virtual void setCenter(afwGeom::Point2D const& center);
    virtual afwGeom::Extent2D getSize() const;
    //
    // Add a Detector to the DetectorMosaic
    //
    void addDetector(afwGeom::Point2I const& index, afwGeom::Point2D const& center,
                     Orientation const& orient, Detector::Ptr det);
    //
    // Find a Detector given an Id or pixel position
    //
    Detector::Ptr findDetector(Id const id) const;
    Detector::Ptr findDetector(afwGeom::Point2I const& pixel, bool const fromCenter=false) const;
    Detector::Ptr findDetector(afwGeom::Point2D const& posMm) const;
    //
    // Translate between physical positions in mm to pixels
    //
    virtual afwGeom::Point2I getIndexFromPosition(afwGeom::Point2D const& pos) const;
    virtual afwGeom::Point2I getPixelFromPosition(afwGeom::Point2D const& pos) const;
    virtual afwGeom::Point2D getPositionFromIndex(afwGeom::Point2I const& pix) const;
    virtual afwGeom::Point2D getPositionFromIndex(afwGeom::Point2I const& pix, bool const) const {
        return getPositionFromIndex(pix);
    }
private:
    DetectorSet _detectors;             // The Detectors that make up this DetectorMosaic
    std::pair<int, int> _nDetector;     // the number of columns/rows of Detectors
};

}}}

#endif