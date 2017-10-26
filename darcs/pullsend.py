from darcs.common import Darcs, DarcsException, Values
from guidata_wrapper import message, Ask
from pexpect_helper import Strategy, Send, EOF
import os


def pull(cwd, repo=None, apply_all=True):
    args = ['pull']
    if apply_all:
        args.append('-a')
    else:
        message('nope', 'not implemented')

    if repo:
        args.append(repo)
        # print('pulling from {}'.format(repo))
    darcs_pull = Darcs(args, None, cwd=cwd)

    if apply_all:
        output = darcs_pull.get_all_output()
        # i, output = darcs_pull.get_all_output_interactive(
        #     errors=[".*No changes\!.*"],
        #     cases=[r'.*\n.*\n'])

        print('pull output:')
        print(output)


def unpull(cwd, *patches):
    for p in patches:
        args = ['unpull', p.MATCH_ARG, p.match_hash]

        darcs_unpull = Darcs(args, None, cwd=cwd)

        Strategy(
            r'Shall I unpull this patch\?',
            Send('y'),
            r'Do you want to [uU]npull these patches\?',
            Send('y'),
            {r'Finished unpulling\.': EOF(''),
             r"Can\'t unpull patch without reverting some unrecorded change\.": DarcsException(
                 'revert first'),
             r"This operation will make unrevert impossible!": (
                 Ask('Continue?'), Send('y'))
             },
        ).execute(darcs_unpull)


def send(cwd, *patches, repo=None, output=None):  # List[Patch]
    if len(patches) != 1:
        message('not supported', 'not supported')
        exit()
    args = ['send', patches[0].MATCH_ARG, patches[0].match_hash]

    if output:
        rp = os.path.realpath(output)
        path, fname = os.path.split(rp)
        if os.path.isdir(rp):
            args += ['-O' + rp]
        elif os.path.isdir(path):
            args += ['-o', rp]
        else:
            print('{} is no valid directory.'.format(path))

    if repo:
        args.append(repo)

    env = Values.darcs_env.copy()
    del env['TERM']
    darcs_send = Darcs(args, None, cwd=cwd, env=env)

    Strategy(
        r'Shall I send this patch\? \(\d+\/\d+\).*',
        Send('y'),
        r'Do you want to [sS]end these patches\?.*',
        Send('y'),
        {
            r'File content did not change. Continue anyway\?.*': Send('y'),
            r'Do you want to [sS]end these patches\?.*': DarcsException(
                'It appears, darcs asks for more than one patch'
                'to be sent. Check the dependencies, and '
                'if wanted. send the patches manually'),
        }
    ).execute(darcs_send)

    i, output = darcs_send.get_all_output_interactive(errors=[], cases=[
        r'Shall I send this patch\? \(\d+\/\d+\).*'])
    print(output)
    darcs_send.send('y')

    i, output = darcs_send.get_all_output_interactive(errors=[], cases=[
        r'Do you want to send these patches\?.*'])
    print(output)
    darcs_send.send('y')

    i, output = darcs_send.get_all_output_interactive(errors=[],
                                                      cases=[
                                                          r'File content did not change. Continue anyway\?.*'])
    print(output)
    darcs_send.send('y')

    output = darcs_send.get_all_output()
    # i, output = darcs_pull.get_all_output_interactive(
    #     errors=[".*No changes\!.*"],
    #     cases=[r'.*\n.*\n'])

    print('send output:')
    print(output)
