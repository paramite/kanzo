# -*- coding: utf-8 -*-


import configparser
import collections
import importlib
import logging
import os
import sys
import textwrap

from . import defaultproject


LOG = logging.getLogger('kanzo.backend')


# This class is by 98% stolen from Django (django.conf.Settings), only few
# things are changed and lazy objects are not used
class Project(object):
    """Class for defining Kanzo projects. Project in Kanzo is a Python module
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
        if os.path.exists(path) and not self._config.read(path):
            raise ValueError('Failed to parse config file %s.' % path)

        self._get_values()
        self._validate_config()

    def _iter_conf(self):
        for key in sorted(self._meta.keys()):
            is_multi = self._meta[key].get('is_multi', False)
            separator = project.CONFIG_MULTI_PARAMETER_SEPARATOR
            value = self[key]
            if is_multi:
                value = separator.join(value)
            section, variable = key.split('/', 1)
            usage = self._meta[key].get('usage')
            options = self._meta[key].get('options')
            default = self._meta[key].get('default', '')
            if options:
                usage += '\nValid values: %s' % ', '.join([str(i) for i in options])
            yield section, variable, value, default, usage

    def save(self):
        """Saves configuration to file."""
        with open(self._path, 'w') as confile:
            last_section = None
            for section, variable, value, default, usage in self._iter_conf():
                if section != last_section:
                    confile.write('\n[{section}]\n'.format(**locals()))
                    last_section = section
                usage = textwrap.fill(
                    usage or '',
                    initial_indent='# ',
                    subsequent_indent='# ',
                    break_long_words=False
                )
                fmt = '\n{usage}\n' if usage else ''
                fmt += (
                    '{variable}={value}\n' if value and value != default else
                    '#{variable}={default}\n'
                )
                confile.write(fmt.format(**locals()))

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
                          'value.' % (fnc.__name__, val, key))
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
                              'validation.' % (fnc.__name__, val, key))
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
                value = self._meta[key].get('default', None)
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
        for key in self:
            yield self[key]

    def items(self):
        for key in self:
            yield key, self[key]

    def meta(self, key):
        """Returns metadata for given parameter."""
        return self._meta[key]

    def get_validated(self, key):
        return self._validate_value(key, self._values[key])


project = Project()
