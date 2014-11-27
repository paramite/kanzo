# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import collections
import importlib
import os
import sys

from ..conf import project


# Add all plugin directory paths to sys.path
for path in project.PLUGIN_PATHS:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise ValueError('Given path %s does not exits.' % path)
    sys.path.append(path)


def load_plugin(plugin_name):
    """Loads plugin given by plugin_name."""
    try:
        plugin = importlib.import_module(plugin_name)
    except ImportError:
        raise ValueError('Failed to load plugin %s.' % plugin_name)
    return plugin


_plugins = []
def load_all_plugins():
    """Loads all plugins specified by project's PLUGINS list"""
    if _plugins:
        return _plugins
    for plugin_name in project.PLUGINS:
        plugin = load_plugin(plugin_name)
        if plugin in _plugins:
            raise ValueError('Plugin %s is already loaded.' % plugin_name)
        _plugins.append(plugin)
    return _plugins


def meta_builder(plugins):
    """This function is used for building meta dictionary for Config class.
    Input parameter should contain list of imported plugin modules."""
    meta = collections.OrderedDict()
    for plg in plugins:
        for parameter in plg.CONFIGURATION:
            key = parameter['name']
            # CLI parameter
            parameter['cli'] = key.replace('_', '-').replace('/', '-')
            if key in meta:
                raise ValueError('Duplicated parameter found: %s.' % key)
            meta[key] = parameter
    return meta
