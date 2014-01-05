# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future import standard_library
from future.builtins import *

import base64
import logging
import os
import paramiko
import pipes
import re
import subprocess
import types

from .strings import mask_string


OUTFMT = '---- %s ----'


def execute(cmd, workdir=None, can_fail=True, mask_list=None,
            use_shell=False, log=True):
    """
    Runs shell command cmd. If can_fail is set to False RuntimeError is raised
    if command returned non-zero return code. Otherwise returns return code
    and content of stdout.
    """
    mask_list = mask_list or []
    repl_list = [("'", "'\\''")]

    if not isinstance(cmd, types.StringType):
        masked = ' '.join((pipes.quote(i) for i in cmd))
    else:
        masked = cmd
    masked = mask_string(masked, mask_list, repl_list)
    log_msg = ['Executing command: %s' % masked]

    proc = subprocess.Popen(cmd, cwd=workdir, shell=use_shell, close_fds=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if log:
        log_msg.extend([OUTFMT % 'stdout',
                        mask_string(out, mask_list, repl_list),
                        OUTFMT % 'stderr',
                        mask_string(err, mask_list, repl_list)])

        logger = logging.getLogger('voodoo.backend')
        logger.info('\n'.join(log_msg))

    if proc.returncode and can_fail:
        raise RuntimeError('Failed to execute command: %s' % masked)
    return proc.returncode, out, err


class IgnorePolicy(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, *args, **kwargs):
            return

#TODO: Paramiko is not Python3 compliant, refactor with popen
class RemoteShell(object):
    _connections = {}

    username = 'root'
    sshkey = None
    port = 22

    def __init__(self, host):
        self.host = host
        if host in self._connections:
            self.client = self._connections[host]
        else:
            self.reconnect()

    def reconnect(self):
        """Establish connection to host."""

        if not self.sshkey:
            raise ValueError('Attribute sshkey has to be set to connect '
                             'to host %s.' % host)
        if self.host in self._connections:
            self.close()
        priv_key = (self.sshkey.endswith('.pub') and self.sshkey[:-4]
                    or self.sshkey)
        pub_key = (self.sshkey.endswith('.pub') and self.sshkey
                   or '%s.pub' % self.sshkey)
        with open(pub_key) as kfile:
            data = kfile.read().strip()
        # register ssh-key to host
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                      '-o', 'UserKnownHostsFile=/dev/null',
                      '%s@%s' % (self.username, host),
                      'bash -x']
        script = ['function t(){ exit $? ; }',
                  'trap t ERR',
                  'mkdir -p ~/.ssh',
                  'chmod 500 ~/.ssh',
                  'grep "%(data)s" ~/.ssh/authorized_keys > '
                        '/dev/null 2>&1 || '
                        'echo %(data)s >> ~/.ssh/authorized_keys' % locals(),
                  'chmod 400 ~/.ssh/authorized_keys',
                  'restorecon -r ~/.ssh']
        proc = subprocess.Popen(cmd, close_fds=True, shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate('\n'.join(script))
        if proc.returncode:
            raise ValueError('Failed to copy ssh-key to host %s.' % self.host)

        # create connection to host
        clt = paramiko.SSHClient()
        clt.set_missing_host_key_policy(IgnorePolicy())
        clt.connect(host, port=self.port, username=self.username,
                       key_filename=priv_key)
        self._connections[host] = self.client = clt

    def execute(self, cmd, can_fail=True, mask_list=None, log=True):
        """Executes given command on remote host. Raises RuntimeError if
        command failed and if can_fail is True. Logging executed command,
        content of stdout and content of stderr if log is True. Parameter
        mask_list should contain words which is supposed to be masked
        in log messages. Returns (return code, content of stdout, content
        of stderr).
        """
        def process_output(otype, channel, mlist, rlist):
            logmsg = []
            output = []
            if log:
                logmsg.append(OUTFMT % otype)
            for line in channel:
                output.append(line)
                if log:
                    logmsg.append(mask_string(line, mlist, rlist))
            return output, logmsg

        mask_list = mask_list or []
        repl_list = [("'", "'\\''")]
        masked = mask_string(cmd, mask_list, repl_list)
        log_msg = ['[%s] Executing command: %s'  % (self.host, masked)]

        chin, chout, cherr = self.client.exec_command(cmd)
        stdout, solog = process_output('stdout', chout, mask_list, repl_list)
        stderr, selog = process_output('stderr', cherr, mask_list, repl_list)

        if log:
            log_msg.extend(solog)
            log_msg.extend(selog)
            logger = logging.getLogger('voodoo.backend')
            logger.info('\n'.join(log_msg))

        rc = chout.channel.recv_exit_status()
        if rc and can_fail:
            raise RuntimeError('Failed to run following command on host %s: %s'
                               % (self.host, masked))
        return rc, '\n'.join(stdout), '\n'.join(stderr)

    def close(self):
        self.client.close()
