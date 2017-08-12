import csv
import datetime
import logging
import yaml


class AugurModelProp(object):
    def __init__(self, key, value, tp='unicode'):
        self.key = key
        self.value = value
        self.type = tp

    def __repr__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other

    def __gt__(self, other):
        return self.value > other

    def __lt__(self, other):
        return self.value < other

    def __add__(self,other):
        return self.value + other

    def __mul__(self, other):
        return self.value * other

    def __div__(self, other):
        return self.value / other

    def __sub__(self, other):
        return self.value - other

    def __str__(self):
        return str(self.value)

    def __unicode__(self):
        return unicode(self.value)

    def __iter__(self):
        return iter(self.value)

    def _set_special_type_handling(self, value):
        """
        If the type is special (not a builtin type) then we can use this method to do special value setting
        :param value: The value given
        :return: Returns True if handled, False otherwise.
        """
        if self.type == datetime.datetime:
            if not value:
                self.value = datetime.datetime.now()
            else:
                self.value = datetime.datetime.strptime(value, "%Y-%m-%d")

            return True
        else:
            return False

    def set(self, value):
        if not isinstance(value, self.type) and value:
            if not self._set_special_type_handling(value):
                self.value = self.type(value)
        else:
            self.value = value


class AugurModel(object):
    """
    Any derived classes can add properties to the model by overriding the "_add_properties" method
     and add properties using the add_prop call.  
     
    Importing data from a CSV can be done using the static method import_from_csv which takes the path to the
    file as well as the derived model to use.  A model will be created for each row and the function `handle_field_import`
    will be called for each field in the csv row.  This is an opportunity to do special handling on value types. If
    no special action taken then the base class will assume that there's a prop with the given name and try to set 
    it - it will also attempt to cast it to the data type associated with the property.
    
    After the import is complete it will call `handle_post_import` which can be used to fill in any calculated
    fields or anything else.
    """

    logger = logging.getLogger("AugurModel")

    def __init__(self):
        self.__dict__['_props'] = dict()
        self._add_properties()

    def __getattr__(self, key):
        if key in self.__dict__['_props']:
            if isinstance(self.__dict__['_props'][key],AugurModelProp):
                return self.__dict__['_props'][key].value
            else:
                return self.__dict__['_props'][key]
        else:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        if key in self.__dict__['_props']:
            prop_ob = self.__dict__['_props'][key]
            prop_ob.set(value)
        else:
            raise AttributeError(key)

    def as_dict(self):
        return {key:v.value for key,v in self.__dict__['_props'].iteritems()}

    def _add_properties(self):
        """
        Override to add properties.
        :return: 
        """
        pass

    def add_prop(self, key, default, typ='unicode'):
        """
        Called to add a single property to the model.  This should be called within the _add_properties method.
        :param key: The name of the key
        :param default: The default value (this will also be used to identify the type of the field)
        :param typ: The type of value this is
        :return: None
        """
        self._props[key] = AugurModelProp(key, default, typ)

    def get_props_as_dict(self):
        return self.__dict__['_props']

    def handle_field_import(self, key, value):
        if key:
            setattr(self, key, value)
        else:
            self.logger.error("Received an empty key within this AugurModel: %s" % self.__class__.__name__)

    def handle_dict_import(self, item):
        """
        Handles import of a dictionary object that is meant to represent a single instance of the model
        :param item: dict: The item being imported
        :return:
        """
        pass

    def handle_post_import(self):
        pass

    @staticmethod
    def import_from_csv(filepath, model_type):

        if "AugurModel" not in map(lambda x: x.__name__, model_type.__bases__):
            raise TypeError("The model type when importing from CSV must be derived from AugurModel")

        models = []
        with open(filepath, 'rU') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                model = model_type()
                for key, value in row.iteritems():
                    model.handle_field_import(key, value)
                model.handle_post_import()
                models.append(model)

        return models

    @staticmethod
    def import_from_yaml(filepath, model_type):

        if "AugurModel" not in map(lambda x: x.__name__, model_type.__bases__):
            raise TypeError("The model type when importing from YAML must be derived from AugurModel")

        models = []
        item_list = yaml.load(file(filepath,"r")) or []
        for item in item_list:
            model = model_type()
            models.append(model.handle_dict_import(item))

        return models

    @staticmethod
    def find_model_in_collection(collection, prop, value):
        for r in collection:
            if value == getattr(r, prop):
                return r
        else:
            return None
