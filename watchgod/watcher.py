import logging
import os
import re
from enum import IntEnum

__all__ = 'Change', 'AllWatcher', 'DefaultDirWatcher', 'DefaultWatcher', 'PythonWatcher', 'RegExpWatcher'
logger = logging.getLogger('watchgod.watcher')


class Change(IntEnum):
    added = 1
    modified = 2
    deleted = 3


class AllWatcher:
    def __init__(self, root_path):
        self.files = {}
        self.root_path = root_path
        self.check()

    def should_watch_dir(self, entry):
        return True

    def should_watch_file(self, entry):
        return True

    def _walk(self, path, changes, new_files):
        if os.path.isfile(path):
            self._watch_file(path, changes, new_files)
        else:
            self._walk_dir(path, changes, new_files)

    def _watch_file(self, path, changes, new_files):
        mtime = os.stat(path).st_mtime
        new_files[path] = mtime
        old_mtime = self.files.get(path)
        if not old_mtime:
            changes.add((Change.added, path))
        elif old_mtime != mtime:
            changes.add((Change.modified, path))

    def _walk_dir(self, dir_path, changes, new_files):
        for entry in os.scandir(dir_path):
            if entry.is_dir():
                if self.should_watch_dir(entry):
                    self._walk_dir(entry.path, changes, new_files)
            elif self.should_watch_file(entry):
                self._watch_file(entry.path, changes, new_files)

    def check(self):
        changes = set()
        new_files = {}
        try:
            self._walk(str(self.root_path), changes, new_files)
        except OSError as e:
            # happens when a directory has been deleted between checks
            logger.warning('error walking file system: %s %s', e.__class__.__name__, e)

        # look for deleted
        deleted = self.files.keys() - new_files.keys()
        if deleted:
            changes |= {(Change.deleted, entry) for entry in deleted}

        self.files = new_files
        return changes


class DefaultDirWatcher(AllWatcher):
    ignored_dirs = {'.git', '__pycache__', 'site-packages', '.idea', 'node_modules'}

    def should_watch_dir(self, entry):
        return entry.name not in self.ignored_dirs


class DefaultWatcher(DefaultDirWatcher):
    ignored_file_regexes = r'\.py[cod]$', r'\.___jb_...___$', r'\.sw.$', '~$'

    def __init__(self, root_path):
        self._ignored_file_regexes = tuple(re.compile(r) for r in self.ignored_file_regexes)
        super().__init__(root_path)

    def should_watch_file(self, entry):
        return not any(r.search(entry.name) for r in self._ignored_file_regexes)


class PythonWatcher(DefaultDirWatcher):
    def should_watch_file(self, entry):
        return entry.name.endswith(('.py', '.pyx', '.pyd'))


class RegExpWatcher(AllWatcher):
    def __init__(self, root_path, re_files=None, re_dirs=None):
        self.re_files = re.compile(re_files) if re_files is not None else re_files
        self.re_dirs = re.compile(re_dirs) if re_dirs is not None else re_dirs
        super().__init__(root_path)

    def should_watch_file(self, entry):
        if self.re_files is not None:
            return self.re_files.match(entry.path)
        else:
            return super().should_watch_file(entry)

    def should_watch_dir(self, entry):
        if self.re_dirs is not None:
            return self.re_dirs.match(entry.path)
        else:
            return super().should_watch_dir(entry)
