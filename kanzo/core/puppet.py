# -*- coding: utf-8 -*-

import logging
import os
import re

from ..conf import project


logger = logging.getLogger('kanzo.backend')


class ManifestTemplate(object):

    def __init__(self, path, config):
        self.path = path
        self.config = config

    def render(self, destination, context=None):
        """Renders template to Puppet manifest file given by destination
        parameter. Values for template are taken from kanzo.conf.Config class
        and from given context dict."""
        context = context or {}
        context.update(self.config)
        with open(self.path) as template:
            with open(destination, 'w') as manifest:
                for line in template:
                    manifest.writeline(line % context)



class LogChecker(object):
    color = re.compile('\x1b.*?\d\dm')
    errors = re.compile('err:|Syntax error at|^Duplicate definition:|'
                        '^Invalid tag|^No matching value for selector param|'
                        '^Parameter name failed:|Error:|^Invalid parameter|'
                        '^Duplicate declaration:|^Could not find resource|'
                        '^Could not parse for|^/usr/bin/puppet:\d+: .+|'
                        '^\/usr\/bin\/env\: jruby\: No such file or directory|'
                        '.+\(LoadError\)')
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
                logger.debug('Ignoring expected Puppet: %s' % line)
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
