# -*- coding: utf-8 -*-

""" Example plugin for tests. This plugin should be able to install
SQL database server.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

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

# List of paths to Puppet modules which are required
MODULES = []

# List of paths to Puppet resources
RESOURCES = []

# List of callables (steps) which will run at first even before Puppet
# installation. Step callable has to accept following parameters:
# host - hostname or IP of currently initializing host
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# messages - list of messages which will be printed to stdout if installations
#            succeeds
INITIALIZATION = []

# List of callables (steps) which will run right before Puppet is run,
# which means after Puppet installation and initialization. Step callable has
# to accept following parameters:
# host - hostname or IP of currently initializing host
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# info - dict containing drone information
# messages - list of messages which will be printed to stdout if installations
#            succeeds
PREPARATION = []

# List of callables (steps) which will run after Puppet is finished with hosts
# configuration. Step callable has to accept following parameters:
# host - hostname or IP of currently initializing host
# config - kanzo.conf.Config object containing loaded configuration
#          from config file
# info - dict containing drone information
# messages - list of messages which will be printed to stdout if installations
#            succeeds
CLEANUP = []
