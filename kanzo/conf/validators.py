# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import re
import socket
import logging


__all__ = ('validate_not_empty', 'validate_integer', 'validate_float',
           'validate_regexp', 'validate_options', 'validate_ip',
           'validate_port', 'validate_hostname', 'validate_file')


def validate_not_empty(value, key=None, config=None):
    """Raises ValueError if given value is empty."""
    if not value:
        raise ValueError('Empty value is not allowed')


def validate_integer(value, key=None, config=None):
    """Raises ValueError if given value is not an integer."""
    if not value:
        return

    try:
        int(value)
    except ValueError:
        raise ValueError('Given value is not an integer: %s' % value)


def validate_float(value, key=None, config=None):
    """Raises ValueError if given value is not a float."""
    if not value:
        return

    try:
        float(value)
    except ValueError:
        raise ValueError('Given value is not a float: %s' % value)


def validate_regexp(value, key=None, config=None):
    """Raises ValueError if given value doesn't match at least one of regular
    expressions given in options.
    """
    if not value:
        return

    for regex in config[key]['regexps']:
        if re.search(regex, value):
            break
    else:
        raise ValueError('Given value does not match required regular '
                         'expression(s): %s' % value)


def validate_ip(value, key=None, config=None):
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
        raise ValueError('Given value is not in IP address format: %s' % value)


def validate_port(value, key=None, config=None):
    """Raises Value if given value is not a decimal number
    in range (0, 65535).
    """
    if not value:
        return

    try:
        port = int(value)
    except ValueError:
        raise ValueError('Given value is not valid port: %s' % value)
    if not (port >= 0 and port < 65535):
        raise ValueError('Given value is not in valid port range: %s' % value)


_hosts = set()
def validate_hostname(value, key=None, config=None):
    """Raises ValueError if given value is not valid hostname."""
    if not value:
        return
    if value in _hosts:
        return

    try:
        socket.gethostbyname(value)
        _hosts.add(value)
    except socket.error:
        raise ValueError('Given value is not in resolvable hostname: %s'
                         % value)


def validate_file(value, key=None, config=None):
    """Raises ValueError if provided file does not exist."""
    if not value:
        return

    if not os.path.isfile(value):
        raise ValueError('Given file does not exist: %s' % value)
