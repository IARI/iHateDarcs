from pexpect import spawn, EOF, TIMEOUT, ExceptionPexpect
# from pexpect.pty_spawn import spawn as ptyspawn
from enum import Enum
from config import Config
# from pexpect_helper import bash
import redmine
from redmine.resources import Issue, IssueStatus
import re
import os
from lazy import lazy


class Prefixes(Enum):
    TRIVIAL = """für Änderungen, die die Semantik des Produkts gar nicht betreffen, wie z.B. Codeformatierungen, Typos,
    Editorkommandos im Header, Änderungen an Hilfsskripten, geänderten Schulungsdaten etc."""
    MINOR = """für minimale Änderungen, die eventuell das vom Nutzer wahrgenommene Aussehen aber aller
    wahrscheinlichkeit nach nicht die Semantik der Anwendung betreffen. Nur für "kleine Änderungen" sowohl in der Größe
    als auch in der Bedeutung (kleine Textänderungen auf den Webseiten, Implementierung von str oder
    repr Funktionen, ...)"""
    BUGFIX = """"für gefixte Bugs, die nicht im Bugtracker waren"""
    FEATURE = """für Features, die nicht im Bugtracker waren"""
    TEST = """für Tests, die nicht im Bugtracker waren"""
    BUG = ("""für Bugreports aus dem Bugtracker""", "BUG #{}")
    FRQ = ("""für implementierte Featurequests aus dem Bugtracker""", "FRQ #{}")
    TESTF = ("""für implementierte Featurequests aus dem Bugtracker""", "TEST #{}")
    AMEND = ("""für Ausbesserungen zu einem bestimmten Bug""", "AMEND #{}")
    ENH = ("""für Enhancments aus dem Bugtracker""", "ENH #{}")
    YOLO = """"Für reine Textänderungen oder Änderungen, die die Schulungsversion betreffen"""
    YOLOF = ("""Für reine Textänderungen aus dem Bugtracker""", "YOLO #{}")

    def __init__(self, desc, txt=None):
        self.desc = desc
        self.realstr = txt

    def description(self):
        return "{}:\n{}".format(self.name, self.desc)

    def Name(self, tracker):
        try:
            return self.realstr.format(tracker)
        except Exception:
            return self.name

    def Match(self, name):
        return re.match(self.Name("(\d+)"), name)

    @classmethod
    def read(cls, name):
        for pref in cls:
            m = pref.Match(name)
            issue = None
            try:
                issue = m.group(1)
            except:
                pass
            if m:
                return pref, int(issue)

        raise Exception("Could not read {} as prefix".format(name))


NEWLINE = r"(\r\n?|\n)"
NONEWLINE = r"[^\r\n]"


def named_match(name, pattern=NONEWLINE + r'*', before=r'', after=NEWLINE):
    return r'{b}(?P<{n}>{p}){a}'.format(n=name, p=pattern, b=before, a=after)


class LazyValues:
    @lazy
    def darcs_env(self):
        darcs_env = dict(os.environ)

        # from subprocess import check_output
        # darcs_env = dict([s.split('=', 1) for s in check_output('printenv').decode().strip().split('\n')])
        # darcs_env = dict([s.split('=', 1) for s in bash('printenv').decode().strip().split('\n')])
        # print(bash("whoami"))

        for c in ["ANDROID_HOME", "TERM"]:
            print("{} in env: {}".format(c, c in darcs_env))

        darcs_env.update({
            # darcs should pipe output to stdout, instead of using a pager like less
            "DARCS_PAGER": "cat",
            "PATH": os.getenv('PATH')
        })

        darcs_env.update(Config.ENVIRONMENT)

        # for v in darcs_env:
        #     print(v)

        return darcs_env

    def default_args(self):
        return dict(timeout=5, env=self.darcs_env)


Values = LazyValues()


class Darcs(spawn):
    def __init__(self, args=[], file=None, timeout=None, maxread=10000,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 ignore_sighup=False, echo=True, preexec_fn=None,
                 encoding='utf-8', codec_errors='replace', dimensions=None):
        print("darcs {}".format(' '.join(args)))

        if env is None:
            env = Values.darcs_env

        darcs_args = args[:]
        if file is not None:
            darcs_args += file

        if timeout is None:
            timeout = Config.TIMEOUT

        super().__init__('darcs', darcs_args, timeout, maxread, searchwindowsize, logfile, cwd, env, ignore_sighup,
                         echo,
                         preexec_fn, encoding, codec_errors, dimensions)

        # print("executing {} ...".format(self.full_cmd))

    @property
    def full_cmd(self):
        return ' '.join(self.args)

    def get_all_output(self, errors=()):
        r = self.expect([EOF, TIMEOUT] + list(errors))
        if r > 1:
            raise DarcsException(self.match.group())
        elif r == 1:
            raise TIMEOUT("{} {}".format(self.before, self.after))
        return str(self.before)

    def get_all_output_interactive(self, errors=(), cases=()):
        r = self.expect(list(errors) + [EOF] + list(cases))
        EOF_INDEX = len(errors)
        if r < EOF_INDEX:
            raise DarcsException(self.match.group())
        elif r == EOF_INDEX:
            rval = self.before
        else:
            rval = self.match.group()
            # case = cases[r - EOF_INDEX]
        return r, rval

    def printstatus(self):
        print('before:')
        print(self.before)
        print('match:')
        print(self.match.group())
        print('after:')
        print(self.after)


class DarcsException(ExceptionPexpect):
    pass


class Patch:
    MATCH_ARG = '--match'
    CHANGES_PATCH_PATTERN = re.compile(''.join(named_match(name, before=before) for name, before in [
        ('hash', r'patch '),
        ('author', r'Author: '),
        ('date', r'Date: '),
        ('title', r'\s+\*\s+'),
    ]), re.M | re.S)

    def __init__(self, hash, author, date, title):
        self.hash = hash
        self.author = author
        self.date = date
        self.title = title

    def __str__(self):
        return "{}\nby {}".format(self.title, self.author)

    @property
    def match_hash(self):
        return 'hash ' + self.hash

    @classmethod
    def parse(cls, string):
        return [cls(**m.groupdict()) for m in cls.CHANGES_PATCH_PATTERN.finditer(string)]

    @property
    def referenced_issues(self):
        refs = re.findall(r"#(\d+)", self.title)
        if not refs:
            return None

        mrm = MyRedmine()
        return [mrm.getIssue(r) for r in refs]

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.title == other.title and self.hash == other.hash


class Hunk:
    HUNK_PATTERN = re.compile(
        r'^hunk ' + ''.join(named_match(name, pattern=pattern, after=after) for name, pattern, after in [
            ('file', r'\S+', ' '),
            ('line', r'\d+', NEWLINE),
            ('removed', r'(^-' + NONEWLINE + '*' + NEWLINE + ')*', ''),
            ('added', r'(^\+' + NONEWLINE + '*' + NEWLINE + ')*', ''),
        ]), re.M | re.S)

    ADDFILE_PATTERN = re.compile(r'^addfile ' + named_match('file', '\S+', after=NEWLINE), re.M | re.S)

    def __init__(self, file, line, removed, added):
        self.file = file
        self.line = line
        if not isinstance(removed, list):
            removed = removed.split('\n-')
        self.removed = removed
        if not isinstance(added, list):
            added = added.split('\n+')
        self.added = added

    def __str__(self):
        return "hunk {} {}{}{}".format(self.file, self.line,
                                       self._joinfront('-', self.removed),
                                       self._joinfront('+', self.added))

    @classmethod
    def _joinfront(cls, front, lst):
        return ''.join('\n' + front + s for s in lst)

    @classmethod
    def parse(cls, string):
        hunks = [cls(**m.groupdict()) for m in cls.HUNK_PATTERN.finditer(string)]
        addfiles = [m.groupdict()['file'] for m in cls.ADDFILE_PATTERN.finditer(string)]

        return hunks, addfiles


class MyRedmine:
    def __init__(self):
        self.redmine_main = redmine.Redmine(Config.REDMINE_URL, key=Config.REDMINE_API_KEY, requests={'verify': False})
        self.current_user = self.redmine_main.user.get('current')

    #  -> list[IssueStatus]
    @property
    def issue_statuses(self):
        return self.redmine_main.issue_status.all()

    #  -> list[Issue]
    @property
    def my_issues(self):
        return self.my_issues_filtered()

    def my_issues_filtered(self, **kwargs):
        return self.redmine_main.issue.filter(project_id=Config.REDMINE_PROJECT, assigned_to_id=self.current_user.id,
                                              **kwargs)

    @property
    def project(self):
        return self.redmine_main.project.get(Config.REDMINE_PROJECT)

    def getIssue(self, id):
        return self.redmine_main.issue.get(id)


class LazyObject:
    def __init__(self):
        self.initialized = False
        self.data = None

    def init(self, *args):
        # print 'initializing'
        pass

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return repr(self.data)

    def __getattribute__(self, key):
        if self.initialized == False:
            self.init()
            self.initialized = True

        if key == 'data':
            return getattr(self, 'data')
        else:
            try:
                return object.__getattribute__(self, 'data').__getattribute__(key)
            except AttributeError:
                return super(LazyObject, self).__getattribute__(key)
