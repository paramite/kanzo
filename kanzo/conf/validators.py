# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import os
import re
import socket
import logging


__all__ = ('validate_not_empty', 'validate_integer', 'validate_float',
           'validate_regexp', 'validate_options', 'validate_ip',
           'validate_port', 'validate_hostname', 'validate_file')


_logger = logging.getLogger('kanzo.backend')



def validate_not_empty(value, options=None):
    """Raises ValueError if given value is empty."""
    options = options or []
    if not value and value is not False:
        _logger.debug('validate_not_empty(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Empty value is not allowed')


def validate_integer(value, options=None):
    """Raises ValueError if given value is not an integer."""
    if value is None or value == '':
        return

    options = options or []
    try:
        int(value)
    except ValueError:
        _logger.debug('validate_integer(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not an integer: %s' % value)


def validate_float(value, options=None):
    """Raises ValueError if given value is not a float."""
    if value is None or value == '':
        return

    options = options or []
    try:
        float(value)
    except ValueError:
        _logger.debug('validate_float(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not a float: %s' % value)


def validate_regexp(value, options=None):
    """Raises ValueError if given value doesn't match at least one of regular
    expressions given in options.
    """
    if not value:
        return

    options = options or []
    for regex in options:
        if re.search(regex, value):
            break
    else:
        _logger.debug('validate_regexp(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value does not match required regular '
                         'expression(s): %s' % value)


def validate_options(value, options=None):
    """Raises ValueError if given value is not member of options."""
    if not value:
        return

    options = options or []
    if value not in options:
        _logger.debug('validate_options(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not member of allowed values %s: %s'
                         % (options, value))


def validate_ip(value, options=None):
    """Raises ValueError if given value is not in IPv4 or IPv6 address."""
    if not value:
        return

    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, value)
            break
        except socket.error:
            continue
    else:
        _logger.debug('validate_ip(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not in IP address format: %s' % value)


def validate_port(value, options=None):
    """Raises Value if given value is not a decimal number
    in range (0, 65535).
    """
    if not value:
        return

    options = options or []
    validate_integer(value, options)
    port = int(value)
    if not (port >= 0 and port < 65535):
        _logger.debug('validate_port(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not in port range: %s' % value)


_hosts = set()
def validate_hostname(value, options=None):
    """Raises ValueError if given value is not valid hostname."""
    if not value:
        return
    if value in _hosts:
        return

    try:
        socket.gethostbyname(value)
        _hosts.add(value)
    except socket.error:
        _logger.debug('validate_hostname(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given value is not in resolvable hostname: %s'
                         % value)


def validate_file(value, options=None):
    """Raises ValueError if provided file does not exist."""
    if not value:
        return

    options = options or []
    if not os.path.isfile(value):
        _logger.debug('validate_file(%s, options=%s) failed.' %
                      (value, options))
        raise ValueError('Given file does not exist: %s' % value)
