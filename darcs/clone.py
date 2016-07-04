from darcs.common import Darcs
from guidata_wrapper import message
from subprocess import call
import os, re
import shutil
from threading import Thread, Event
from tempfile import mkdtemp


class RepoMirrorThread(Thread):
    def __init__(self, cwd, other):
        Thread.__init__(self)
        # super().__init__(self)
        self.cwd = cwd
        self.target = other

    @staticmethod
    def deletePristine(pristineDir):
        if not os.path.isdir(pristineDir):
            print("pristine copy didn't exist ({})".format(pristineDir))
            return

        shutil.rmtree(pristineDir)
        print('pristine copy deleted ({})'.format(pristineDir))

    @staticmethod
    def clone(cwd, pristineDir):
        darcs_clone = Darcs(['clone', cwd, pristineDir, '--set-scripts-executable'])

        darcs_clone.wait()
        print('cloned pristine.')


class Clone(RepoMirrorThread):
    def __init__(self, cwd, other, delete=True):
        super().__init__(cwd, other)
        self.delete = delete

    def run(self):
        if self.delete:
            self.deletePristine(self.target)

        self.clone(self.cwd, self.target)


class CopyFiles(RepoMirrorThread):
    def __init__(self, cwd, other, paths=()):
        super().__init__(cwd, other)
        self.paths = paths

    def run(self):
        print('copying {} files...'.format(len(self.paths)))
        for p in self.paths:
            source = os.path.join(self.cwd, p)
            destin = os.path.join(self.target, p)
            shutil.copyfile(source, destin)
            print('copied {} from {} to {}'.format(p, self.cwd, self.target))


class CopyDir(RepoMirrorThread):
    def __init__(self, cwd, target):
        super().__init__(cwd, target)

    def run(self):
        self.deletePristine(self.target)
        print('copying dir {} to {}...'.format(self.cwd, self.target))
        shutil.copytree(self.cwd, self.target)


class TempBackup(CopyDir):
    def __init__(self, cwd, prefix='backup_', timeout=5):
        temp = mkdtemp(prefix=prefix)
        super().__init__(cwd, temp)
        self.suspend = Event()
        self.progress = Event()
        self.progress.clear()
        self.suspend.set()
        self.timeout = timeout

    def resume(self):
        self.suspend.set()

    def join(self, timeout=None):
        self.resume()
        super().join(timeout)

    def wait(self):
        while not self.progress.wait(self.timeout):
            print('waiting for backup to continue..')
        self.progress.clear()

    def run(self):
        super().run()
        self.progress.set()
        self.suspend.clear()
        while not self.suspend.wait(self.timeout):
            print('waiting for ok to delete tempbakup')

        shutil.rmtree(self.target)
        print('deleted {}'.format(self.target))
