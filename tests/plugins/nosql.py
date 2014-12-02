# -*- coding: utf-8 -*-

""" Example plugin for tests. This plugin should be able to install
SQL database server.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import uuid


# List of dicts defining configuration paramaters for plugin
CONFIGURATION = [
    {'name': 'nosql/host',
     'usage': 'NoSQL server hostname / IP address',
     'default': '192.168.6.67'},

    {'name': 'nosql/backend',
     'usage': ('Type of SQL server. Possible values are "postgresql" '
               'for PostreSQL server or "mysql" for MySQL / MariaDB server '
               '(depends on host OS platform).'),
     'default': 'mongodb',
     'options': ['mongodb', 'redis']},

    {'name': 'nosql/admin_user',
     'usage': 'Admin user name',
     'default': 'admin'},

    {'name': 'nosql/admin_password',
     'usage': 'Admin user password',
     'default': ''},
]

MODULES = []
RESOURCES = []
INITIALIZATION = []
PREPARATION = []
DEPLOYMENT = []
CLEANUP = []
