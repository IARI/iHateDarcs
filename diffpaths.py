#! /usr/bin/python3

import argparse_wrapper
import guidata
from os import path
import sys

# from guidata_wrapper import message

mypath = __file__


def exec_pattern(tmpfile):
    return "{} %1 %2 {}".format(mypath, tmpfile)


__all__ = ['mypath', 'exec_pattern']

if __name__ == "__main__":
    parser = argparse_wrapper.parser
    parser.add_argument("old", help="path to old repo", action=argparse_wrapper.readable_dir)
    parser.add_argument("new", help="path to new repo", action=argparse_wrapper.readable_dir)
    parser.add_argument("tmp", help="path to temp file", action=argparse_wrapper.valid_file)

    cli_args = argparse_wrapper.parse()
    old = path.abspath(cli_args.old)
    new = path.abspath(cli_args.new)

    f = open(cli_args.tmp, 'a') # a if there are multiple file paths
    f.writelines([old + '\n', new + '\n'])
    f.close()

    print('new: {}\nold: {}'.format(new, old))

    # sys.stdout.flush()
    # _app = guidata.qapplication()  # not required if a QApplication has already been created
    # print()
    # message('Paths..', 'new: {}\nold: {}'.format(new, old))
