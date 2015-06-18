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

# List all possible commands how to install Puppet on hosts
PUPPET_INSTALLATION_COMMANDS = [
    'yum install -y puppet',      # Red Had based distros
    'apt-get install -y puppet',  # Debian based distros
]

# List all possible commands how to install Puppet and mis. dependencies
# on hosts.
PUPPET_DEPENDENCY_COMMANDS = [
    'yum install -y tar',      # Red Had based distros
    'apt-get install -y tar',  # Debian based distros
]

# Command to start Puppet agent which will run single installation phase
PUPPET_APPLY_COMMAND = (
    '('
        'puppet agent --onetime --verbose --no-daemonize --no-splay '
            '--show_diff --no-usecacheonfailure 2>&1 > {log}.running; '
        'mv {log}.running {log}'
    ') > /dev/null 2>&1 < /dev/null &'
)

PUPPET_CONFIG = '''
[main]
basemodulepath={moduledir}
logdir={logdir}
'''

HIERA_CONFIG = '''
---
:backends:
  - yaml
:yaml:
  :datadir: {datadir}
:hierarchy:
  - "%{{::fqdn}}"
  - config
'''

# Configuration files for Puppet
# Content variable host is internal variable.
# All other variables are formated from PUPPET_CONFIGURATION_VALUES dictionary
PUPPET_CONFIGURATION = [
    ('/etc/puppet/puppet.conf', PUPPET_CONFIG),
    ('/etc/puppet/hiera.yaml', HIERA_CONFIG),
]

# Values for Puppet configs. Values can be either static or dynamicaly glued
# from following variables:
# host - current host
# info - dictionary containing discovered info about current host
# config - loaded config values
# tmpdir - temporary directory on current host
PUPPET_CONFIGURATION_VALUES = {
    'datadir': '{tmpdir}/data',
    'moduledir': '{tmpdir}/modules',
    'logdir': '{tmpdir}/log',
}

# List of paths where project plugins are located
PLUGIN_PATHS = ['/usr/share/kanzo/plugins']

# List of plugins which should be loaded
PLUGINS = []

# If SET_LOGGING is True Kanzo will setup logging to given file, otherwise user
# has to setup logging for 'kanzo.backend' logger himself/herself
SET_LOGGING = True
LOG_FILE = '/var/log/kanzo.log'
LOG_LEVEL = 'INFO'
