import sys
from pathlib import Path

import pytest

from watchgod._rust_notify import RustNotify


def test_add(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)
    (test_dir / 'foo.txt').write_text('foobar')

    assert watcher.watch(200, 50, None) == {(1, str(test_dir / 'foo.txt'))}


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_modify_write(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    (test_dir / 'a.txt').chmod(0o444)

    assert watcher.watch(200, 50, None) == {(2, str(test_dir / 'a.txt'))}


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_modify_chmod(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    (test_dir / 'a.txt').chmod(0o444)

    assert watcher.watch(200, 50, None) == {(2, str(test_dir / 'a.txt'))}


def test_delete(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    # notify those files
    (test_dir / 'c.txt').unlink()

    assert watcher.watch(200, 50, None) == {
        (3, str(test_dir / 'c.txt')),
    }


def test_does_not_exist(tmp_path: Path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError):
        RustNotify([str(p)], False)


def test_rename(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    f = test_dir / 'a.txt'
    f.rename(f.with_suffix('.new'))

    assert watcher.watch(200, 50, None) == {
        (3, str(f)),
        (1, str(test_dir / 'a.new')),
    }


def test_watch_multiple(tmp_path: Path):
    foo = tmp_path / 'foo'
    foo.mkdir()
    bar = tmp_path / 'bar'
    bar.mkdir()
    watcher = RustNotify([str(foo), str(bar)], False)

    (tmp_path / 'missed.txt').write_text('foobar')
    (foo / 'foo.txt').write_text('foobar')
    (bar / 'foo.txt').write_text('foobar')

    assert watcher.watch(200, 50, None) == {(1, str(foo / 'foo.txt')), (1, str(bar / 'foo.txt'))}
