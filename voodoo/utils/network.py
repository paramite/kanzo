# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import re
import socket

from .shell import ScriptRunner


def get_localhost_ip(host):
    """
    Returns IP address of localhost. Raises NetworkError if discovery failed.
    """
    # find nameservers
    ns_regex = re.compile('nameserver\s*(?P<ns_ip>[\d\.\:]+)')

    script = ScriptRunner(host)
    script.append('cat /etc/resolv.conf | grep nameserver')

    try:
        rc, resolv = script.execute('cat /etc/resolv.conf | grep nameserver',
                                    can_fail=False, use_shell=True, log=False)
    except ScriptRunner.ScriptRuntimeError as ex:
        raise KeyError(str(ex))

    nsrvs = []
    for line in resolv.split('\n'):
        match = ns_regex.match(line.strip())
        if match:
            nsrvs.append(match.group('ns_ip'))

    # try to connect to nameservers and return own IP address
    nsrvs.append('8.8.8.8')  # default to google dns
    for i in nsrvs:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((i, 0))
            loc_ip = s.getsockname()[0]
        except socket.error:
            continue
        else:
            return loc_ip
    raise KeyError('Local IP address discovery failed. Please set '
                       'nameserver correctly.')


def get_device_from_ip(host, ip):
    """
    Returns device naeme
    """
    script = ScriptRunner(host)
    script.append("DEVICE=($(ip -o address show to %s | cut -f 2 -d ' '))"
                  % ip)
    # Ensure that the IP is only assigned to one interface
    script.append("if [ ! -z ${DISPLAY[1]} ]; then false; fi")
    # Test device, raises an exception if it doesn't exist
    script.append("ip link show \"$DEVICE\" > /dev/null")
    script.append("echo $DEVICE")
    try:
        rv, stdout = script.execute()
    except ScriptRunner.ScriptRuntimeError as ex:
        raise KeyError(str(ex))
    return stdout.strip()


def host_to_ip(hostname, allow_localhost=False):
    """
    Converts given hostname to IP address. Raises NetworkError
    if conversion failed.
    """
    try:
        ip_list = socket.gethostbyaddr(hostname)[2]
        if allow_localhost:
            return ip_list[0]
        else:
            local_ips = ('127.0.0.1', '::1')
            for ip in ip_list:
                if ip not in local_ips:
                    break
            else:
                raise NameError()
            return ip
    except NameError:
        # given hostname is localhost, return appropriate IP address
        return get_localhost_ip()
    except socket.error:
        raise NetworkError('Unknown hostname %s.' % hostname)
    except Exception, ex:
        raise NetworkError('Unknown error appeared: %s' % repr(ex))
