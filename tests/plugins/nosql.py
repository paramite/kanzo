# -*- coding: utf-8 -*-

""" Example plugin for tests. This plugin should be able to install
SQL database server.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import uuid

from kanzo.core.puppet import update_manifest_inline


#------------------- initialization and preparation steps ---------------------#

#------------------------- deployment planning steps --------------------------#
def prerequisite_2(config, info, messages):
    """This steps generates preprequisite manifest for manifest generated
    in step test_planning implemented in sql plugin.
    """
    update_manifest_inline(
        'prerequisite_2',
        "notify { 'prerequisite_2': message => 'running prerequisite_2' }"
    )
    return [
        (config['nosql/host'], 'prerequisite_2', 'prerequisite_2', None)
    ]

#-------------------------------- plugin data ---------------------------------#
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
DEPLOYMENT = [
    prerequisite_2
]
CLEANUP = []
