#! /usr/bin/python3

import argparse_wrapper
from guidata_wrapper import message
import guidata
from os import getcwd, path
from darcs.common import DarcsException
from pexpect import TIMEOUT
from darcs.gui import DarcsGui, OperationCancelled
from config import Config

parser = argparse_wrapper.parser
parser.add_argument("--cwd", help="darcs project path", action=argparse_wrapper.readable_dir, default=getcwd())
parser.add_argument("--cmd", help="command type", choices=list(DarcsGui.Commands()))
parser.add_argument("--kivy", help="use kivy gui")
# parser.add_argument("files", help="restrict darcs commands to this file", action=argparse_wrapper.valid_file, nargs='*')
parser.add_argument("files", help="restrict darcs commands to this file", nargs='*')

cli_args = argparse_wrapper.parse()

for f in cli_args.files:
    filepath = path.join(cli_args.cwd, f)
    assert path.isfile(filepath), "{} is not a valid file location".format(filepath)

_app = guidata.qapplication()  # not required if a QApplication has already been created

try:

    if not Config._INITIALIZED:
        if message("first run: config",
                   "Do you want to configure iHateDarcs now?", True):

            from guidata_wrapper import AutoGui


            def hook():
                Config._INITIALIZED = True
                print("config has been initialized.")
                Config.save()


            AutoGui(Config, changed_hook=hook).edit()
            if not Config._INITIALIZED:
                message("no changes", "You may edit the preferences later.")

    if not cli_args.kivy:
        gui = DarcsGui(cli_args)
        gui.run()
    else:
        from main import DarcsApp

        DarcsApp().run()

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
