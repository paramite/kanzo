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

from ..conf import project
from .strings import mask_string


OUTFMT = '---- %s ----'
logger = logging.getLogger('kanzo.backend')


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
        logger.info('\n'.join(log_msg))

    if proc.returncode and can_fail:
        raise RuntimeError('Failed to execute command: %s' % masked)
    return proc.returncode, out, err


class IgnorePolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, *args, **kwargs):
        return

# XXX: Paramiko is not Python3 compliant yet, but it is WIP
class RemoteShell(object):
    _connections = {}

    username = project.DEFAULT_SSH_USER
    sshkey = project.DEFAULT_SSH_PRIVATE_KEY
    port = project.DEFAULT_SSH_PORT

    def __init__(self, host):
        self.host = host
        if host in self._connections:
            self._client = self._connections[host]
        else:
            self.reconnect()

    def _get_key(self, key_type):
        if key_type == 'private' and self.sshkey.endswith('.pub'):
            path = self.sshkey[:-4]
        elif key_type == 'public' and not self.sshkey.endswith('.pub'):
            path = '%s.pub' % self.sshkey
        else:
            path = self.sshkey
        return os.path.abspath(os.path.expanduser(path))

    def _register(self):
        if self.host in self._connections:
            # ssh-key should be in place on host already, so do nothing
            logger.debug('Skipping ssh-key register process for host %s.'
                         % self.host)
            return
        if not self.sshkey:
            raise ValueError('Attribute sshkey has to be set to connect '
                             'to host %s.' % self.host)
        with open(self._get_key('public')) as kfile:
            data = kfile.read().strip()
        # register ssh-key to host
        script = ['mkdir -p ~/.ssh',
                  'chmod 500 ~/.ssh',
                  'grep "%(data)s" ~/.ssh/authorized_keys > '
                        '/dev/null 2>&1 || '
                        'echo "%(data)s" >> ~/.ssh/authorized_keys' % locals(),
                  'chmod 400 ~/.ssh/authorized_keys',
                  'restorecon -r ~/.ssh']
        self.run_script(script, description='ssh-key register')

    def reconnect(self):
        """Establish connection to host."""
        self._register()

        # create connection to host
        clt = paramiko.SSHClient()
        clt.set_missing_host_key_policy(IgnorePolicy())
        clt.set_log_channel('kanzo.backend')
        try:
            clt.connect(self.host, port=self.port, username=self.username,
                        key_filename=self._get_key('private'))
        except paramiko.SSHException as ex:
            raise RuntimeError('Failed to (re)connect to host %s' % self.host)
        self._connections[self.host] = self._client = clt
        # XXX: following should not be required, so commenting for now
        #clt.get_transport().set_keepalive(10)

    def _process_output(self, otype, channel, mlist, rlist, log=True):
        log_msg = []
        output = []
        if log:
            log_msg.append(OUTFMT % otype)
        for line in channel:
            output.append(line)
            if log:
                log_msg.append(mask_string(line, mlist, rlist))
        return '\n'.join(output), '\n'.join(log_msg)

    def execute(self, cmd, can_fail=True, mask_list=None, log=True):
        """Executes given command on remote host. Raises RuntimeError if
        command failed and if can_fail is True. Logging executed command,
        content of stdout and content of stderr if log is True. Parameter
        mask_list should contain words which is supposed to be masked
        in log messages. Returns (return code, content of stdout, content
        of stderr).
        """
        mask_list = mask_list or []
        repl_list = [("'", "'\\''")]
        masked = mask_string(cmd, mask_list, repl_list)
        log_msg = '[%s] Executing command: %s\n'  % (self.host, masked)

        try:
            chin, chout, cherr = self._client.exec_command(cmd)
        except paramiko.SSHException:
            # in case any error reconnect and try again
            self.reconnect()
            try:
                chin, chout, cherr = self._client.exec_command(cmd)
            except paramiko.SSHException as ex:
                raise RuntimeError('Failed to run following command '
                                   'on host %s: %s' % (self.host, masked))

        stdout, solog = self._process_output('stdout', chout,
                                             mask_list, repl_list)
        stderr, selog = self._process_output('stderr', cherr,
                                             mask_list, repl_list)
        if log:
            log_msg += '%s\n%s' % (solog, selog)
            logger.info(log_msg)

        rc = chout.channel.recv_exit_status()
        if rc and can_fail:
            raise RuntimeError('Failed to run following command on host %s: %s'
                               % (self.host, masked))
        return rc, stdout, stderr

    def run_script(self, script, can_fail=True, mask_list=None,
                   log=True, description=None):
        """Runs given script on remote host. Script should be list where each
        item represents one command. Raises RuntimeError if command failed
        and if can_fail is True. Logging executed command, content of stdout
        and content of stderr if log is True. Parameter mask_list should
        contain words which is supposed to be masked in log messages.
        Returns (return code, content of stdout, content of stderr).
        """
        mask_list = mask_list or []
        repl_list = [("'", "'\\''")]
        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                      '-o', 'UserKnownHostsFile=/dev/null',
                      '-p', str(self.port),
                      '-i', self._get_key('private'),
                      '%s@%s' % (self.username, self.host),
                      'bash -x']
        _script = ['function script_trap(){ exit $? ; }',
                   'trap script_trap ERR']
        _script.extend(script)

        description = description and ' "%s" ' % description or ' '
        log_msg = '[%s] Executing%sscript.\n'  % (self.host, description)
        proc = subprocess.Popen(cmd, close_fds=True, shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate('\n'.join(_script))

        if log:
            log_msg += '%s\n%s' % (mask_string(out, mask_list, repl_list),
                                   mask_string(err, mask_list, repl_list))
            logger.info(log_msg)

        if proc.returncode and can_fail:
            raise RuntimeError('Failed to execute%sscript on host '
                               '%s.' % (description, self.host))
        return proc.returncode, out, err

    def close(self):
        self._client.close()
