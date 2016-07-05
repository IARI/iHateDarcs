import guidata.dataset.datatypes as dt
import guidata.dataset.dataitems as di
from darcs.changes import get_local_changes_only
from darcs.whatrevert import whatsnew
from pexpect_helper import SpawnAction, spawn
from config import Config
from collections import defaultdict
import os

try:
    from PyQt5.QtWidgets import QMessageBox
except RuntimeError:
    from PyQt4.QtGui import QMessageBox

from darcs.common import Prefixes, MyRedmine


class CancelDataset(dt.DataSet):
    def edit(self, parent=None, apply=None, size=None):
        res = super().edit(parent, apply, size)
        if not res:
            exit()
        return res


def message(title, text, question=False, icon=None):
    msg = QMessageBox()
    icon = (QMessageBox.Question if question else QMessageBox.Information) if icon is None else icon
    msg.setIcon(icon)

    msg.setText(text)
    # msg.setInformativeText("This is additional information")
    msg.setWindowTitle(title)
    # msg.setDetailedText("The details are as follows:")
    # msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    buttons = QMessageBox.Ok
    if question:
        buttons |= QMessageBox.Cancel
    msg.setStandardButtons(buttons)
    # msg.buttonClicked.connect(msgbtn)

    return msg.exec_() == QMessageBox.Ok


def pickfrom(*items, title="Pick an item...", itemtitle="items", multiple=False, strf=str):
    do_format = callable(strf)
    choices = [strf(i) for i in items] if do_format else list(items)
    kwargs = dict(label=itemtitle, choices=choices)
    if multiple:
        kwargs.update(default=range(len(items)))
        widget = di.MultipleChoiceItem(**kwargs).vertical(2)
    else:
        if do_format:
            kwargs.update(default=0)
        kwargs.update(radio=True)
        widget = di.ChoiceItem(**kwargs)

    class Processing(CancelDataset):
        selection = widget

    p = Processing(title=title)
    p.edit()

    if not do_format:
        return p.selection

    if multiple:
        return [items[i] for i in p.selection]

    return items[int(p.selection)]


def AmendPatch(cwd, files):
    patches = get_local_changes_only(cwd, Config.UPSTREAM_REPO, files, Config.MAX_PATCH_COUNT,
                                     author=Config.AUTHOR)[:Config.MAX_PATCH_SHOW]
    if not patches:
        message("no patches", "Konnte keine Patches von {} finden, die nicht auch in {} sind.".format(Config.AUTHOR,
                                                                                                      Config.UPSTREAM_REPO))
        exit()

    titlecount = defaultdict(int)
    for p in patches:
        titlecount[p.title] += 1

    def strf(p):
        if titlecount[p.title] > 1:
            return "{} ({}) \n\n".format(p.title, p.date)
        return p.title

    filechanges, addfiles = whatsnew(cwd, files)

    if addfiles:
        files_item = di.MultipleChoiceItem("addfiles", [(f, str(f)) for f in addfiles]).vertical()
    else:
        files_item = None

    class AmendPatch(CancelDataset):
        patch = di.ChoiceItem("patch", [(p, strf(p)) for p in patches])
        files = files_item
        askdeps = di.BoolItem("ask-deps", default=False)

    return AmendPatch("Amend Patch...")


def RecordPatch(*args, **kwargs):
    # raise_attr_exception=False
    mrm = MyRedmine()

    issueChoices = [(0, "None")] + [(i.id, "#{}: {}".format(i.id, i.subject)) for i in mrm.my_issues]

    class RecordPatch(CancelDataset):
        prefix = di.ChoiceItem('Prefix', [(p, p.name) for p in Prefixes])
        tracker = di.ChoiceItem("Tracker", issueChoices, default=0)

        name = di.StringItem("Name", notempty=True)
        author = di.StringItem("Author", notempty=True, default=Config.AUTHOR)

        @property
        def Prefix(self):
            return self.prefix.Name(self.tracker)

    return RecordPatch(*args, **kwargs)


def QuickEditIssue(*args, **kwargs):
    # raise_attr_exception=False
    mrm = MyRedmine()

    issueChoices = [(i, "#{} ({}: {}%)".format(i, i.status, i.done_ratio)) for i in mrm.my_issues_filtered(**kwargs)]
    statusChoices = [(0, "Dont Change")] + [(s, s.name) for s in mrm.issue_statuses]

    if not issueChoices:
        message("Nope", "There are no new Issues for you.")
        return

    class QuickIssue(CancelDataset):
        issue = di.ChoiceItem("Issue", issueChoices)
        status = di.ChoiceItem("Status", statusChoices, default=0)
        progress = di.IntItem("Progress", min=0, max=100, slider=True, default=0)
        comment = di.TextItem("Comment")

    return QuickIssue(*args)


class GraphOptions(CancelDataset):
    """
    Generate a Dependency Graph
    """
    limit = di.IntItem("How many Patches?", default=20, min=1)
    filename = di.StringItem("file", notempty=True, default='/tmp/depgraph')
    format = di.ChoiceItem('format', [('pdf', 'pdf'), ('svg', 'svg'), ('png', 'png')])
    open = di.BoolItem('open', help='gnome-open file when done if checked', default=True)
    color = di.ColorItem("My Local Patches", default="#00AA00")
    acolor = di.ColorItem("My Applied Patches", default="#0000DD")
    bcolor = di.ColorItem("Other Applied Patches", default="#999999")
    cleanup = di.BoolItem('cleanup', help='cleanup the dot source file if checked', default=True)

    # author = di.StringItem("Author", notempty=True, default=Config.AUTHOR)


class SaveDiff(dt.DataSet):
    """
    Save selected Diff?
    """
    name = di.FileSaveItem("name", basedir=Config.DIFF_STORE_DIR,
                           default=os.path.join(Config.DIFF_STORE_DIR, 'local diff'))
    # di.StringItem("name", notempty=True, default='local diff')


def getint(title="How many...", itemlabel="items", default=None, min=None, max=None, nonzero=None,
           unit='', even=None, slider=False, help='', check=True):
    class Getint(CancelDataset):
        selection = di.IntItem(itemlabel, default=default, min=min, max=max, nonzero=nonzero, unit=unit, even=even,
                               slider=slider, help=help, check=check)

    p = Getint(title=title)
    p.edit()

    return p.selection


class Ask(SpawnAction, str):
    def spawnAction(self, sp: spawn):
        _, m, *_ = yield self
        msg = m.group() + '\n' + self
        message('Continue?', msg, True)


class NewFileItem(di.FileSaveItem):
    def check_value(self, value):
        return super().check_value(value) and not os.path.exists(value)


def AutoGui(object, grouping=None, title="Preferences", changed_hook=None):
    class ObjectEditor(dt.DataSet):
        def edit(self, parent=None, apply=None, size=None):
            res = super().edit(parent, apply, size)
            changed = False
            if res:
                for ds in self._items:
                    k = ds._name
                    v = getattr(self, ds._name)
                    if getattr(object, k) != v:
                        print("updated {}: {} ({})".format(ds._name, v, type(v)))
                        changed = True
                        setattr(object, k, v)

            if changed and callable(changed_hook):
                changed_hook()

            return res

    members = {}

    for k, v in object.__dict__.items():
        if isinstance(v, int):
            members[k] = di.IntItem(k, v)
        elif isinstance(v, bool):
            members[k] = di.BoolItem(k, v)
        elif isinstance(v, str):
            members[k] = di.StringItem(k, v)

    AutoGui = type("AutoGui", (ObjectEditor,), members)

    return AutoGui(title)
