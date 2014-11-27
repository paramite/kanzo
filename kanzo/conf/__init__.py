# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

try:
    # Python2.x
    import ConfigParser as configparser
except ImportError:
    # Python 3.x
    import configparser

import collections
import importlib
import logging
import os
import sys
import textwrap

from . import defaultproject


__all__ = ('Project', 'Config', 'project', 'iter_hosts', 'get_hosts')


LOG = logging.getLogger('kanzo.backend')


def iter_hosts(config):
    """Iterates all host parameters and their values."""
    for key, value in config.items():
        if key.endswith('host'):
            yield key, value
        if key.endswith('hosts') and config.meta(key).get('is_multi', False):
            for i in value.split(project.CONFIG_MULTI_PARAMETER_SEPARATOR):
                yield key, i.strip()


def get_hosts(config):
    """Returns set containing all hosts found in config file."""
    result = set()
    for key, host in iter_hosts(config):
        result.add(host)
    return result


# This class is by 98% stolen from Django (django.conf.Settings), only few
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
        KANZO_PROJECT env is checked. Raises RuntimeError if project module
        is already loaded.
        """
        # load project module
        project = project or os.environ.get('KANZO_PROJECT')
        if project and not self._loaded:
            project_path = os.path.abspath(os.path.dirname(project))
            project_name = os.path.basename(project[:-3])
            sys.path.append(project_path)
            try:
                module = importlib.import_module(project_name)
            except ImportError as e:
                raise ImportError('Failed to import project "%s".\nReason: %s'
                                  % (project, e))
            for key, value in module.__dict__.items():
                if key.isupper():
                    setattr(self, key, value)
            self._loaded = True
            self._project = project_name
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
        self._values = {}

        self._config = configparser.SafeConfigParser()
        if not self._config.read(path):
            raise ValueError('Failed to parse config file %s.' % path)

        self._get_values()
        self._validate_config()

    def save(self):
        """Saves configuration to file."""
        sections = collections.OrderedDict()
        for key in self._meta.keys():
            is_multi = self._meta[key].get('is_multi', False)
            separator = project.CONFIG_MULTI_PARAMETER_SEPARATOR
            value = self[key]
            if is_multi:
                value = separator.join(value)
            section, variable = key.split('/', 1)
            usage = self._meta[key].get('usage')
            options = self._meta[key].get('options')
            if options:
                usage += '\nValid values: %s' % ', '.join(options)
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

    def _validate_value(self, key, value):
        metadata = self._meta[key]
        # split multi value
        is_multi = metadata.get('is_multi', False)
        if is_multi:
            separator = project.CONFIG_MULTI_PARAMETER_SEPARATOR
            value = [i.strip() for i in value.split(separator) if i]
        else:
            value = [value]
        options = metadata.get('options')
        # process value
        new_value = []
        for val in value:
            nv = val
            for fnc in metadata.get('processors', []):
                nv = fnc(nv, key=key, config=self)
                LOG.debug('Parameter processor %s(%s, key=%s) changed '
                          'value.' % (fnc.func_name, val, key))
            new_value.append(nv)
        value = new_value
        # validate value
        for val in value:
            if options and val not in options:
                raise ValueError('Value of parameter %s is not from valid '
                                 'values %s: %s' % (key, options, val))
            for fnc in metadata.get('validators', []):
                try:
                    fnc(val, key=key, config=self)
                except ValueError:
                    LOG.debug('Parameter validator %s(%s, key=%s) failed '
                              'validation.' % (fnc.func_name, val, key))
                    raise
        return value if is_multi else value.pop()

    def _validate_config(self):
        for key in self._meta:
            self._values[key] = self._validate_value(key, self._values[key])

    def __getitem__(self, key):
        return self._values[key]

    def _get_values(self):
        for key in self._meta:
            section, variable = key.split('/', 1)
            try:
                value = self._config.get(section, variable)
            except (configparser.NoOptionError, configparser.NoSectionError):
                value = self._meta[key].get('default', '')
            self._values[key] = value

    def __setitem__(self, key, value):
        try:
            metadata = self._meta[key]
        except KeyError:
            raise KeyError('Given key %s does not exist in metadata '
                           'dictionary.' % key)
        # process and validate new value
        self._values[key] = self._validate_value(key, value)

    def __contains__(self, item):
        return item in self._meta

    def __iter__(self):
        return iter(self._meta.keys())

    def keys(self):
        return self._meta.keys()

    def values(self):
        return self._values.values()

    def items(self):
        return self._values.items()

    def meta(self, key):
        """Returns metadata for given parameter."""
        return self._meta[key]

    def get_validated(self, key):
        return self._validate_value(key, self._values[key])


project = Project()
