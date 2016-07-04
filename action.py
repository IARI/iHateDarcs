#! /usr/bin/python3

import argparse_wrapper
import guidata
from guidata_wrapper import message
from os import getcwd, path
from darcs.common import DarcsException
from pexpect import TIMEOUT
from darcs.gui import DarcsGui, OperationCancelled

parser = argparse_wrapper.parser
parser.add_argument("--cwd", help="darcs project path", action=argparse_wrapper.readable_dir, default=getcwd())
parser.add_argument("--cmd", help="command type", choices=list(DarcsGui.Commands()))
# parser.add_argument("files", help="restrict darcs commands to this file", action=argparse_wrapper.valid_file, nargs='*')
parser.add_argument("files", help="restrict darcs commands to this file", nargs='*')

cli_args = argparse_wrapper.parse()

for f in cli_args.files:
    filepath = path.join(cli_args.cwd, f)
    assert path.isfile(filepath), "{} is not a valid file location".format(filepath)

_app = guidata.qapplication()  # not required if a QApplication has already been created

try:

    gui = DarcsGui(cli_args)

    gui.run()

except OperationCancelled:
    exit("operation canceled")
except TIMEOUT:
    message("timed out...", "operation timed out.")
    exit()
except DarcsException as e:
    message("darcs operation canceled", str(e))
    print(e)
    # print(e.output)
    exit()
except Exception as e:
    message("Error", "something went wrong: {}".format(e))
    raise e
