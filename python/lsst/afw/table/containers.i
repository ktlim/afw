%{
#include "lsst/afw/table/Catalog.h"
#include "lsst/afw/table/Simple.h"
#include "lsst/afw/table/Source.h"
%}

%pythondynamic;  // We want to add attributes in Python for the classes wrapped here.

namespace lsst { namespace afw { namespace table {

template <typename RecordT>
class CatalogT {
public:

    typedef typename RecordT::Table Table;
    typedef typename RecordT::ColumnView ColumnView;

    PTR(Table) getTable() const;

    %feature("autodoc", "Return the table shared by all the catalog's records.") getTable;

    Schema getSchema() const;

    %feature("autodoc", "Shortcut for self.getTable().getSchema()") getSchema;

    explicit CatalogT(PTR(Table) const & table);

    explicit CatalogT(Schema const & table);

    CatalogT(CatalogT const & other);

    %feature(
        "autodoc", 
        "Constructors:  __init__(self, table) -> empty catalog with the given table\n"
        "               __init__(self, schema) -> empty catalog with a new table with the given schema\n"
        "               __init__(self, catalog) -> shallow copy of the given catalog\n"
    ) CatalogT;

    void writeFits(std::string const & filename, std::string const & mode="w") const;

    static CatalogT readFits(std::string const & filename, int hdu=2);

    ColumnView getColumnView() const;
    %pythonappend getColumnView %{
        self._columns = val
    %}

    PTR(RecordT) addNew();

    CatalogT copy() const;

};

%extend CatalogT {
    std::size_t __len__() const { return self->size(); }
    PTR(RecordT) __getitem__(std::ptrdiff_t i) const {
        if (i < 0) i = self->size() - i;
        if (std::size_t(i) >= self->size()) {
            throw LSST_EXCEPT(
                lsst::pex::exceptions::InvalidParameterException,
                (boost::format("Catalog index %d out of range.") % i).str()
            );
        }
        return self->get(i);
    }
    %feature("shadow") __getitem__ %{
    def __getitem__(self, k):
        """Return the record at index k if k is an integer,
        or return a column if k is a string field name or Key.
        """
        try:
            return $action(self, k)
        except TypeError:
            return self.columns[k]
    %}
    void __setitem__(std::ptrdiff_t i, PTR(RecordT) const & p) {
        if (i < 0) i = self->size() - i;
        if (std::size_t(i) >= self->size()) {
            throw LSST_EXCEPT(
                lsst::pex::exceptions::InvalidParameterException,
                (boost::format("Catalog index %d out of range.") % i).str()
            );
        }
        self->set(i, p);
    }
    void __delitem__(std::ptrdiff_t i) {
        if (i < 0) i = self->size() - i;
        if (std::size_t(i) >= self->size()) {
            throw LSST_EXCEPT(
                lsst::pex::exceptions::InvalidParameterException,
                (boost::format("Catalog index %d out of range.") % i).str()
            );
        }
        self->erase(self->begin() + i);
    }
    void append(PTR(RecordT) const & p) { self->push_back(p); }
    void insert(std::ptrdiff_t i, PTR(RecordT) const & p) {
        if (i < 0) i = self->size() - i;
        if (std::size_t(i) > self->size()) {
            throw LSST_EXCEPT(
                lsst::pex::exceptions::InvalidParameterException,
                (boost::format("Catalog index %d out of range.") % i).str()
            );
        }
        self->insert(self->begin() + i, p);
    }
    %feature("pythonprepend") __setitem__ %{
        self._columns = None
    %}
    %feature("pythonprepend") __delitem__ %{
        self._columns = None
    %}
    %feature("pythonprepend") append %{
        self._columns = None
    %}
    %feature("pythonprepend") insert %{
        self._columns = None
    %}
    %pythoncode %{
    def __getColumns(self):
        if not hasattr(self, "_columns") or self._columns is None:
            self._columns = self.getColumnView()
        return self._columns
    columns = property(__getColumns, doc="a column view of the catalog")
    def extend(self, iterable):
        """Append all records in the given iterable to the catalog."""
        for e in iterable:
            self.append(e)
    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]
    def get(self, k):
        """Synonym for self[k]; provided for consistency with C++ interface."""
        return self[k]
    def cast(self, type_, deep=False):
        """Return a copy of the catalog with the given type, optionally
        cloning the table and deep-copying all records if deep==True.
        """
        table = self.table.clone() if deep else self.table
        newTable = table.cast(type_.Table)
        copy = type_(newTable)
        for record in self:
            newRecord = newTable.copyRecord(record) if deep else record.cast(type_.Record)
            copy.append(newRecord)
        return copy
    def copy(self, deep=False):
        return self.cast(type(self), deep)
    def __getattribute__(self, name):
        # Catalog forwards unknown method calls to its table and column view
        # for convenience.  (Feature requested by RHL; complaints about magic
        # should be directed to him.)
        # We have to use __getattribute__ because SWIG overrides __getattr__.
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            pass
        try:
            return getattr(self.table, name)
        except AttributeError:
            return getattr(self.columns, name)
    table = property(getTable)
    schema = property(getSchema)
    %}
}

template <typename RecordT>
class SimpleCatalogT : public CatalogT<RecordT> {
public:

    typedef typename RecordT::Table Table;

    explicit SimpleCatalogT(PTR(Table) const & table);

    explicit SimpleCatalogT(Schema const & table);

    SimpleCatalogT(SimpleCatalogT const & other);

    %feature(
        "autodoc", 
        "Constructors:  __init__(self, table) -> empty catalog with the given table\n"
        "               __init__(self, schema) -> empty catalog with a new table with the given schema\n"
        "               __init__(self, catalog) -> shallow copy of the given catalog\n"
    ) SimpleCatalogT;

    static SimpleCatalogT readFits(std::string const & filename, int hdu=2);

    SimpleCatalogT copy() const;

    bool isSorted() const;
    void sort();
};

%extend SimpleCatalogT {
    PTR(RecordT) find(RecordId id) {
        return self->find(id);
    }
}

%define %declareCatalog(TMPL, PREFIX)
%template (PREFIX ## Catalog) TMPL< PREFIX ## Record >;
typedef TMPL< PREFIX ## Record > PREFIX ## Catalog;
%extend TMPL< PREFIX ## Record > {
%pythoncode %{
    Table = PREFIX ## Table
    Record = PREFIX ## Record
    ColumnView = PREFIX ## ColumnView
%}
}
// Can't put this in class %extend blocks because they need to come after all class blocks in Python.xz
%pythoncode %{ 
PREFIX ## Record.Table = PREFIX ## Table
PREFIX ## Record.Catalog = PREFIX ## Catalog
PREFIX ## Record.ColumnView = PREFIX ## ColumnView
PREFIX ## Table.Record = PREFIX ## Record
PREFIX ## Table.Catalog = PREFIX ## Catalog
PREFIX ## Table.ColumnView = PREFIX ## ColumnView
PREFIX ## ColumnView.Record = PREFIX ## Record
PREFIX ## ColumnView.Table = PREFIX ## Table
PREFIX ## ColumnView.Catalog = PREFIX ## Catalog
%}
%enddef


%template (SimpleCatalogBase) CatalogT<SimpleRecord>;
%template (SourceCatalogBase) CatalogT<SourceRecord>;


%declareCatalog(CatalogT, Base)
%declareCatalog(SimpleCatalogT, Simple);
%declareCatalog(SimpleCatalogT, Source);

}}} // namespace lsst::afw::table

%pythonnondynamic;  // Re-enable attribute restriction