from config import Config, Cache
from guidata_wrapper import *
from darcs.common import Patch
from darcs.changes import get_local_changes_only, get_changes
from darcs.whatrevert import annotate
from depgraph import draw_graph, darcs_deps
from darcs.clone import Clone, CopyFiles, CopyDir, TempBackup
from darcs.amendrecord import amend_patch, record_patch, unrecord_patch, rename_patch
from darcs.diff import diffPaths, diffMeldDirs, diff, apply, diffMeld
from darcs.pullsend import pull, send, unpull
from darcs.test import test
from collections import defaultdict
import os
from shutil import move
from rietveld import all_issues, RIETVELD_ISSUE_URL
import webbrowser
import traceback
from enum import Enum


class CommandPrefixes(Enum):
    DARCS = "darcs_"
    RIETVELD = "rietveld_"
    REDMINE = "redmine_"


class DarcsGui:
    DARCS_PREFIX = 'darcs_'

    def __init__(self, cli_args):
        if cli_args.cmd is None:
            prefixed_commands = list(CommandPrefixes)
            prefix = pickfrom(*prefixed_commands, title='pick a command category', itemtitle='Category',
                              strf=lambda c: c.name)

            cmds = list(self.PrefixedCommands(prefix.value))
            if not cmds:
                message("Nope", "there are no commands of type {}".format(prefix.name))
                exit()
            cmds.sort()
            self.cmd = pickfrom(*cmds, title='pick a command...', itemtitle='Command')
        else:
            self.cmd = cli_args.cmd

        self.args = cli_args
        self.files = cli_args.files or None
        print("files: {}".format(self.files))
        self.cwd = cli_args.cwd
        self.pristine = self._abspath(Config.PRISTINE_DIR)
        self.backup = self._abspath(Config.BACKUP_DIR)

        # patch(es) that might be needed in some commands
        self.patches = None

    @classmethod
    def Commands(cls):
        commands = {}
        for prefix in CommandPrefixes:
            commands.update(cls.PrefixedCommands(prefix.value))

        return commands

    @classmethod
    def PrefixedCommands(cls, prefix):
        return {m[len(prefix):].replace('_', ' '): getattr(cls, m) for m in cls.__dict__ if
                m.startswith(prefix) and callable(getattr(cls, m))}

    @property
    def cmd_string(self):
        return 'darcs {}'.format(self.cmd)

    @property
    def command_method(self):
        return self.Commands().get(self.cmd, None)

    def run(self):
        try:
            method = self.command_method
        except Exception as e:
            message('not implemented', '{} not supported yet'.format(self.cmd))
            raise e

        method(self)

    def getpatchagain(self, patch: Patch = None):
        if patch is None:
            patch = self.patches
        patches = get_changes(self.cwd, None, Config.MAX_PATCH_COUNT, author=Config.AUTHOR)

        return next(p for p in patches if p.title == patch.title)

    def getpatches(self):
        patches = get_local_changes_only(self.cwd, Config.UPSTREAM_REPO, self.files, Config.MAX_PATCH_COUNT,
                                         author=Config.AUTHOR)[:Config.MAX_PATCH_SHOW]

        if not patches:
            message("no patches", "Konnte keine Patches von {} finden, die nicht auch in {} sind.".format(Config.AUTHOR,
                                                                                                          Config.UPSTREAM_REPO))
            exit()

        return patches

    def getpatch(self, multiple=False):

        patches = self.getpatches()

        title = "Wähle Patches" if multiple else "Wähle einen Patch"

        titlecount = defaultdict(int)
        for p in patches:
            titlecount[p.title] += 1

        def strf(p: Patch):
            if titlecount[p.title] > 1:
                return "{} ({})".format(p.title, p.date)
            return p.title

        self.patches = pickfrom(*patches, title=title, itemtitle="Patch", strf=strf,
                                multiple=bool(multiple))

        if multiple == -1:
            self.patches = [p for p in patches if p not in self.patches]

        print(self.patches)

    def darcs_record(self):
        # backup = self._backup()

        NewPatchPars = RecordPatch('Neuen Patch Aufzeichnen')
        NewPatchPars.edit()

        record_changes, pending_changes, strips, dp = self._select_diff_parts("record")

        # backup.join()

        # revert(self.cwd, self.files)
        #
        # print('applying patch {} with p{}...'.format(record_changes, strips))
        # apply(self.cwd, record_changes, strips)
        # print('applied selected changes')

        print('unapplying patch {} with p{}...'.format(pending_changes, strips))
        apply(self.cwd, pending_changes, strips, unapply=True)
        print('unapplied pending changes')

        patchname = NewPatchPars.FormattedName
        record_patch(self.cwd, patchname, NewPatchPars.author)

        print('applying patch {} with p{}...'.format(pending_changes, strips))
        apply(self.cwd, pending_changes, strips)
        print('applied pending changes')

        list(dp)  # finish darcs diff

        # if message('send', 'send patch?\n{}'.format(self.patches.title), True):
        #     send(self.cwd, self.getpatchagain())

        patch = Patch('', NewPatchPars.author, None, patchname)

        self._afterPatchMod(patch)

    def darcs_pull(self):
        # pull(self.cwd, apply_all=False)
        pull(self.cwd)

    def rietveld_open_review(self):
        issues = all_issues()

        picked = pickfrom(*zip(*issues), title="pick an issue", itemtitle="Issues", strf=None)
        # picked = pickfrom(*issues, title="pick an issue", itemtitle="Issues", strf=None)

        # print(picked)

        picked_issue_url = RIETVELD_ISSUE_URL.format(picked)

        webbrowser.open_new(picked_issue_url)

    def redmine_edit_new_issue(self):
        self._redmine_change_issue_status_filtered(status_id=1)

    def redmine_edit_issue(self):
        self._redmine_change_issue_status_filtered()

    def _redmine_change_issue_status_filtered(self, **kwargs):

        qei = QuickEditIssue(**kwargs)

        qei.edit()

        print(qei.issue)
        print(type(qei.issue))

        issue = qei.issue

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

    def darcs_invalidate_cache(self):

        cpls = pickfrom(*Cache.get_cache.UPSTREAM_PATCHES, title="Pick cach entries", itemtitle="Cache entry",
                        multiple=True)
        for cpl in cpls:
            cpl.invalidate()

        Cache.get_cache.save()

    def darcs_amend(self):
        # backup = self._backup()
        # clone = self._clone_pristine()

        amend_gui = AmendPatch(self.cwd, self.files)

        amend_gui.edit()
        patch = amend_gui.patch

        if amend_gui.askdeps:
            message("not supported", '"ask-deps" is not yet supported.')

        if amend_gui.files:
            message("not supported", 'adding files is not yet supported.')
            print("Selected files:")
            print(amend_gui.files)

        patch_title = ''.join(e if e.isalnum() else '_' for e in patch.title)

        record_changes, pending_changes, strips, dp = self._select_diff_parts("amend_" + patch_title)

        print('unapplying patch {} with p{}...'.format(pending_changes, strips))
        apply(self.cwd, pending_changes, strips, unapply=True)
        print('unapplied pending changes')

        try:
            amend_patch(self.cwd, patch, self.files, look_for_adds=False)
        except Exception as e:
            traceback.print_exc()
            print("amend command failed, continuing...")

        print('applying patch {} with p{}...'.format(pending_changes, strips))
        apply(self.cwd, pending_changes, strips)
        print('applied pending changes')

        # os.remove(record_changes)
        # os.remove(pending_changes)

        list(dp)  # finish darcs diff

        self._afterPatchMod(patch)

    def _afterPatchMod(self, patch: Patch):
        if message('send', 'send patch?\n{}'.format(patch.title), True):
            send(self.cwd, self.getpatchagain(patch))

        issues = patch.referenced_issues
        if not issues:
            return

        issueNames = "\n".join(["#{}: {}".format(i.id, i.subject) for i in issues])
        if message('Edit Issues', 'Do you want to edit referenced Issues?\n{}'.format(issueNames), True):
            for issue in issues:
                QuickEditIssue2(issue)

    def darcs_annotate(self):
        annotated = annotate(self.cwd, self.files)
        # os.path.abspath(Config.ANNOTATED_STORE_DIR)
        if not os.path.isdir(Config.ANNOTATED_STORE_DIR):
            print("creating directory {}".format(Config.ANNOTATED_STORE_DIR))
            os.mkdir(Config.ANNOTATED_STORE_DIR)

        fname = os.path.basename(self.files[0])

        filepath = os.path.join(Config.ANNOTATED_STORE_DIR, fname + ".annotated")
        newfilepath = filepath
        while os.path.exists(newfilepath):
             newfilepath += 'X'
        if newfilepath != filepath:
             message("existed", "File {} existed. Patch saved as {}.".format(filepath, newfilepath))

        with open(newfilepath,'w') as f:
            f.write(annotated)

        from pexpect_helper import gnome_open
        gnome_open(newfilepath)
        # message('annotated', annotated)

    def darcs_rename(self):
        self.getpatch()
        patch = self.patches

        NewPatchPars = RecordPatch('Neuen Patch Aufzeichnen')
        NewPatchPars.read(patch)
        NewPatchPars.edit()

        old, new = patch.title, NewPatchPars.FormattedName
        if old == new:
            print("patch name\n   {}\nnot changed.".format(old))
            return
        print("renaming\n   {}\n-> {}".format(old, new))
        rename_patch(self.cwd, patch, new)

        patch.title = new
        if message('send', 'send patch?\n{}'.format(patch.title), True):
            send(self.cwd, self.getpatchagain(patch))

    def darcs_suspend(self):
        self.getpatch()
        patch = self.patches

        depres = darcs_deps(self.cwd, patch)
        #message(depres)

    def darcs_diff(self):
        record_changes, pending_changes, strips, dp = self._select_diff_parts('diff', False)

        os.remove(pending_changes)

        list(dp)

        saveDiff = SaveDiff()

        do_move = saveDiff.edit()

        if message("Revert", "Revert selected changes?", True):
            print("revert {}".format(record_changes))
            apply(self.cwd, record_changes, strips, True)

        if do_move:
            filepath = os.path.join(Config.DIFF_STORE_DIR, saveDiff.name)
            newfilepath = filepath
            while os.path.exists(newfilepath):
                newfilepath += 'X'
            if newfilepath != filepath:
                message("existed", "File {} existed. Patch saved as {}.".format(filepath, newfilepath))
            move(record_changes, newfilepath)

    def darcs_changes(self):
        clone = self._clone_pristine()
        self.getpatch()
        clone.join()

        unpull(self.pristine, self.patches)



        # diffMeld(self.pristine, self.cwd, filechanges=())

    def darcs_apply(self):
        self._apply()

    def darcs_unapply(self):
        self._apply(True)

    def _apply(self, unapply=False):
        files = os.listdir(Config.DIFF_STORE_DIR)

        if not files:
            message("No patches", "You have no recorded diffs in {}".format(Config.DIFF_STORE_DIR))
            exit()

        patch = pickfrom(*files)
        patchfile = os.path.join(Config.DIFF_STORE_DIR, patch)
        print(patchfile)

        if message('diff', "continue?", True):
            apply(self.cwd, patchfile, 3, unapply=unapply)

        if message('delete', "delete patch {} ?".format(patchfile), True):
            os.remove(patchfile)

    def darcs_test(self):
        clone = self._clone_pristine()
        self.getpatch(-1)
        clone.join()

        unpull(self.pristine, *self.patches)

        test(self.pristine)

    def darcs_unrecord(self):
        self.getpatch()
        unrecord_patch(self.cwd, self.patches)

    def darcs_show_dependencies(self):
        draw_graph(self.cwd)

    def darcs_unpull(self):
        self.getpatch()
        unpull(self.cwd, self.patches)

    def darcs_send(self):

        send_gui = SendPatch(self.cwd, self.files)
        send_gui.edit()

        patch = send_gui.patch
        print(patch)

        send(self.cwd, patch, output=send_gui.output)

    def darcs_preferences(self):
        AutoGui(Config, changed_hook=Config.save).edit()

    def _backup(self):
        backup = CopyDir(self.cwd, self.backup)
        backup.start()
        return backup

    def _restore_backup(self):
        restore = CopyDir(self.backup, self.cwd)
        restore.start()
        return restore

    def _clone_pristine(self):
        clone = Clone(self.cwd, self.pristine)
        clone.start()
        return clone

    def _compare_paths(self, p1, p2):
        return os.path.abspath(os.path.join(self.cwd, p1)) == os.path.abspath(os.path.join(self.cwd, p2))

    def _abspath(self, relpath):
        return os.path.abspath(os.path.join(self.cwd, relpath))

    def _copy_new_files(self, addfiles):
        new_files_selected = pickfrom(*addfiles, multiple=True)

        copytask = CopyFiles(self.cwd, self.pristine, new_files_selected)
        copytask.start()
        return copytask

    def _patch_prefix(self, id):
        return 'darcs_{}_'.format(id)

    def _select_diff_parts(self, cmdname, askContinue=True):
        dp = diffPaths(self.cwd, self.files)
        old, new = next(dp)

        selectedChanges = TempBackup(new, 'select_changes_')
        selectedChanges.start()
        selectedChanges.wait()

        diffMeldDirs(old, selectedChanges.target)

        if askContinue and not message('continue', 'continue with selected changes?', True):
            list(dp)
            raise OperationCancelled()

        record_changes = diff(old, selectedChanges.target, self._patch_prefix(cmdname))

        pending_changes = diff(selectedChanges.target, new, self._patch_prefix('pending'))
        selectedChanges.join()
        strips = old.count(os.path.sep) + 1

        return record_changes, pending_changes, strips, dp


class OperationCancelled(Exception):
    pass
