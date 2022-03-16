import sys
from pathlib import Path
from time import sleep

import anyio
import pytest

from watchgod import Change, PythonFilter, awatch, watch

from .conftest import mktree

skip_on_windows = pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
skip_unless_linux = pytest.mark.skipif(sys.platform != 'linux', reason='test only on linux')
tree = {
    'foo': {
        'bar.txt': 'bar',
        'spam.py': 'whatever',
        'spam.pyc': 'splosh',
        'recursive_dir': {
            'a.js': 'boom',
        },
        '.git': {
            'x': 'y',
        },
    }
}


def test_add(tmp_path):
    sleep(0.01)
    (tmp_path / 'foo.txt').write_text('foobar')
    watcher = watch(tmp_path, watch_filter=None)
    assert next(watcher) == {(Change.added, str((tmp_path / 'foo.txt')))}


def test_add_loop(tmp_path):
    sleep(0.01)
    (tmp_path / 'foo.txt').write_text('foobar')
    changes = None

    for changes in watch(tmp_path, watch_filter=None):
        break

    assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}


def test_modify(tmp_path: Path):
    mktree(tmp_path, tree)
    sleep(0.01)

    (tmp_path / 'foo/bar.txt').chmod(0o444)

    watcher = watch(tmp_path, watch_filter=None)
    # because this file is pretty new, we get the created event too
    assert next(watcher) == {
        (Change.added, str(tmp_path / 'foo/bar.txt')),
        (Change.modified, str(tmp_path / 'foo/bar.txt')),
    }


def test_delete(tmp_path: Path):
    mktree(tmp_path, tree)
    sleep(0.01)

    (tmp_path / 'foo/bar.txt').unlink()

    watcher = watch(tmp_path, watch_filter=None)
    # because this file is pretty new, we get the created event too
    assert next(watcher) == {
        (Change.added, str(tmp_path / 'foo/bar.txt')),
        (Change.deleted, str(tmp_path / 'foo/bar.txt')),
    }


def test_ignore_file(tmp_path):
    watcher = watch(tmp_path)

    sleep(0.01)
    (tmp_path / 'spam.pyc').write_text('foobar')
    (tmp_path / 'spam.swp').write_text('foobar')
    (tmp_path / 'foo.txt').write_text('foobar')

    assert next(watcher) == {(Change.added, str(tmp_path / 'foo.txt'))}


def test_ignore_dir(tmp_path):
    watcher = watch(tmp_path)

    sleep(0.01)
    (tmp_path / '.git').mkdir()
    (tmp_path / '.git/spam').write_text('xxx')
    (tmp_path / 'foo.txt').write_text('foobar')

    assert next(watcher) == {(Change.added, str(tmp_path / 'foo.txt'))}


def test_python(tmp_path):
    watcher = watch(tmp_path, watch_filter=PythonFilter())

    sleep(0.01)
    (tmp_path / 'spam.py').write_text('xxx')
    (tmp_path / 'bar.txt').write_text('xxx')
    (tmp_path / 'spam.md').write_text('xxx')

    assert next(watcher) == {(Change.added, str(tmp_path / 'spam.py'))}


def test_python_extensions(tmp_path):
    watcher = watch(tmp_path, watch_filter=PythonFilter(extra_extensions=('.md',)))

    sleep(0.01)
    (tmp_path / 'spam.py').write_text('xxx')
    (tmp_path / 'bar.txt').write_text('xxx')
    (tmp_path / 'spam.md').write_text('xxx')

    assert next(watcher) == {
        (Change.added, str(tmp_path / 'spam.py')),
        (Change.added, str(tmp_path / 'spam.md')),
    }


def test_does_not_exist(tmp_path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError, match='No path was found.'):
        watcher = watch(p)
        next(watcher)


async def test_await_add(tmp_path):
    sleep(0.01)
    (tmp_path / 'foo.txt').write_text('foobar')
    async for changes in awatch(tmp_path, watch_filter=None):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        break


async def test_await_stop(tmp_path):
    sleep(0.01)
    stop_event = anyio.Event()
    (tmp_path / 'foo.txt').write_text('foobar')
    async for changes in awatch(tmp_path, watch_filter=None, stop_event=stop_event):
        debug(changes)
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        stop_event.set()
