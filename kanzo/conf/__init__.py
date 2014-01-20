# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import ConfigParser
import importlib
import os
import textwrap

from ..utils.datastructures import OrderedDict
from . import defaultproject


__all__ = ('Project', 'Config', 'project')


# this class is by 98% stolen from Django (django.conf.Settings), only few
# things are changed and lazy objects are not used
class Project(object):
    """Class for defining Voodoo projects. Project in Kanzo is a Python module
    which contains variables (uppercase named) setting framework. Module import
    path can be in evironment variable KANZO_PROJECT or can be passed to
    the constructor. Available project variables can be found in defaultproject
    module.
    """
    def __init__(self, project=None):
        # set default values
        for key, value in defaultproject.__dict__.items():
            if key.isupper():
                setattr(self, key, value)
        self._loaded = False
        self.load(project)

    def load(self, project=None):
        """Loads project module from given path. If path is not given
        VOODO_PROJECT env is checked. Raises RuntimeError if project module
        is already loaded.
        """
        # load project module
        project = project or os.environ.get('KANZO_PROJECT')
        if project and not self._loaded:
            try:
                module = importlib.import_module(project)
            except ImportError as e:
                raise ImportError('Project module "%s" cannot be imported. '
                                  'Please put path to the module to the '
                                  'sys.path first.' % project)
            for key, value in module.__dict__.items():
                if key.isupper():
                    setattr(self, key, value)
            self._loaded = True
            self._project = project
            self.PROJECT = project
        elif self._loaded:
            raise RuntimeError('Project %s is already loaded. Cannot load '
                               'project %s' % (self._project, project))


class Config(object):
    def __init__(self, path, meta):
        """Class used for reading/writing configuration from/to file given by
        attribute 'path'.

        Attribute 'meta' has to be dictionary. Keys of meta have to be
        in format 'section/name'. Values should be in following format:
        {'default': 'default value', 'is_multi': False,
         'processors': [func, func], 'validators': [func, func],
         'usage': 'Description'}
        """
        self._path = path
        self._meta = meta
        self._cache = {}
        self._config = ConfigParser.SafeConfigParser()
        self._config.read(path)

    def save(self):
        """Saves configuration to file."""
        sections = OrderedDict()
        for key in self._meta.keys():
            is_multi = self._meta[key].get('is_multi', False)
            separator = project.CONFIG_MULTI_PARAMETER_SEPARATOR
            value = self[key]
            if is_multi:
                value = separator.join(value)
            section, variable = key.split('/', 1)
            usage = self._meta[key].get('usage')
            sections.setdefault(section, []).append((variable, value, usage))

        fmt = '\n%(usage)s\n%(variable)s=%(value)s\n'
        with open(self._path, 'w') as confile:
            for section, variables in sections.items():
                confile.write('\n[%(section)s]' % locals())
                for variable, value, usage in variables:
                    usage = usage or ''
                    usage = textwrap.fill(usage, initial_indent='# ',
                                          subsequent_indent='# ',
                                          break_long_words=False)
                    confile.write(fmt % locals())

    def _val_n_proc(self, key, value):
        metadata = self._meta[key]
        # split multi value
        is_multi = metadata.get('is_multi', False)
        if is_multi:
            separator = project.CONFIG_MULTI_PARAMETER_SEPARATOR
            value = set([i.strip() for i in value.split(separator) if i])
        else:
            value = set([value])
        # process value
        new_value = set()
        for val in value:
            nv = val
            for fnc in metadata.get('processors', []):
                nv = fnc(nv)
            new_value.add(nv)
        value = new_value
        # validate value
        options = metadata.get('options')
        for val in value:
            for fnc in metadata.get('validators', []):
                fnc(val, options=options)
        return value if is_multi else value.pop()

    def __getitem__(self, key):
        if key in self._cache:
            return self._cache[key]
        # get metadata
        try:
            metadata = self._meta[key]
        except KeyError:
            raise KeyError('Given key %s does not exist in metadata '
                           'dictionary.' % key)
        # get raw value
        section, variable = key.split('/', 1)
        try:
            value = self._config.get(section, variable)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            value = metadata.get('default', '')
        # process and validate raw value
        self._cache[key] = self._val_n_proc(key, value)
        return self._cache[key]

    def __setitem__(self, key, value):
        try:
            metadata = self._meta[key]
        except KeyError:
            raise KeyError('Given key %s does not exist in metadata '
                           'dictionary.' % key)
        # process and validate new value
        self._cache[key] = self._val_n_proc(key, value)

    def __contains__(self, item):
        return item in self._meta

    def __iter__(self):
        return iter(self._meta.keys())

    def keys(self):
        return self._meta.keys()

    def _init_all(self):
        if len(self._meta) != len(self._cache):
            for key in self.keys():
                self[key]

    def values(self):
        self._init_all()
        return self._cache.values()

    def items(self):
        self._init_all()
        return self._cache.items()


project = Project()
