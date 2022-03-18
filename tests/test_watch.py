from pathlib import Path
from time import sleep

import anyio

from watchgod import Change, PythonFilter, awatch, watch

from .conftest import MockRustType


def test_watch(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    changes = None
    for changes in watch(tmp_path, watch_filter=None):
        break

    assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}


async def test_awatch(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    async for changes in awatch(tmp_path, watch_filter=None):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        break


async def test_await_stop(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    stop_event = anyio.Event()
    async for changes in awatch(tmp_path, watch_filter=None, stop_event=stop_event):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        stop_event.set()


def test_ignore_file(mock_rust_notify: MockRustType):
    mock_rust_notify([{(1, 'spam.pyc'), (1, 'spam.swp'), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}


def test_ignore_dir(mock_rust_notify: MockRustType):
    mock_rust_notify([{(1, '.git'), (1, '.git/spam'), (1, 'foo.txt')}])

    assert next(watch('.')) == {(Change.added, 'foo.txt')}


def test_python(mock_rust_notify: MockRustType):
    mock_rust_notify([{(2, 'spam.txt'), (2, 'spam.md'), (2, 'foo.py')}])

    assert next(watch('.', watch_filter=PythonFilter())) == {(Change.modified, 'foo.py')}


def test_python_extensions(mock_rust_notify: MockRustType):
    mock_rust_notify([{(1, 'spam.txt'), (1, 'spam.md'), (1, 'foo.py')}])

    f = PythonFilter(extra_extensions=('.md',))
    assert next(watch('.', watch_filter=f)) == {(Change.added, 'foo.py'), (Change.added, 'spam.md')}
