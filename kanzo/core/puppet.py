# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import collections
import logging
import os
import re
import yaml

from ..conf import project, Config


LOG = logging.getLogger('kanzo.backend')


def parse_crf(logstr):
    """Returns certificate request fingerprint from given log."""
    master_regexp = re.compile(
        '"(?P<host>[\w\.\-_]*)"\s*\((?P<method>\w*)\)\s*'
        '(?P<fingerprint>[\w\:]*)'
    )
    agent_regexp = re.compile(
        '\((?P<method>\w*)\)\s*(?P<fingerprint>[\w\:]*)'
    )

    match = master_regexp.search(logstr) or agent_regexp.search(logstr)
    if not match:
        raise ValueError(
            'Did not find fingerprint in given string:\n{0}'.format(logstr)
        )
    return match.groups()


class LogChecker(object):
    color = re.compile('\x1b.*?\d\dm')
    errors = re.compile('|'.join(project.PUPPET_ERRORS))
    ignore = [re.compile(i)
              for i in project.PUPPET_ERROR_IGNORE]
    surrogates = [(re.compile(i[0]), i[1])
                  for i in project.PUPPET_ERROR_SURROGATES]

    def _preproces(self, line):
        return self.color.sub('', line.strip())  # remove colors

    def _check_ignore(self, line):
        skip = False
        for ign in self.ignore:
            if ign.search(line):
                LOG.debug('Ignoring expected Puppet: %s' % line)
                skip = True
                break
        return skip

    def _check_surrogates(self, line):
        for regex, surrogate in self.surrogates:
            match = regex.search(line)
            if match is None:
                continue

            args = {}
            num = 1
            while True:
                try:
                    args['arg%d' % num] = match.group(num)
                    num += 1
                except IndexError:
                    break
            return surrogate % args
        return line

    def validate(self, path):
        """Check given Puppet log file for errors and raise RuntimeError
        if there is any error.
        """
        with open(path) as logfile:
            for line in logfile:
                line = self._preproces(line)
                if self.errors.search(line) is None:
                    continue
                if self._check_ignore(line):
                    continue
                raise RuntimeError(self._check_surrogates(line))


class HieraYAMLLibrary(object):
    """Holds content of Hiera YAML files."""
    def __init__(self, config=None):
        """If given config file content will be exported as config.yaml."""
        self._content = {'config.yaml': dict(config)} if config else {}

    def add(self, filename, key, value):
        self._content.setdefault(filename, {})[key] = value

    def render(self, filename):
        return yaml.dump(
            self._content[filename], explicit_start=True,
            default_flow_style=False
        )

    def clean(self):
        self._content = {}


_hieralib = HieraYAMLLibrary()
def update_hiera_file(filename, variable, value):
    """This function should be used to dynamicaly insert configuration
    in Hiera YAML files.
    """
    _hieralib.add(filename, variable, value)

def render_hiera_files():
    for filename in _hieralib._content.keys():
        yield filename, _hieralib.render(filename)

def clean_hiera_files():
    _hieralib.clean()
