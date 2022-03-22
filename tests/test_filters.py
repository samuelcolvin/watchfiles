from typing import TYPE_CHECKING

from watchgod import Change, PythonFilter, watch

if TYPE_CHECKING:
    from conftest import MockRustType


def test_ignore_file(mock_rust_notify: 'MockRustType'):
    mock = mock_rust_notify([{(1, 'spam.pyc'), (1, 'spam.swp'), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}
    assert mock.watch_count == 1


def test_ignore_dir(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, '.git'), (1, '.git/spam'), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}


def test_python(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(2, 'spam.txt'), (2, 'spam.md'), (2, 'foo.py')}])

    assert next(watch('.', watch_filter=PythonFilter())) == {(Change.modified, 'foo.py')}


def test_python_extensions(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'spam.txt'), (1, 'spam.md'), (1, 'foo.py')}])

    f = PythonFilter(extra_extensions=('.md',))
    assert next(watch('.', watch_filter=f)) == {(Change.added, 'foo.py'), (Change.added, 'spam.md')}


def test_simple_function(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'added.txt'), (2, 'mod.txt'), (3, 'del.txt')}])

    def only_added(change: Change, path: str) -> bool:
        return change == Change.added

    assert next(watch('.', watch_filter=only_added)) == {(Change.added, 'added.txt')}
