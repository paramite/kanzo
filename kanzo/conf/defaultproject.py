# -*- coding: utf-8 -*-

"""Default project settings"""

import datetime
import os


_timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

PROJECT_NAME = 'Kanzo'
PROJECT_TEMPDIR = '/var/tmp/kanzo'
PROJECT_RUN_TEMPDIR = os.path.join(PROJECT_TEMPDIR, _timestamp)

# Separator for multiple value parameters
CONFIG_MULTI_PARAMETER_SEPARATOR = ','

# SSH connection settings
DEFAULT_SSH_USER = 'root'
DEFAULT_SSH_PORT = 22
DEFAULT_SSH_PRIVATE_KEY = '~/.ssh/id_rsa'

# List of regular exceptions which are used to catch recognised errors from
# Puppet logs
PUPPET_ERRORS = [
    'err:', 'Syntax error at', '^Duplicate definition:', '^Invalid tag',
    '^No matching value for selector param', '^Parameter name failed:',
    'Error:', '^Invalid parameter', '^Duplicate declaration:',
    '^Could not find resource', '^Could not parse for', '^Could not autoload',
    '^/usr/bin/puppet:\d+: .+', '.+\(LoadError\)',
    '^\/usr\/bin\/env\: jruby\: No such file or directory'
]

# List of tuples. First item in tuple is regexp strings to match error,
# second item is message surrogate
# Example:
# PUPPET_ERROR_SURROGATES = [
#     ('Sysctl::Value\[.*\]\/Sysctl\[(?P<arg1>.*)\].*Field \'val\' is required',
#         'Cannot change value of %(arg1)s in /etc/sysctl.conf'),
# ]
PUPPET_ERROR_SURROGATES = []

# List of regexp strings to match errors which should be ignored
PUPPET_ERROR_IGNORE = []

# If Kanzo should try to apply all manifests even if one (or more) failed
# for some reason
PUPPET_FINISH_ON_ERROR = False

# List all possible commands how to install Puppet on hosts. Tar is necessary
# dependency for manifest transfer.
PUPPET_INSTALLATION_COMMANDS = [
    'yum install -y puppet tar && rpm -q puppet',      # Red Had based distros
    'apt-get install -y puppet tar && dpkg -s puppet'  # Debian based distros
]

# List of Puppet modules which are be copied to all hosts where installation
# will happen
PUPPET_DEFAULT_MODULES = []

# List of paths where project plugins are located
PLUGIN_PATHS = ['/usr/share/kanzo/plugins']

# List of plugins which should be loaded
PLUGINS = []
