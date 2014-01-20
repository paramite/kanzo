# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import logging
import os
import re

from ..conf import project


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
        template = open(self.path)
        with open(destination, 'w') as manifest:
            for line in template:
                formated = line % context
                manifest.writeline('%s\n' % formated)


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

    def validate(self, path):
        """Check given Puppet log file for errors and raise RuntimeError
        if there is any error.
        """
        logger = logging.getLogger('kanzo.backend')
        with open(path) as logfile:
            for line in logfile:
                # preprocess
                line = line.strip()
                error = self.color.sub('', line)  # remove colors
                if self.error.search(error) is None:
                    continue
                # check ignore list
                skip = False
                for ign in self.ignore:
                    if i.search(line):
                        logger.debug('Ignoring expected error during Puppet '
                                     'run: %s' % error)
                        skip = True
                        break
                if skip:
                    continue
                # check surrogate list
                for regex, surrogate in self.surrogates:
                    match = regex.search(error)
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
                    error = surrogate % args
                raise RuntimeError('Error appeared during Puppet run: %s'
                                   % error)
