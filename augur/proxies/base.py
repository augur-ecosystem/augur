from augur.models.db import db as augur_db


def model_required(func):
    def inner(self, *args, **kwargs):
        if not self._model:
            raise ValueError("Model is required for this method to function properly")
        func(*args, **kwargs)

    return inner


def model_to_proxy(model):
    """Converts the given model to its proxy
    
    Arguments:
        model {db.Entity} -- The model to convert.  
        If not a model, the parameter will be returned as is.
    
    Returns:
        [*] -- Returns the proxy object if one was found, otherwise
                it returns the parameter given.
    """
    if not isinstance(model,augur_db.Entity):
        return model
    if hasattr(model,'_proxy_class'):
        proxy_name = model._proxy_class
        module = __import__('proxies')
        class_ = getattr(module, proxy_name)
        return class_(model)
    else:
        return model
                

def models_to_proxies (func):
    """Automatically converts models to proxies when a proxy is available
    
    Arguments:
        func {function} -- The wrapped function
    
    Returns:
        [function] -- The wrapper function
    """
    def inner(*args, **kwargs):
        for a in args:
            a = model_to_proxy(a)

        args = [model_to_proxy(a) for a in args]
        kwargs = {k:model_to_proxy(v) for k,v in kwargs}
            
        return func(*args,**kwargs)
    
    return inner
                
                            
class ProxyBase(object):
    
    def __init__(self, *args, **kwargs):
        self._model = None
        model_type = self._get_model_type()
        if 'model' in kwargs and model_type:
            if isinstance(kwargs['model'], model_type):
                self._model = kwargs['model']
            else:
                raise ValueError("The model given is not of the correct type.  We are expecting a model of type %s" % self._get_model().__name__)
        elif 'model_id' in kwargs and model_type:
            self._model = model_type[kwargs['model_id']]

    def _get_model_type(self):
        """Gets the class representing the model associated with this proxy
        
        Returns:
            [type] -- The model class or None
        """

        if not hasattr(self, 'model_type'):
            self.model_type = None
            if hasattr(self,'_model_class'):
                model_name = self._model_class
                module = __import__('models')
                self.model_type = getattr(module, model_name)
        return self.model_type                

    def pre_model_create(self):
        """Called just before a model is created
        """
        pass
                
    def post_model_create(self, model):
        """Called just after a model is created
        
        Arguments:
            model {db.Entity} -- The model object that was created
        """
        pass

    def create_model(self, *args, **kwargs):
        """Creates an instance of the model initializing it with the given params
        
        Raises:
            ValueError -- If this proxy does not define a model_class property a ValueException will be raised.
        """

        model_type = self._get_model_type()
        if model_type:
            self.pre_model_create()
            self._model = model_type(*args, **kwargs)
            if self._model:
                self.post_model_create(self._model)

            return self._model
        else:
            self.set_error("Unable to create a model because this proxy does not implement the _model_class property")
            return None

    @property
    def model(self):
        return self._model

    @property
    def last_error(self):
        return self.last_error

    def set_error(self, error_string):
        self.last_error = error_string  
