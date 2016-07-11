from darcs.common import Darcs, Patch, Hunk
from pexpect_helper import Strategy, Send, EOF
from guidata_wrapper import message


def amend_patch(cwd, patch: Patch, files=None, apply_all=True, look_for_adds=False):
    args = ['amend', patch.MATCH_ARG, patch.match_hash]
    if look_for_adds:
        args.append('-l')
    else:
        args.append('--dont-look-for-adds')

    if apply_all:
        args.append('-a')
    else:
        # False

        message('nope', 'not implemented')
        # return pickfrom(*mypatchview, title="darcs amend", itemtitle="Patch")
        return

    darcs_amend = Darcs(args, files, cwd=cwd)

    start = {r'\n[^\n]*?amend this patch\?.*': Send('y'),
             'Cancelling amend since no patch was selected.': None,
             'Waiting for lock .*\n': None}

    finished = {r'Finished amending patch.*': EOF(None)}
    finish = {'Proceed?': [Send('y'), finished]}
    finish.update(finished)

    addfinish = finish.copy()

    def add_file_or_finish(x):
        if x in look_for_adds:
            print("{} should be added".format(x))
            return [Send('y'), addfinish]
        else:
            print("{} should NOT be added".format(x))
            return [Send('n'), addfinish]

    addfinish.update({
        Hunk.ADDFILE_PATTERN: add_file_or_finish,
        Hunk.HUNK_PATTERN: [Send('y'), addfinish]
    })

    Strategy(start, addfinish if isinstance(look_for_adds, list) else finish,
             # r'Amending changes in .*\n', r'.*\n',
             # Send('y'),
             ).execute(darcs_amend)


def rename_patch(cwd, patch: Patch, patchname: str):
    args = ['amend', patch.MATCH_ARG, patch.match_hash, '-m', patchname]

    darcs_amend = Darcs(args, None, cwd=cwd)

    start = {r'\n[^\n]*?amend this patch\?.*': Send('y'),
             'Cancelling amend since no patch was selected.': None,
             'Waiting for lock .*\n': None}

    finished = {r'Finished amending patch.*': EOF(None)}
    finish = {'Proceed?': [Send('y'), finished]}
    finish.update(finished)

    done = {r'\n[^\n]*?record this change\?.*': Send('d'),
            }

    Strategy(start, done, finish).execute(darcs_amend)


def record_patch(cwd, patchname, author, file=None, apply_all=True):
    args = ['record', '-l', '--author', author, '--name', patchname]
    if apply_all:
        args.append('-a')
    else:
        message('nope', 'not implemented')
        return

    darcs_record = Darcs(args, file, cwd=cwd)
    r = darcs_record.get_all_output()

    print(r)


def unrecord_patch(cwd, patch: Patch):
    args = ['unrecord', patch.MATCH_ARG, patch.match_hash, '-a']
    darcs_unrecord = Darcs(args, None, cwd=cwd)

    r = darcs_unrecord.get_all_output()

    print(r)
