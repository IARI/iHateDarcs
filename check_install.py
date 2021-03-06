#! /usr/bin/python3

import os, sys
from subprocess import check_output

S_IXUSR = 0o0100  # execute by owner
S_IXGRP = 0o0010  # execute by group
S_IXOTH = 0o0001  # execute by others


def which(filename):
    '''This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None.'''

    # Special case where filename contains an explicit path.
    if os.path.dirname(filename) != '' and is_executable_file(filename):
        return filename
    if 'PATH' not in os.environ or os.environ['PATH'] == '':
        p = os.defpath
    else:
        p = os.environ['PATH']
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        ff = os.path.join(path, filename)
        if is_executable_file(ff):
            return ff
    return None


def is_executable_file(path):
    """Checks that path is an executable regular file, or a symlink towards one.

    This is roughly ``os.path isfile(path) and os.access(path, os.X_OK)``.
    """
    # follow symlinks,
    fpath = os.path.realpath(path)

    if not os.path.isfile(fpath):
        # non-files (directories, fifo, etc.)
        return False

    mode = os.stat(fpath).st_mode

    if (sys.platform.startswith('sunos')
        and os.getuid() == 0):
        # When root on Solaris, os.X_OK is True for *all* files, irregardless
        # of their executability -- instead, any permission bit of any user,
        # group, or other is fine enough.
        #
        # (This may be true for other "Unix98" OS's such as HP-UX and AIX)
        return bool(mode & (S_IXUSR | S_IXGRP | S_IXOTH))

    return os.access(fpath, os.X_OK)


REQUIRED_PROGRAMS = [
    "diff",
    "patch",
    "stack",
    "meld",
    "darcs",
]

REQUIRED_PYTHON_MODULES = [
    ""
]

# _app = guidata.qapplication()  # not required if a QApplication has already been created

for prog in REQUIRED_PROGRAMS:
    path = which(prog)
    if not path:
        sys.exit('Could not find {}!'.format(prog))
    else:
        ver = check_output([prog, '--version']).decode('utf-8')
        print('found {}:\n{}'.format(prog, ver.split('\n')[0]))
