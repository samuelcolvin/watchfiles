import logging
import re
from typing import TYPE_CHECKING, Sequence, Tuple

__all__ = 'BaseFilter', 'DefaultFilter', 'PythonFilter'
logger = logging.getLogger('watchgod.watcher')


if TYPE_CHECKING:
    from .main import Change


class BaseFilter:
    __slots__ = 'ignore_dirs', 'ignore_entity_regexes'

    def __init__(self, ignore_dirs: Sequence[str], ignore_entity_patterns: Sequence[str]) -> None:
        self.ignore_dirs = set(ignore_dirs)
        self.ignore_entity_regexes = tuple(re.compile(r) for r in ignore_entity_patterns)

    def __call__(self, change: 'Change', path: str) -> bool:
        parts = path.lstrip('/').split('/')
        if any(p in self.ignore_dirs for p in parts):
            return False
        entity_name = parts[-1]
        return not any(r.search(entity_name) for r in self.ignore_entity_regexes)


default_ignore_dirs = '__pycache__', '.git', '.hg', '.svn', '.tox', '.venv', 'site-packages', '.idea', 'node_modules'
default_ignore_entity_patterns = (
    r'\.py[cod]$',
    r'\.___jb_...___$',
    r'\.sw.$',
    '~$',
    r'^\.\#',
    r'^\.DS_Store$',
    r'^flycheck_',
)


class DefaultFilter(BaseFilter):
    def __init__(self) -> None:
        super().__init__(default_ignore_dirs, default_ignore_entity_patterns)


class PythonFilter(DefaultFilter):
    def __init__(
        self,
        extra_extensions: Tuple[str, ...] = (),
    ) -> None:
        self.extensions = ('.py', '.pyx', '.pyd') + extra_extensions
        super().__init__()

    def __call__(self, change: 'Change', path: str) -> bool:
        return path.endswith(self.extensions) and super().__call__(change, path)
