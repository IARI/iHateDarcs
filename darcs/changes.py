from darcs.common import Darcs, Patch
from config import Cache, Config


def get_local_changes_only(cwd, upstream, files, max_patchcount=None, author=None):
    upstream_patches = get_changes_from_upstream(cwd, upstream, files, max_patchcount, author)
    patches = get_changes(cwd, None, max_patchcount, author=author)

    for p in upstream_patches:
        print("{}: {}".format(p in patches, p.title))
    for p in patches:
        if p not in upstream_patches:
            print(p.title)

    return [p for p in patches if p not in upstream_patches]


def get_changes_from_upstream(cwd, upstream, files, max_patchcount=None, author=None):
    callback = lambda: get_changes(cwd, None, max_patchcount, author=author, repo=upstream)

    return Cache.get_cache.get_or_set(callback, max_patchcount, author, upstream)


def get_changes(cwd, file, max_patchcount=None, author=None, repo=None):
    args = ['changes', '-a']

    if max_patchcount:
        args += ['--max-count', str(max_patchcount)]
    if repo:
        args += ['--repo', repo]
    if author:
        args += ['--matches', 'author ' + author]

    darcs_changes = Darcs(args, file, cwd=cwd)

    output = darcs_changes.get_all_output()

    return Patch.parse(output)
