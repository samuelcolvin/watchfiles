from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from watchfiles import Change, DefaultFilter, PythonFilter, watch

if TYPE_CHECKING:
    from conftest import MockRustType


def test_ignore_file(mock_rust_notify: 'MockRustType'):
    mock = mock_rust_notify([{(1, 'spam.pyc'), (1, 'spam.swp'), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}
    assert mock.watch_count == 1


def test_ignore_dir(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, '.git'), (1, str(Path('.git') / 'spam')), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}


def test_python(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(2, 'spam.txt'), (2, 'spam.md'), (2, 'foo.py')}])

    assert next(watch('.', watch_filter=PythonFilter())) == {(Change.modified, 'foo.py')}


def test_python_extensions(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'spam.txt'), (1, 'spam.md'), (1, 'foo.py')}])

    f = PythonFilter(extra_extensions=('.md',))
    assert next(watch('.', watch_filter=f)) == {(Change.added, 'foo.py'), (Change.added, 'spam.md')}


def test_web_filter(mock_rust_notify: 'MockRustType'):
    # test case from docs

    class WebFilter(DefaultFilter):
        allowed_extensions = '.html', '.css', '.js'

        def __call__(self, change: Change, path: str) -> bool:
            return super().__call__(change, path) and path.endswith(self.allowed_extensions)

    mock_rust_notify([{(1, 'foo.txt'), (2, 'bar.html'), (3, 'spam.xlsx'), (1, '.other.js')}])

    assert next(watch('.', watch_filter=WebFilter())) == {(Change.modified, 'bar.html'), (Change.added, '.other.js')}


def test_simple_function(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'added.txt'), (2, 'mod.txt'), (3, 'del.txt')}])

    def only_added(change: Change, path: str) -> bool:
        return change == Change.added

    assert next(watch('.', watch_filter=only_added)) == {(Change.added, 'added.txt')}


@pytest.mark.parametrize(
    'path,expected',
    [
        ('foo.txt', True),
        ('foo.swp', False),
        ('foo.swx', False),
        ('foo.swx.more', True),
        (Path('x/y/z/foo.txt'), True),
        (Path.home() / 'ignore' / 'foo.txt', False),
        (Path.home() / 'ignore', False),
        (Path.home() / '.git' / 'foo.txt', False),
        (Path.home() / 'foo' / 'foo.txt', True),
        (Path('.git') / 'foo.txt', False),
    ],
)
def test_default_filter(path, expected):
    f = DefaultFilter(ignore_paths=[Path.home() / 'ignore'])
    assert f(Change.added, str(path)) == expected
