# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

from ..utils.datastructures import OrderedDict


class Parameter(object):
    allowed_keys = ('name',         # parameter section/name
                    'is_multi',     # is this multi-value parameter, eg. 'a,b'
                    'secure',       # should value be secured, eg. not printed
                    'default',      # default value
                    'usage',        # description of parameter
                    'prompt',       # string printed when asking for value
                    'processors',   # list of processor callables
                    'validators',   # list of validator callables
                    'options')      # list of valid values

    def __init__(self, **kwargs):
        defaults = {}.fromkeys(self.allowed_keys)
        defaults.update(kwargs or {})

        for key, value in defaults.items():
            if key not in self.allowed_keys:
                raise KeyError('Given attribute %s is not allowed' % key)
            self.__dict__[key] = value


class Group(Parameter):
    allowed_keys = ('name',         # group name
                    'condition',    # group condition callable
                    'match')        # valid condition callable return value

    def __init__(self, parameters=None, **kwargs):
        super(Group, self).__init__(**kwargs)
        self.parameters = OrderedDict()
        for param in parameters or []:
            self.parameters[param['name']] = Parameter(**param)

    def search(self, attr, value):
        """Returns list of parameters which have given attribute of given
        value.
        """
        result = []
        for param in self.parameters.values():
            if getattr(param, attr) == value:
                result.append(param)
        return result

    def can_use(self, config):
        """Returns True if group condition matches required condition value
        or if condition was not specified. Otherwise returns False.
        """
        if self.condition:
            return self.condition(config) == self.match
        return True
