# -*- coding: utf-8 -*-

""" Example plugin for tests. This plugin should be able to install
SQL database server.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import uuid


def length_validator(value, key, config):
    # All three parameters are mandatory. Value to validate, key in config and
    # config itself. Note that values in given config might not be processed
    # or validated, so use config.get_validated(some_key) if you need to read
    # other config value.
    # Validators has to raise ValueError if given value is invalid.
    if len(value) < 8:
        raise ValueError('Password is too short.')


def password_processor(value, key, config):
    # All three parameters are mandatory. Value to validate, key in config and
    # config itself. Note that values in given config might not be processed
    # or validated, so use config.get_validated(some_key) if you need to read
    # other config value.
    # Processors returns processed value which will be corrected in config.
    if not value:
        return uuid.uuid4().hex[:8]
    return value



# List of dicts defining configuration paramaters for plugin
CONFIGURATION = [
    {'name': 'sql/host',
     'usage': 'SQL server hostname / IP address',
     'default': '127.0.0.1'},

    {'name': 'sql/backend',
     'usage': ('Type of SQL server. Possible values are "postgresql" '
               'for PostreSQL server or "mysql" for MySQL / MariaDB server '
               '(depends on host OS platform).'),
     'default': 'mysql',
     'options': ['postgresql', 'mysql']},

    {'name': 'sql/admin_user',
     'usage': 'Admin user name',
     'default': 'admin'},

    {'name': 'sql/admin_password',
     'usage': 'Admin user name',
     'processors': [password_processor],
     'validators': [length_validator]},
]

# List of paths to Puppet modules which are required specificaly by manifests
# used in this plugin. For example puppetlabs-mysql module, which will be
# copied only to host where MySQL is installed
MODULES = []

# List of paths to Puppet resources which are required specificaly by manifests
# used in this plugin.
RESOURCES = []

# List of tuples containing decsription and callable (steps) which will run
# before manifest application. Step callable has to accept following
# parameters:
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# drones_info - dict containing usefult information about each host
# messages - list of messages which will be printed to stdout if installations
#            succeeds
INITIALIZATION = []


# List of tuples containing decsription and callable (steps) which will run
# before manifest application. Step callable has to accept following
# parameters:
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# drones_info - dict containing usefult information about each host
# messages - list of messages which will be printed to stdout if installations
#            succeeds
CLEANUP = []


# List of factory functions for manifest registering. Factory function has to
# accept following parameters:
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# drones_info - dict containing usefult information about each host
# messages - list of messages which will be printed to stdout if installations
#            succeeds
# Factory function has to return either None or dict in format:
# {'description': 'Manifest description',
#  'path': '/path/to/rendered/manifest',
#  'host': 'hostname_or_IP_where_to_apply',
#  'dependency': ['marker1', 'marker2'], # this manifest won't be applied
#                                        # before manifests marked as marker1
#                                        # and marker2, optional
#  'marker': 'manifest_marker'} # optional
# For creation and rendering manifests there are functions 'render_manifest'
# and 'create_or_update_manifest' in kanzo.core.puppet module. Manifests will
# be registered to the controller in the same order as factory functions
# are defined in FACTORIES list.
FACTORIES = []
