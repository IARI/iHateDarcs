from darcs.common import Darcs, Hunk
from guidata_wrapper import message, pickfrom
from collections import defaultdict
# from pexpect import spawn, EOF, TIMEOUT
from subprocess import call
import os, re
from tempfile import NamedTemporaryFile
# from darcs.what import whatsnew
from pexpect_helper import Strategy, SendLine, EOF, bash, run
from pexpect import spawn
from diffpaths import exec_pattern


def diffPaths(cwd, files):
    tf = NamedTemporaryFile(delete=False, mode="w+", prefix='darcsDiffPaths')
    tfName = tf.name
    tf.close()
    print('temp file name: {}'.format(tfName))

    # '--no-pause-for-gui'
    darcs_diff = Darcs(['diff', '--diff-command', exec_pattern(tfName), '--pause-for-gui'], files, cwd=cwd)

    darcs_diff.expect('Hit return to move on...')

    with open(tfName) as f:
        yield [l.strip() for l in f.readlines()]

    yield tfName

    os.remove(tfName)

    # old, new = Strategy(SendLine(''), r'new: (.*?)\r?\nold: (.*?)\r?\n').execute(darcs_diff).matches[-2].groups()
    # old, new = Strategy(r'new: (.*?)\r?\nold: (.*?)\r?\n').execute(darcs_diff).matches[-2].groups()

    darcs_diff.sendline()
    darcs_diff.expect(EOF)


def diff(path1, path2, prefix='darcspatch_'):
    tf = NamedTemporaryFile(delete=False, mode="w+", prefix=prefix)
    tfName = tf.name
    diffargs = ['diff', path1, path2, '-ruN']
    print(' '.join(diffargs))
    call(diffargs, stdout=tf)
    # s = spawn('diff', [path1, path2, '-r'], encoding='utf-8')
    # s.expect(EOF)
    tf.close()
    return tfName


def apply(cwd, patch, strip=0, unapply=False):
    if not os.path.isfile(patch):
        raise IOError("File {} does not exist".format(patch))
    if not os.path.getsize(patch) > 0:
        print("Skipping Patch {}: it's empty".format(patch))
        return
    patchcmd = 'patch -p{} -i "{}"'.format(strip, patch)
    if unapply:
        patchcmd += ' -R'
    print("applying patch: " + patchcmd)
    return run(patchcmd, cwd=cwd)


def kompare(diff_str, kompare="kompare"):
    tf = NamedTemporaryFile(delete=False, mode="w+")
    tfName = tf.name
    print('temp file name: {}'.format(tfName))
    tf.write(diff_str)
    tf.close()

    call([kompare, "-o", tfName])

    print('done')

    os.remove(tfName)


def diffStudio(pristineDir, cwd, studioExec="android-studio"):
    call([studioExec, "diff", cwd + os.sep, pristineDir + os.sep])

    print('called')

    message('continue?', 'please confirm to continue')

    print('continued')


def diffMeld(pristineDir, cwd, meld="meld", filechanges=()):
    diffs = [arg for p in filechanges for arg in ('--diff', os.path.join(cwd, p), os.path.join(pristineDir, p))]

    # call([meld, cwd + os.sep, pristineDir + os.sep])
    call([meld] + diffs)


def diffMeldDirs(old, new, meld="meld"):
    call([meld, old, new])
