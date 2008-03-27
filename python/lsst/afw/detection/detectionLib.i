// -*- lsst-c++ -*-
%define detectionLib_DOCSTRING
"
Access to persistable C++ objects for catalog data. Currently supported are:
    - Source
"
%enddef

%feature("autodoc", "1");
%module(docstring=detectionLib_DOCSTRING) detectionLib

// Suppress swig complaints
// I had trouble getting %warnfilter to work; hence the pragmas
#pragma SWIG nowarn=314                 // print is a python keyword (--> _print)
#pragma SWIG nowarn=362                 // operator=  ignored

%{
#include "lsst/fw/Source.h"
#include "lsst/fw/formatters/Utils.h"
%}

%inline %{
namespace boost { namespace filesystem {} }
%}

%init %{
%}

%pythoncode %{
import lsst.fw.exceptions
%}

%include "lsst/mwi/p_lsstSwig.i"
%include "lsst/mwi/persistenceMacros.i"
%import "lsst/mwi/persistence/Persistable.h"

%import "lsst/mwi/data/Citizen.h"
%import "lsst/mwi/policy/Policy.h"
%import "lsst/mwi/persistence/LogicalLocation.h"
%import "lsst/mwi/persistence/Persistence.h"
%import "lsst/mwi/persistence/Storage.h"
%import "lsst/mwi/data/DataProperty.h"


%include <stdint.i>
%include <std_vector.i>
%include <typemaps.i>

%rename(SourceVec)  lsst::fw::SourceVector;

%include "lsst/fw/Source.h"
%include "lsst/fw/formatters/Utils.h"


// Provide semi-useful printing of catalog records

%extend lsst::fw::Source {
    std::string toString() {
        std::ostringstream os;
        os << "Source " << $self->getId();
        os.precision(9);
        os << " (" << $self->getRa() << ", " << $self->getDec() << ")";
        return os.str();
    }
};


%pythoncode %{
Source.__str__ = Source.toString
%}

// Could define a single large SWIG macro to take care of all of this, but for now
// leave it as is for clarity and easy experimentation

%fragment("SourceVectorTraits","header",fragment="StdSequenceTraits")
%{
namespace swig {
    template <>
    struct traits_asptr<lsst::fw::SourceVector>  {
        static int asptr(PyObject *obj, lsst::fw::SourceVector **vec) {
            return traits_asptr_stdseq<lsst::fw::SourceVector>::asptr(obj, vec);
        }
    };
    
    template <>
    struct traits_from<lsst::fw::SourceVector> {
        static PyObject *from(const lsst::fw::SourceVector& vec) {
            return traits_from_stdseq<lsst::fw::SourceVector>::from(vec);
        }
    };
}
%}


// Define an analogue to %std_vector_methods()
// required since we have no access to std::vector::get_allocator()
%define %lsst_vector_methods(vec...)
  vec();
  vec(const vec&);
  vec(size_type size);
  vec(size_type size, const value_type& value);

  bool empty() const;
  size_type size() const;
  void clear();

  void swap(vec& v);

  #ifdef SWIG_EXPORT_ITERATOR_METHODS
  class iterator;
  class reverse_iterator;
  class const_iterator;
  class const_reverse_iterator;

  iterator begin();
  const_iterator begin() const;
  iterator end();
  const_iterator end() const;
  reverse_iterator rbegin();
  const_reverse_iterator rbegin() const;
  reverse_iterator rend();
  const_reverse_iterator rend() const;

  iterator erase(iterator pos);
  iterator erase(iterator first, iterator last);

  iterator insert(iterator pos, const value_type& x);
  void insert(iterator pos, size_type n, const value_type& x);
  #endif

  void pop_back();
  void push_back(const value_type& x);  

  const value_type& front() const;
  const value_type& back() const;
 
  void assign(size_type n, const value_type& x);
  void resize(size_type new_size);
  void resize(size_type new_size, const value_type& x);
 
  void reserve(size_type n);
  size_type capacity() const;

  bool operator==(vec const & v);
  bool operator!=(vec const & v);
%enddef


// Apply SWIG std::vector machinery to catalog classes. These classes contain a std::vector and look 
// like a std::vector, but do not derive from one (since std::vector has a non-virtual destructor).
namespace lsst {
namespace afw {
namespace detection {

class SourceVector : public lsst::mwi::persistence::Persistable {
public:
    typedef size_t size_type;
    typedef ptrdiff_t difference_type;
    typedef Source value_type;
    typedef value_type* pointer;
    typedef const value_type* const_pointer;
    typedef Source& reference;
    typedef const Source& const_reference;
    typedef std::allocator<lsst::fw::Source> allocator_type;

    %traits_swigtype(lsst::fw::Source);

    %fragment(SWIG_Traits_frag(lsst::fw::SourceVector), "header",
              fragment=SWIG_Traits_frag(lsst::fw::Source),
              fragment="SourceVectorTraits") {
        namespace swig {
            template <>  struct traits<lsst::fw::SourceVector> {
                typedef pointer_category category;
                static const char* type_name() {
                    return "lsst::fw::SourceVector";
                }
            };
        }
    }

    %typemap_traits_ptr(SWIG_TYPECHECK_VECTOR, lsst::fw::SourceVector);

    #ifdef %swig_vector_methods
    // Add swig/language extra methods
    %swig_vector_methods(lsst::fw::SourceVector);
    #endif

    %lsst_vector_methods(lsst::fw::SourceVector);
};



}}} // namespace lsst::afw::detection

// Make sure SWIG generates type information for boost::shared_ptr<lsst::mwi::Persistable> *,
// even though that type is actually wrapped in the persistence module
%types(boost::shared_ptr<lsst::mwi::persistence::Persistable> *);

// Export instantiations of boost::shared_ptr for persistable data vectors
%lsst_persistable_shared_ptr(SourceVecSharedPtr, lsst::fw::SourceVector);

%template(SourceSharedPtr) boost::shared_ptr<lsst::fw::Source>;

%pythoncode %{

def SourceVecPtr(*args):
    """return a SourceVecSharedPtr that owns its own SourceVec"""
    v = SourceVec(*args)
    v.this.disown()
    out = SourceVecSharedPtr(v)
    return out

def MopsPredVecPtr(*args):
    """return a MopsPredVecSharedPtr that owns its own MopsPredVec"""
    v = MopsPredVec(*args)
    v.this.disown()
    out = MopsPredVecSharedPtr(v)
    return out

def SourcePtr(*args):
    """return a SourceSharedPtr that owns its own Source"""
    ds = Source(*args)
    ds.this.disown()
    out = SourceSharedPtr(ds)
    return out

%}
