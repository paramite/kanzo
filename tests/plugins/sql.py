# -*- coding: utf-8 -*-

""" Example plugin for tests. This plugin should be able to install
SQL database server.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import uuid


def options_validator(value, options):
    if value not in options:
        raise ValueError('Value %s is not one of possible values %s.'
                         % (value, options))


def password_processor(value, options):
    if not value:
        return uuid.uuid4().hex[:8],
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
     'options': ['postgresql', 'mysql'],
     'validators': [options_validator]},

    {'name': 'sql/admin_user',
     'usage': 'Admin user name',
     'default': 'admin'},

    {'name': 'sql/admin_password',
     'usage': 'Admin user name',
     'processors': [password_processor]},
]


# List of callables (steps) which will be run before manifest application. Step
# callable has to accept following paramters: config
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
INITIALIZATION = []


# List of callables (steps) which will be run after manifest application. Step
# callable has to accept following paramters: config
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
CLEANUP = []


# List of factory functions for manifest registering. Each function have to
# returns dict in format:
# {'path': '/path/to/rendered/manifest',
#  'host': 'hostname_or_IP_where_to_apply',
#  'dependency': ['marker1', 'marker2'], # this manifest won't be applied if
#                                        # manifest having marker1 and marker2
#                                        # did not finished successfully
#  'marker': 'manifest_marker'} # marker is optional, manifests with same
# For creation and rendering manifests there are functions 'render_manifest'
# and 'create_or_update_manifest' in kanzo.core.puppet module. Manifests will
# be registered to the controller in the same order as factory functions
# are defined in FACTORIES list.
FACTORIES = []
