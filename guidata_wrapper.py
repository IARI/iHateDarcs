import guidata.dataset.datatypes as dt
import guidata.dataset.dataitems as di
import guidata.dataset.qtwidgets as qtw
from textwrap import shorten
from darcs.changes import get_local_changes_only
from darcs.common import Patch
from darcs.whatrevert import whatsnew
from pexpect_helper import SpawnAction, spawn
from config import Config
from collections import defaultdict
from releasetestutil import get_releasetest_issues
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


def patchChoiceItem(patches):
    # if not patches:
    #     patches = get_local_changes_only(cwd, Config.UPSTREAM_REPO, files, Config.MAX_PATCH_COUNT,
    #                                  author=Config.AUTHOR)[:Config.MAX_PATCH_SHOW]

    titlecount = defaultdict(int)
    for p in patches:
        titlecount[p.title] += 1

    def strf(p):
        if titlecount[p.title] > 1:
            return "{} ({}) \n\n".format(p.title, p.date)
        return p.title

    return di.ChoiceItem("patch", [(p, strf(p)) for p in patches])


def message(title, text, question=False, icon=None):
    msg = QMessageBox()
    icon = (
    QMessageBox.Question if question else QMessageBox.Information) if icon is None else icon
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


def SendPatch(cwd, files):
    author = Config.AUTHOR
    patches = get_local_changes_only(cwd, Config.UPSTREAM_REPO, files, Config.MAX_PATCH_COUNT,
                                     author=author)[:Config.MAX_PATCH_SHOW]

    if not patches:
        raise Exception("No unapplied patcehs found by {}.".format(author))

    def callback(dataset, item, value, parent):
        dataset.output = Config.DIFF_STORE_DIR

    class SendPatch(CancelDataset):
        patch = patchChoiceItem(patches)
        output = di.StringItem("file", default='').set_pos(col=0)
        button = di.ButtonItem("default", callback).set_pos(col=1)

    return SendPatch("Send Patch...")


def AmendPatch(cwd, files):
    patches = get_local_changes_only(cwd, Config.UPSTREAM_REPO, files, Config.MAX_PATCH_COUNT,
                                     author=Config.AUTHOR)[:Config.MAX_PATCH_SHOW]
    if not patches:
        message("no patches",
                "Konnte keine Patches von {} finden, die nicht auch in {} sind.".format(
                    Config.AUTHOR,
                    Config.UPSTREAM_REPO))
        exit()

    filechanges, addfiles = whatsnew(cwd, files)

    if addfiles:
        files_item = di.MultipleChoiceItem("addfiles", [(f, str(f)) for f in addfiles]).vertical()
    else:
        files_item = None

    class AmendPatch(CancelDataset):
        patch = patchChoiceItem(patches)
        files = files_item
        askdeps = di.BoolItem("ask-deps", default=False)

    return AmendPatch("Amend Patch...")


def RecordPatch(*args, **kwargs):
    # raise_attr_exception=False
    mrm = MyRedmine()

    issueChoices = [(0, "None")] + [(i.id, "#{}: {}".format(i.id, i.subject)) for i in
                                    mrm.my_issues]

    releaseChoices = [(0, "None")] + [
        (int(r['Nr']), "{}: {}".format(r['Nr'], shorten(r['Beschreibung'], 80))) for r in
        get_releasetest_issues(assignee=Config.GSPREAD_ASSIGNEE)]

    class RecordPatch(CancelDataset):
        prefix = di.ChoiceItem('Prefix', [(p, p.name) for p in Prefixes])
        tracker = di.ChoiceItem("Tracker", issueChoices, default=0)
        rtest = di.ChoiceItem("Releasetest", releaseChoices, default=0)

        name = di.StringItem("Name", notempty=True)
        author = di.StringItem("Author", notempty=True, default=Config.AUTHOR)

        @property
        def Prefix(self):
            return self.prefix.Name(self.tracker, self.rtest)

        @property
        def FormattedName(self):
            return '{}: {}'.format(self.Prefix, self.name)

        def check_prefix(self):
            if not self.prefix.hasParameter:
                return False
            return self.tracker > 0 or self.rtest


        def read(self, p: Patch):
            prefix, name = p.title.split(': ', 1)
            self.name = name
            self.prefix, self.tracker, self.rtest = Prefixes.read(prefix)

    return RecordPatch(*args, **kwargs)


def QuickEditIssue(*args, **kwargs):
    # raise_attr_exception=False
    mrm = MyRedmine()

    issueChoices = [(i, "#{} ({}: {}%)".format(i, i.status, i.done_ratio)) for i in
                    mrm.my_issues_filtered(**kwargs)]
    statusChoices = [(0, "Dont Change")] + [(s, s.name) for s in mrm.issue_statuses]
    releaseChoices = [(int(r['Nr']), "{}: {}".format(r['Nr'], shorten(r['Beschreibung'], 50))) for
                      r in
                      get_releasetest_issues()]

    if not issueChoices:
        message("Nope", "There are no new Issues for you.")
        return

    class QuickIssue(CancelDataset):
        issue = di.ChoiceItem("Issue", issueChoices)
        rtest = di.ChoiceItem("Releasetest", releaseChoices)
        status = di.ChoiceItem("Status", statusChoices, default=0)
        progress = di.IntItem("Progress", min=0, max=100, slider=True, default=0)
        comment = di.TextItem("Comment")

    return QuickIssue(*args)


def QuickEditIssue2(issue, *args):
    mrm = MyRedmine()
    stati = [issue.status] + [s for s in mrm.issue_statuses if s.name != issue.status.name]
    statusChoices = [(s, s.name) for s in stati]

    class QuickIssue(CancelDataset):
        status = di.ChoiceItem("Status", statusChoices)
        progress = di.IntItem("Progress", min=0, max=100, slider=True, default=issue.done_ratio)
        comment = di.TextItem("Comment")

    qei = QuickIssue(*args)
    qei.edit()

    if qei.status:
        issue.status_id = qei.status.id

    if qei.comment:
        issue.notes = qei.comment

    save_progress = qei.progress != issue.done_ratio
    if qei.progress < issue.done_ratio:
        save_progress = message("are you sure?",
                                "you're changing the progress of the issue from {}% to {}%.".format(
                                    issue.done_ratio,
                                    qei.progress),
                                True)
    if save_progress:
        issue.done_ratio = qei.progress

    issue.save()

    return qei


class GraphOptions(CancelDataset):
    """
    Generate a Dependency Graph
    """
    limit = di.IntItem("How many Patches?", default=20, min=1)
    filename = di.StringItem("file", notempty=True, default='/tmp/depgraph')
    format = di.ChoiceItem('format', [('pdf', 'pdf'), ('svg', 'svg'), ('png', 'png')])
    just_mine = di.BoolItem('only mine', help='show only my patches', default=False)
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
        selection = di.IntItem(itemlabel, default=default, min=min, max=max, nonzero=nonzero,
                               unit=unit, even=even,
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


class DictItem(di.ButtonItem):
    """
    Construct a dictionary data item
        * label [string]: name
        * default [dict]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def __init__(self, label, default=None, help='', check=True):
        def dictedit(instance, item, value, parent):
            try:
                # Spyder 3
                from spyder.widgets.variableexplorer \
                    import collectionseditor
                Editor = collectionseditor.CollectionsEditor
            except ImportError:
                # Spyder 2
                from spyderlib.widgets import dicteditor
                Editor = dicteditor.DictEditor
            editor = Editor(parent)
            value_was_none = value is None
            if value_was_none:
                value = {}
            editor.setup(value)
            if editor.exec_():
                return editor.get_value()
            else:
                if value_was_none:
                    return
                return value

        di.ButtonItem.__init__(self, label, dictedit, icon='dictedit.png',
                               default=default, help=help, check=check)


qtw.DataSetEditLayout.register(DictItem, qtw.ButtonWidget)


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
        if k[0] == '_':
            continue
        elif isinstance(v, int):
            members[k] = di.IntItem(k, v)
        elif isinstance(v, bool):
            members[k] = di.BoolItem(k, v)
        elif isinstance(v, str):
            members[k] = di.StringItem(k, v)
        elif isinstance(v, dict):
            members[k] = DictItem(k, v)

    AutoGui = type("AutoGui", (ObjectEditor,), members)

    return AutoGui(title)
