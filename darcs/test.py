from darcs.common import Darcs, Values
from pexpect_helper import Strategy, spawn
from config import Config
from os import path


def test(cwd):
    args = ['test']

    if Config.TEST_COMMAND:
        darcs_test = spawn(path.join(cwd, Config.TEST_COMMAND), Config.TEST_COMMAND_ARGS, cwd=cwd,
                           encoding='iso-8859-1', env=Values.darcs_env, timeout=None)
    else:
        darcs_test = Darcs(args, None, cwd=cwd, encoding='iso-8859-1', timeout=None)

    Strategy().execute(darcs_test)
