# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
import os
import re

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


_templates = {}
def create_or_update_manifest(name, path, config, context=None):
    """Helper function to create new or update existing manifest template
    with fragment template. Parameter 'name' is manifest template name,
    parameter 'path' is path to fragment template file, parameter 'config'
    is Config object and parameter 'context' is special context for fragment
    template.
    """
    manifest = _templates.setdefault(name, ManifestTemplate(name, config))
    manifest.add_template(path, context)


_manifest_destination = os.path.join(project.PROJECT_RUN_TEMPDIR, 'manifests')
def render_manifest(name):
    """Helper function to render single manifest template to manifest file.
    Manifest file will be saved to directory given by 'destination'.
    """
    if name not in _templates:
        raise ValueError('Manifest template "%s" does not exist.' % name)
    return _templates[name].render(_manifest_destination)


class ManifestTemplate(object):
    """Objects of this class are used to glue single manifest template
    from small manifest templates. Resulting manifest template can be rendered
    to manifest file afterwards.
    """

    def __init__(self, name, config):
        self.name = name
        self._templates = []
        self._config = config

    def add_template(self, path, context=None):
        """Append manifest template fragment given by path to file and context
        dictionary with which it will be rendered.
        """
        if not os.path.isfile(path):
            raise ValueError('Given manifest template does not exist: %s'
                             % path)
        self._templates.append((path, context))

    def render(self, destination):
        """Renders template to directory given by destination parameter.
        Values for template are taken from config and from given context dict.
        """
        manpath = os.path.join(destination, '%s.pp' % name)
        with open(manpath, 'w') as manifest:
            for path, context in self._templates:
                context = context or {}
                context.update(self._config)
                with open(path) as template:
                    for line in template:
                        print(line % context, file=manifest)
        return manpath


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
