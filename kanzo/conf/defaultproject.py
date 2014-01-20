# -*- coding: utf-8 -*-

"""Default project settings"""

PROJECT_NAME = 'Kanzo'

# Separator for multiple value parameters
CONFIG_MULTI_PARAMETER_SEPARATOR = ','

# SSH connection settings
DEFAULT_SSH_USER = 'root'
DEFAULT_SSH_PORT = 22
DEFAULT_SSH_PRIVATE_KEY = '~/.ssh/id_rsa'


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
