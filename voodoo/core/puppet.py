# -*- coding: utf-8 -*-

from voodoo.conf import project


class ManifestTemplate(object):

    def __init__(self, path, config):
        self.path = path
        self.config = config

    def render(self, destination, context=None):
        """Renders template to manifest file given by destination parameter. Values"""
        context = context or {}
        context.update(self.config)
        template = open(self.path)
        with open(destination, 'w') as manifest:
            for line in template:
                formated = line % context
                manifest.writeline('%s\n' % formated)
