from darcs.common import Darcs, Hunk
from collections import OrderedDict
from pexpect_helper import Strategy, SendLine, EOF


def whatsnew(cwd, file):
    darcs_what = Darcs(['whatsnew', '-l', '--no-summary'], file, cwd=cwd)

    output = darcs_what.get_all_output()

    hunks, addfiles = Hunk.parse(output)

    filechanges = OrderedDict()

    for h in hunks:
        filechanges.setdefault(h.file, []).append(h)

    return filechanges, addfiles


def revert(cwd, files):
    darcs_revert = Darcs(['revert', '-a'], files, cwd=cwd)
    Strategy({'Finished reverting.': EOF('reverted.'),
              'There are no changes to revert!': EOF('nothing to revert.')}).execute(darcs_revert)


def annotate(cwd, file):
    darcs_annotate = Darcs(['annotate'], file, cwd=cwd)

    return darcs_annotate.get_all_output()
