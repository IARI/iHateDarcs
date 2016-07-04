from darcs.common import Darcs
from darcs.changes import get_changes, get_changes_from_upstream
from config import Config
from guidata_wrapper import GraphOptions
from graphviz import Source, Digraph

import re


# from pydot.dot_parser import parse_dot_data


# from pexpect_helper import gnome_open


def darcs_show(cwd, limit, output='/tmp/depgraph', author=None):
    args = ['show', 'dependencies', '--last', str(limit)]
    if author:
        args += ['--matches', 'author ' + author]
    depgraph = Darcs(args, None, cwd=cwd)
    return depgraph.get_all_output()


# from pexpect_helper import bash
# r = bash('"darcs show dependencies --last={} | dot -T{} -o {}"'.format(limit, format, output), cwd=cwd)
# print('done. output:')
# print(r)
# Darcs(['show', 'dependencies', '--last', limit], None, cwd=cwd)

# format='pdf',

PATCH_PATTERN = re.compile(r"\s*\d+\s*\[label=\"([^\n]*)\"\];", re.M)


def draw_graph(cwd):
    ui = GraphOptions()
    ui.edit()

    max_patchcount = 2 * ui.limit

    # changes = get_changes(cwd, None, ui.limit, author=Config.AUTHOR)
    from_upstream = get_changes_from_upstream(cwd, Config.UPSTREAM_REPO, None, max_patchcount)
    changes = get_changes(cwd, None, max_patchcount)

    # print('format picked: {}'.format(ui.format))
    dotSrcLines = darcs_show(cwd, ui.limit, ui.filename).splitlines()

    def changeColor(i, color):
        dotSrcLines[i] = dotSrcLines[i][:-2] + 'color="{}"];'.format(color)

    for i, l in enumerate(dotSrcLines):
        m = PATCH_PATTERN.search(l)
        if not m:
            continue
        title = m.group(1).replace("\\n", " ").strip()
        print(title)

        def find_in(lst):
            try:
                return next(c for c in lst if title == c.title)
            except StopIteration:
                return None

        up = find_in(from_upstream)  # type: Patch
        loc = find_in(changes)  # type: Patch
        if up:
            if not loc:
                print("patch in upstream but not local?? {}".format(title))
            if up.author == Config.AUTHOR:
                changeColor(i, ui.acolor)
            else:
                changeColor(i, ui.bcolor)
        elif loc:
            if loc.author == Config.AUTHOR:
                changeColor(i, ui.color)

    dotSrc = "\n".join(dotSrcLines)

    print(dotSrc)

    # for l in enumerate(dotSrc.splitlines()):
    #     print("{}:  {}".format(*l))

    # dot = parse_dot_data(dotSrc)

    # print(dot)
    dot = Source(dotSrc)
    #
    # print(dotObj.source)
    #
    # dot.graph_attr['rankdir'] = 'LR'
    dot.format = ui.format
    dot.render(ui.filename, view=ui.open, cleanup=ui.cleanup)


    # dot = darcs_show(cwd, ui.limit, ui.filename, author=Config.AUTHOR)
    # print(dot)

    # if ui.open:
    #     r = gnome_open(ui.filename)
    #     print(r)
