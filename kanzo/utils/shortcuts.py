# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import grp
import os
import pwd


def get_current_user():
    """Returns uid and gid of currently logged in user."""
    try:
        user = pwd.getpwnam(os.getlogin())
        uid, gid = user.pw_uid, user.pw_gid
    except OSError:
        # in case program is run by a script
        uid, gid = os.getuid(), os.getgid()
    return uid, gid


def get_current_username():
    """Returns username and groupname of currently logged in user."""
    uid, gid = get_current_user()
    user = pwd.getpwuid(uid).pw_name
    group = grp.getgrgid(gid).gr_name
    return user, group
