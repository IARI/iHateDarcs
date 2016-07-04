from meta import Injector, abstractmethod
from pexpect import spawn, EOF, TIMEOUT, run, ExceptionPexpect
import os


def gnome_open(path):
    # return run('gnome-open {}'.format(path), cwd=cwd)
    return os.system('gnome-open {}'.format(path))


def bash(command, timeout=30, env=None, cwd=None):
    cmd = '/bin/bash -c "{}"'.format(command)
    print(cmd)
    # cmd = '/bin/bash -c'
    return run(cmd,
               # extra_args=command,
               timeout=timeout, env=None, cwd=cwd)
    # return run('/bin/bash', timeout=30, withexitstatus=False, events=None,
    #     extra_args=None, logfile=None, cwd=None, env=None, **kwargs)
    # , ['-c', command])


class SpawnAction(metaclass=Injector):
    @abstractmethod
    def spawnAction(self, sp: spawn):
        raise NotImplementedError


class Function(SpawnAction):
    def __init__(self, fun):
        self.fun = fun

    def spawnAction(self, sp: spawn):
        r = Lazy()
        _, m, *_ = yield r
        v = self.fun(m)
        r = self.inject(v)
        r.val = v
        yield from r.spawnAction(sp)


Function.associate(type(lambda x: x))


class Receive(SpawnAction, str):
    def spawnAction(self, sp: spawn):
        print("expecting {}".format(self))
        yield sp.expect(self)


class Send(SpawnAction, str):
    def spawnAction(self, sp: spawn):
        print("sending {}".format(self))
        yield sp.send(self)


class SendLine(SpawnAction, str):
    def spawnAction(self, sp: spawn):
        print("sendline {}".format(self))
        yield sp.sendline(self)


class EOFActiion(SpawnAction, EOF):
    def __init__(self, eof: EOF):
        self.eof = eof
        pass

    def spawnAction(self, sp: spawn):
        yield self.eof.value


class Err(SpawnAction, ExceptionPexpect):
    def __init__(self, e):
        self.e = e

    def spawnAction(self, sp: spawn):
        # SpawnException('encountered {}'.format(self.e))
        _, m, *_ = yield self.e
        if m is None:
            raise self.e
        raise SpawnException(m.group())


Err.associate(type(None))


class Sequence(SpawnAction, list):
    def __init__(self, arg=()):
        list.__init__(self, (self.inject(a) for a in arg))

    def spawnAction(self, sp: spawn):
        for a in self:
            yield from a.spawnAction(sp)


Sequence.associate(tuple)


class Alternative(SpawnAction, dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        for k, v in self.items():
            self[self.inject(k)] = self.inject(v)

    def spawnAction(self, sp: spawn):
        keys = list(self.keys())
        r = sp.expect(keys)
        yield r
        matched = keys[r]
        print('received {} ({})'.format(matched, r))
        yield from self.get(matched).spawnAction(sp)


class Lazy:
    def __init__(self, *args):
        if len(args):
            self.val = args[0]

    @property
    def val(self):
        return self._delayed_value

    @val.setter
    def val(self, val):
        self._delayed_value = val


class SpawnException(Exception):
    pass


class Strategy:
    def __init__(self, *args, **kwargs):
        args = list(args)
        if kwargs:
            args.append(kwargs)
        self.seq = SpawnAction.inject(args)
        self.trace = []
        self._last = None
        self.retvals = []

    @property
    def last(self):
        if not isinstance(self._last, Lazy):
            return self._last
        return self._last.val

    @property
    def matches(self):
        return [v[1] for v in self.trace]

    @last.setter
    def last(self, val):
        self._last = val

    def execute(self, sp: spawn, outputhook=print):
        gen = self.seq.spawnAction(sp)
        try:
            self.last = next(gen)
            while True:
                args = self.log(sp, outputhook)
                self.last = gen.send(args)
        except StopIteration:
            r = sp.expect([EOF, TIMEOUT])
            self.log(sp, outputhook)
            if r:
                self.error(sp.command)
        except (TIMEOUT, EOF) as e:
            self.log(sp, outputhook)
            self.error(sp.command)
            raise e

        return self

    def log(self, sp, outputhook=print):
        args = (str(sp.before), sp.match, str(sp.after))
        self.retvals.append(str(self.last))
        outputhook('{}\n{}\n{}\n---------'.format(str(sp.before), str(self.last), str(sp.after)))
        # outputhook('{}{}'.format(str(sp.before), str(sp.after)))
        self.trace.append(args)
        return args

    def error(self, cmd):
        print('execution of {} failed.'.format(cmd))
        for rv, tr in zip(self.retvals, self.trace):
            print(tr)
            print(rv)
