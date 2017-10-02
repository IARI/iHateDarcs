from _ast import Mod

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dateutil import parser
from copy import deepcopy


# import wrapt
# @wrapt.decorator
# def lazy(function, instance, args, kwargs):
#     assert isinstance(instance, type)
#     result = function(*args, **kwargs)
#     instance


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(current_dict.keys()), set(past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect if self.past_dict[o] == self.current_dict[o])


class LazyClassProp:
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func
        self.computed = False
        self.result = None

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)

        if not self.computed:
            self.result = self.func(klass)
            self.computed = True

        return self.result


class LazyProp:
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func
        self.attrname = "_LazyProp_" + self.__name__

    def __get__(self, obj, klass=None):
        if not hasattr(obj, self.attrname):
            setattr(obj, self.attrname, self.func(obj))

        return getattr(obj, self.attrname)


class DefaultMethod:
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func
        self._overwritten = {}
        self.attrname = "_LazyProp_" + self.__name__

    def _key(self, instance):
        return str(instance) + '_' + self.func.__qualname__

    def overwritten(self, instance):
        return self._overwritten.get(self._key(instance), None)

    def __get__(self, obj, klass=None):
        overwritten = self.overwritten(obj)
        if callable(overwritten):
            return overwritten.__get__(obj, obj)

        return self.func.__get__(obj, obj)

    def __set__(self, instance, value):
        self._overwritten[self._key(instance)] = value


class SpreadWrapper(gspread.models.Spreadsheet):
    @classmethod
    def fromSheet(cls, sheet: gspread.models.Spreadsheet):
        return cls(sheet.client, sheet._feed_entry)

    def getSheetTime(self):
        return parser.parse(self.sheet1.updated)


class SpreadDB:
    def __init__(self, key_file: str, scope=('https://spreadsheets.google.com/feeds',)):
        scopes = list(scope)
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(key_file, scopes)
        self.client = gspread.authorize(self.credentials)

    @LazyProp
    def all_sheets(self):
        return [SpreadWrapper.fromSheet(s) for s in self.client.openall()]

    @LazyProp
    def sheet_dict(self):
        return {s.title: s for s in self.all_sheets}

    @LazyProp
    def latest_first(self):
        return sorted(self.all_sheets, key=SpreadWrapper.getSheetTime, reverse=True)


class ParseException(Exception):
    pass


class Column:
    def __init__(self,
                 label=None,
                 nr=None,
                 validate=None,
                 testLabel=None,
                 required=False):
        self.label = label
        self.nr = nr
        self.name = None
        self.testLabel = testLabel
        if callable(validate):
            self.validate = validate
        if required:
            def d_validate(self, val):
                try:
                    return bool(self.parseValue(val))
                except ParseException:
                    return False

            self.validate = d_validate

    def add_to_class(self, model_class, name):
        assert issubclass(model_class, Model)

        self.name = name
        if self.label is None:
            self.label = name
        self.model_class = model_class

        model_class._meta.add_field(self)
        setattr(model_class, name, ColumnDescriptor(self))
        self._is_bound = True

    @DefaultMethod
    def validate(self, val):
        try:
            self.parseValue(val)
            return True
        except ParseException:
            return False

    @DefaultMethod
    def parseValue(self, val):
        return val

    @DefaultMethod
    def writeValue(self, val):
        return val

    @DefaultMethod
    def testLabel(self, headings):
        return self.label in headings

    @DefaultMethod
    def effective_nr(self, headings):
        if isinstance(self.nr, int):
            return self.nr
        else:
            return headings.index(self.label)

    @property
    def col_nr(self):
        return self.effective_nr(self.model_class.headings)

    def cell(self, model):
        return model._get_col_nr(self.col_nr + 1)


class ModelOptions(object):
    def __init__(self, cls, database: SpreadDB, db_table=None, db_table_func=None, constraints=None, schema=None,
                 **kwargs):
        self.model_class = cls
        self.name = cls.__name__.lower()
        self.fields = {}
        self.columns = {}
        self.defaults = {}
        self._default_by_name = {}
        self._default_dict = {}
        self._default_callables = {}
        self._default_callable_list = []
        self.sorted_fields = []
        self.sorted_field_names = []
        self.valid_fields = set()
        self.declared_fields = []

        self.database = database  # if database is not None else default_database
        self.db_table_func = db_table_func

        self.db_table = db_table
        if callable(self.db_table_func) and not self.db_table:
            self.db_table = self.db_table_func(cls)
        if db_table is not None:
            print("No db table name for {}, trying classname.".format(self.name))
            self.db_table = cls.__name__

        self.constraints = constraints
        self.schema = schema

        for key, value in kwargs.items():
            setattr(self, key, value)
        self._additional_keys = set(kwargs.keys())

    def add_field(self, col):
        self.fields[col.name] = col


class MetaModel(type):
    inheritable = {'constraints', 'database', 'db_table_func', 'indexes', 'order_by', 'primary_key', 'schema',
                   'validate_backrefs', 'only_save_dirty'}

    def __new__(cls, name, bases, attrs):
        meta_options = {}
        meta = attrs.pop('Meta', None)
        if meta:
            for k, v in meta.__dict__.items():
                if not k.startswith('_'):
                    meta_options[k] = v

        # inherit any field descriptors by deep copying the underlying field
        # into the attrs of the new model, additionally see if the bases define
        # inheritable model options and swipe them

        for b in bases:
            if not hasattr(b, '_meta'):
                continue

            base_meta = getattr(b, '_meta')
            all_inheritable = cls.inheritable | base_meta._additional_keys
            for (k, v) in base_meta.__dict__.items():
                if k in all_inheritable:
                    meta_options.setdefault(k, v)

            for (k, v) in b.__dict__.items():
                if k in attrs:
                    continue
                if isinstance(v, Column):
                    attrs[k] = deepcopy(v)

        # initialize the new class and set the magic attributes
        cls = super(MetaModel, cls).__new__(cls, name, bases, attrs)
        cls._table = None

        # ModelOptions = meta_options.get('model_options_base', ModelOptions)
        db = meta_options.pop('database', None)
        # if 'database' not in meta_options:
        #     raise Exception("Model {} does not specify a database.".format(name))
        # raise TypeError("Invalid Database Type: {} ({}).".format(db, type(db).__name__))

        cls._meta = ModelOptions(cls, db, **meta_options)

        # replace fields with field descriptors, calling the add_to_class hook
        fields = [(name, attr) for name, attr in cls.__dict__.items() if isinstance(attr, Column)]

        for name, field in fields:
            field.add_to_class(cls, name)

        # create a repr and error class before finalizing
        if hasattr(cls, '__unicode__'):
            setattr(cls, '__repr__', lambda self: '<%s: %r>' % (
                cls.__name__, self.__unicode__()))

        exc_name = '%sDoesNotExist' % cls.__name__
        exc_attrs = {'__module__': cls.__module__}
        exception_class = type(exc_name, (DoesNotExist,), exc_attrs)
        cls.DoesNotExist = exception_class
        # cls._meta.prepared()

        if hasattr(cls, 'validate_model'):
            cls.validate_model()

        if isinstance(db, SpreadDB):
            cls.load(cls._meta.db_table)

        return cls


class DoesNotExist(Exception): pass


class Model(metaclass=MetaModel):
    def __init__(self, row):
        self.row = row + 1  # self._worksheet.row_values(row)
        self.row_values = self._worksheet.row_values(row)

    @classmethod
    def load(cls, spread_id=None, worksheet_id=None):
        db = cls._meta.database
        if isinstance(db, SpreadDB):
            if spread_id is None:
                cls._table = db.latest_first[0]
            elif isinstance(spread_id, str):
                cls._table = db.sheet_dict.get(spread_id)
            elif isinstance(spread_id, int):
                cls._table = db.all_sheets[spread_id]
                # db.sheet_dict.get(cls.__name__, None)

            if isinstance(worksheet_id, str):
                cls._worksheet = cls._table.worksheet(worksheet_id)
            elif isinstance(worksheet_id, int):
                cls._worksheet = cls._table.worksheets()[worksheet_id]
            else:
                cls._worksheet = cls._table.worksheets()[0]

            cls.headings = cls._worksheet.row_values(1)
            cls._last_row_seen = None
        else:
            raise Exception('No Database specified for Model "{}"'.format(cls.__name__))

    def _get_col_nr(self, col_nr):
        return self._worksheet.cell(self.row, col_nr)

    @property
    def valid(self):
        return all(c.validate(self.row_values[c.col_nr]) for c in self._meta.fields.values())

    # if isinstance(db, SpreadDB):
    #     cls._table = db.sheet_dict.get(cls.__name__, None)


    def toDict(self):
        return {k: c.parseValue(self.row_values[c.col_nr]) for k, c in self._meta.fields.items()}

    @classmethod
    def all_rows(cls, start=1):

        for i in range(start, 1 + cls._worksheet.row_count):
            row = cls(i)
            if not row.valid:
                break
            yield row

        cls._last_row_seen = i

    @classmethod
    def new_rows(cls):
        yield from cls.all_rows(start=cls._last_row_seen or 1)


class ColumnDescriptor:
    def __init__(self, col: Column):
        self.col = col

    @property
    def table(self):
        return self.col.model_class._table

    @property
    def sheet(self):
        return self.col.model_class._worksheet

    def __get__(self, instance, instance_type=None):
        if isinstance(instance, Model):
            assert isinstance(self.table, SpreadWrapper), "No valid DB Table found for {}".format(self.col.name)
            return self.col.cell(instance).value
        else:
            return self.col

    def __set__(self, instance, value):
        assert isinstance(instance, Model)
        assert isinstance(self.table, SpreadWrapper), "No valid DB Table found for {}".format(self.col.name)

        self.sheet.update_cell(instance.row, self.col.col_nr + 1, value)


db = SpreadDB('ReleaseTest-fa1e0f684571.json')


class ReleasetestFehlerprotokoll(Model):
    Nr = Column('Nr', required=True)
    Kommuniziert = Column('Status Kommunikation an Entwicklung')
    Thema = Column('Thema')
    Beschreibung = Column('Beschreibung', required=True)
    Testdatum = Column('Testdatum')
    PersonTestcrew = Column('Ansprechpartner Testcrew')
    PersonEntwicklung = Column('Ansprechpartner Entwicklung')
    StatusTestcrew = Column('Status Testcrew')
    StatusEntwicklung = Column('Status Entwicklung')
    Anmerkung = Column('Anmerkungen')

    class Meta:
        database = db
        # table = 'Fehlerprotokoll Releasetest Juli 2016 (Absinthe)'

        # def __init__(self, Nr=0, kommuniziert=False, Beschreibung="", Testdatum=None, PersonTestcrew="",
        #              PersonEntwicklung="", StatusTestcrew="", StatusEntwicklung="", Anmerkung=""):
        #     self.Nr = Nr
        #     self.kommuniziert = kommuniziert
        #     self.Beschreibung = Beschreibung
        #     self.Testdatum = Testdatum

# gc.open_by_url("https://docs.google.com/spreadsheets/d/1JA5nLq1_rJjM1kYx6JaS874uG1Sd0-GEAnONCXiCQ70")



# Alle gmail Acounts vom Team:

# kerstin.thiemann@gmail.com
# christopher.rein@protonmail.ch
# dirk.spoeri@gmail.com
# maria.lohmueller@web.de
# marcel.ruecker@gmail.com
# westphal.matt@gmail.com
# lindagrosskreuz@gmail.com
#
# pivotal-racer-146212@appspot.gserviceaccount.com
