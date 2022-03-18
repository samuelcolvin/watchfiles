from pathlib import Path

import pytest

from watchgod._rust_notify import RustNotify


def test_add(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)
    (test_dir / 'foo.txt').write_text('foobar')

    assert watcher.watch(200, 50, None) == {(1, str((test_dir / 'foo.txt')))}


def test_modify(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    # notify those files
    (test_dir / 'a.txt').write_text('bar')
    (test_dir / 'b.txt').chmod(0o444)

    assert watcher.watch(200, 50, None) == {
        (2, str((test_dir / 'a.txt'))),
        (2, str((test_dir / 'b.txt'))),
    }


def test_delete(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    # notify those files
    (test_dir / 'c.txt').unlink()

    assert watcher.watch(200, 50, None) == {
        (3, str((test_dir / 'c.txt'))),
    }


def test_does_not_exist(tmp_path: Path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError, match='No path was found.'):
        RustNotify([str(p)], False)
