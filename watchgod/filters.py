import logging
import os
import re
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence, Union

__all__ = 'BaseFilter', 'DefaultFilter', 'PythonFilter'
logger = logging.getLogger('watchgod.watcher')


if TYPE_CHECKING:
    from .main import Change


class BaseFilter(ABC):
    __slots__ = '_ignore_dirs', '_ignore_entity_regexes', '_ignore_paths'
    ignore_dirs: Sequence[str] = ()
    # "entity" here refers to a file or directory - basically the result of `
    ignore_entity_patterns: Sequence[str] = ()
    ignore_paths: Sequence[Union[str, Path]] = ()

    def __init__(self) -> None:
        self._ignore_dirs = set(self.ignore_dirs)
        self._ignore_entity_regexes = tuple(re.compile(r) for r in self.ignore_entity_patterns)
        self._ignore_paths = tuple(map(str, self.ignore_paths))

    def __call__(self, change: 'Change', path: str) -> bool:
        parts = path.lstrip(os.sep).split(os.sep)
        if any(p in self._ignore_dirs for p in parts):
            return False

        entity_name = parts[-1]
        if any(r.search(entity_name) for r in self._ignore_entity_regexes):
            return False
        elif self._ignore_paths and path.startswith(self._ignore_paths):
            return False
        else:
            return True


class DefaultFilter(BaseFilter):
    ignore_dirs: Sequence[str] = (
        '__pycache__',
        '.git',
        '.hg',
        '.svn',
        '.tox',
        '.venv',
        'site-packages',
        '.idea',
        'node_modules',
    )
    ignore_entity_patterns: Sequence[str] = (
        r'\.py[cod]$',
        r'\.___jb_...___$',
        r'\.sw.$',
        '~$',
        r'^\.\#',
        r'^\.DS_Store$',
        r'^flycheck_',
    )

    def __init__(
        self,
        *,
        ignore_dirs: Optional[Sequence[str]] = None,
        ignore_entity_patterns: Optional[Sequence[str]] = None,
        ignore_paths: Optional[Sequence[Union[str, Path]]] = None,
    ) -> None:
        """
        Take ignores_paths as an argument to support the `--ignore-paths` option in the CLI.
        """
        if ignore_dirs is not None:
            self.ignore_dirs = ignore_dirs
        if ignore_entity_patterns is not None:
            self.ignore_entity_patterns = ignore_entity_patterns
        if ignore_paths is not None:
            self.ignore_paths = ignore_paths
        super().__init__()


class PythonFilter(DefaultFilter):
    def __init__(
        self,
        *,
        ignore_paths: Optional[Sequence[Union[str, Path]]] = None,
        extra_extensions: Sequence[str] = (),
    ) -> None:
        """
        Take `ignores_paths` and `extra_extensions` to support those options in the CLI.
        """
        self.extensions = ('.py', '.pyx', '.pyd') + tuple(extra_extensions)
        super().__init__(ignore_paths=ignore_paths)

    def __call__(self, change: 'Change', path: str) -> bool:
        return path.endswith(self.extensions) and super().__call__(change, path)
