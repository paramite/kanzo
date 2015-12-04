# -*- coding: utf-8 -*-

HOST_SET = set()


def iter_hosts(config):
    """Iterates all host parameters and their values."""
    for key, value in config.items():
        if key.endswith('host'):
            yield key, value
        if key.endswith('hosts') and config.meta(key).get('is_multi', False):
            for i in value:
                yield key, i.strip()


def get_hosts(config, refresh=False):
    """Returns set containing all hosts found in config file."""
    if HOST_SET and not refresh:
        return HOST_SET
    for key, host in iter_hosts(config):
        HOST_SET.add(host)
    return HOST_SET


def inject_hosts(hosts):
    """Provides 'get_hosts' support for setups with dynamic host discover."""
    HOST_SET.update(set(hosts))
