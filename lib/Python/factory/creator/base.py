from ..param import ConfigParam, ParamError, AnyValue, Iterable, InstanceOf

class Creator(object):
    "Base creator object that handles ensuring the contract of creators parameters is kept and type checking parameters requested"

    def __init__(self, config_def, common_store=None):

        # Ensure the config definition is of the appropriate type
        if type(config_def) is dict:
            self.config_def = config_def
        else:
            raise TypeError("The config definition (config_def) argument passed to %s should be of type dict" % self.__class__.__name__)

        # Create a new common store if non are passed
        if common_store is not None:
            if not isinstance(common_store, dict):
                raise TypeError("The common store passed must be a instance of a dict")
            self.common_store = common_store
        else:
            self.common_store = {}

        self._load_parameters()
        
    def _load_parameters(self):
        "Gather class parameter types and ensure config_def has necessary items"

        # Look through class attributes to find the ones that have values that
        # inherit from ConfigParam to determine which are the parameters defined
        # in subclasses
        self.parameters = {}
        for attr_name in dir(self):
            attr_val = getattr(self, attr_name)
            if isinstance(attr_val, ConfigParam):
                # For required parameters, make sure the value is present either in the config or common store
                if attr_val.required and not attr_name in self.config_def and not attr_name in self.common_store:
                    raise ParamError("A parameter named %s was expected in configuration definition used by creator %s" % (attr_name, self.__class__.__name__))
                self.parameters[attr_name] = attr_val

    def param(self, param_name):
        "Retrieve a parameter from the configuration definition"

        # Creator requested a parameter that was not defined by a ConfigParam attribute
        try:
            param_def = self.parameters[param_name]
        except KeyError:
            raise KeyError("Unregistered parameter %s requested by %s" % (param_name, self.__class__.__name__))

        # Get parameter from configuration definition first, then trying common store and
        # if not required return None without error
        if param_name in self.config_def:
            param_val = self.config_def[param_name]
        elif param_name in self.common_store:
            param_val = self.common_store[param_name]
        elif self.parameters[param_name].required:
            raise KeyError("The parameter name %s requested from config definition by %s was not found and is required" % (param_name, self.__class__.__name__))
        else:
            return None

        try:
            return param_def.evaluate(param_val, self)
        except ParamError as exc:
            raise ParamError("The parameter named %s requested by creator %s fails with error: %s" % (param_name, self.__class__.__name__, exc))

    def create(self):
        raise NotImplementedError("Create must be defined in inheriting Creator classes")

class ParamIterateCreator(Creator):
    "Base class for creators that iterate over their parameters"

    order = Iterable(required=False)

    def __init__(self, config_def, param_order=None, **kwargs):
        super().__init__(config_def, **kwargs)

        if param_order is None:
            if "order" in self.config_def:
                param_order = self.param("order")
            else:
                param_order = self.config_def.keys()

        # Filter out parameter names that should not be processed,
        # such as the creator param
        self.param_names = []
        for param_name in param_order:
            if param_name != "creator":
                self.param_names.append(param_name)

                # Param type not defined so allow any value
                if param_name not in self.parameters:
                    self.parameters[param_name] = AnyValue()

class ParamPassThru(ParamIterateCreator):
    "Evaluates and passes configurations parameter through as the creator result"

    def create(self):

        result = {} 
        for param_name in self.param_names:
            result[param_name] = self.param(param_name)

        return result

class SaveToCommon(ParamPassThru):
    "Evalualtes parameters and saves them into the common store, creator has no return value"

    def create(self):
        param_vals = super().create()

        for param_name in self.param_names:
            self.common_store[param_name] = param_vals[param_name]
        
        return param_vals
