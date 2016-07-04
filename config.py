import yaml
import os
from os.path import join
from time import time
from lazy import lazy

APPLICATION_NAME = "iHateDarcs"

APPLICATION_DIR = '.' + APPLICATION_NAME

CONFIG_DIRS = (os.curdir, join(os.path.expanduser("~"), APPLICATION_DIR),
               join("/etc", APPLICATION_DIR),
               os.environ.get(APPLICATION_NAME.upper() + '_CONFIG'))

CONFIG_SAVE_PATH = join(os.path.expanduser("~"), APPLICATION_DIR)


class Serializable:
    FILENAME = "config"

    @classmethod
    def existing_config_locations(cls):
        for d in CONFIG_DIRS:
            if not d: continue
            f = join(d, cls.FILENAME)
            if os.path.isfile(f):
                yield f

    def save(self):
        try:
            if not os.path.isdir(CONFIG_SAVE_PATH):
                print("creating dir {}".format(CONFIG_SAVE_PATH))
                os.mkdir(CONFIG_SAVE_PATH)
            with open(join(CONFIG_SAVE_PATH, self.FILENAME), mode='w') as f:
                yaml.dump(self, f)
        except IOError as e:
            print("could not save config")
            print(e)

    def check_compatibility_update(self):
        r = False
        ref = type(self)()
        for key, val in ref.__dict__.items():
            # self.__dict__.setdefault(key,val)
            if not hasattr(self, key):
                print("updating config: {}: {}".format(key, val))
                r = True
                setattr(self, key, val)

        return r

    @classmethod
    def load(cls):
        config = None
        for f in cls.existing_config_locations():
            try:
                with open(f) as source:
                    config = yaml.load(source)
                    save = config.check_compatibility_update()
                    if save:
                        config.save()
                    break
            except IOError as e:
                print("could not read config")
                print(e)

        if not config:
            config = cls()
            config.save()

        return config


class ConfigObject(Serializable):
    def __init__(self):
        self._INITIALIZED = False

        self.RIETVELD_USER = "yourUserName"

        self.UPSTREAM_REPO = "darcs@yourhost.org:/storage/repos/all/yourrepo"

        # --max-count option for darcs changes
        self.MAX_PATCH_COUNT = 50
        self.MAX_PATCH_SHOW = 10

        self.PRISTINE_DIR = '../f3pristine/'
        self.BACKUP_DIR = '../f3backup/'

        self.TIMEOUT = 15

        self.AUTHOR = 'yourmail@yourhost.org'

        self.ANDROID_HOME = "/home/username/Android/Sdk"

        self.REDMINE_URL = "https://tracker.yourhost.org"
        self.REDMINE_PROJECT = "yourProject"
        self.REDMINE_API_KEY = "your redmine api key"

        self.TEST_COMMAND = "./build.py"
        self.TEST_COMMAND_ARGS = ["test"]

        self.DIFF_STORE_DIR = "/home/username/patches"

        self.RIETVELD_URL = "http://rietveld.yourhost.org:8000/"
        self.RIETVELD_USER = "yourUserName"

        self.INVALIDATE_UPSTREAM_CACHE_TIMEDELTA = 10000


Config = ConfigObject.load()  # type: ConfigObject


class CachedPatchList:
    def __init__(self, author, repo, reqsize):
        self.patches = []
        self.lastUpdate = 0
        self.repo = repo
        self.author_filter = author
        self.reqsize = reqsize

    def update(self, patches, reqsize=None):
        self.patches = patches
        if not reqsize is None:
            self.reqsize = reqsize
        self.lastUpdate = time()

    @property
    def due(self):
        return time() - self.lastUpdate > Config.INVALIDATE_UPSTREAM_CACHE_TIMEDELTA

    def invalidate(self):
        self.lastUpdate = 0

    @property
    def length(self):
        return len(self.patches)

    def __len__(self):
        return self.length

    def __str__(self):
        return "patches from {} for {}".format(self.repo or "local",
                                               self.author_filter or "all")


class CacheObject(Serializable):
    FILENAME = "cache"

    def __init__(self):
        self.UPSTREAM_PATCHES = []

    def get(self, author=None, repo=Config.UPSTREAM_REPO):
        def filter(cpl: CachedPatchList):
            if author and author != cpl.author_filter:
                return False
            if repo and repo != cpl.repo:
                return False
            return True

        return next(cpl for cpl in self.UPSTREAM_PATCHES if filter(cpl))

    def add(self, patches, author=None, repo=Config.UPSTREAM_REPO, reqsize=0):
        cpl = CachedPatchList(author, repo, reqsize)
        cpl.update(patches)
        self.UPSTREAM_PATCHES.append(cpl)
        self.save()
        return cpl

    def get_or_set(self, get_patches_callback, minsize=0, author=None,
                   repo=Config.UPSTREAM_REPO, force_refresh=False):
        try:
            cpl = self.get(author, repo)  # type: CachedPatchList
            if force_refresh:
                print("Forcing refresh")
            elif cpl.reqsize < minsize:
                print(
                    "Cached request result for {} elements, but now {} are wanted.".format(
                        cpl.reqsize, minsize))
            elif cpl.due:
                print("cache {}".format(
                    "outdated" if cpl.lastUpdate else "invalid"))
            else:
                return cpl.patches
            print("refreshing {}".format(cpl))
            patches = get_patches_callback()
            cpl.update(patches, minsize)
            self.save()
            return patches
        except StopIteration:
            patches = get_patches_callback()
            cpl = self.add(patches, author, repo, minsize)
            print("refreshed {}".format(cpl))
            return patches


class LazyCache:
    @lazy
    def get_cache(self):
        print("initializing cache")
        return CacheObject.load()  # type: CacheObject


Cache = LazyCache()
