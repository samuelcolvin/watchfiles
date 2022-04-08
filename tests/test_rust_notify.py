import sys
from pathlib import Path

import pytest

from watchfiles._rust_notify import RustNotify


def test_add(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True)
    (test_dir / 'foo.txt').write_text('foobar')

    assert watcher.watch(200, 50, 500, None) == {(1, str(test_dir / 'foo.txt'))}


def test_modify_write(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True)

    (test_dir / 'a.txt').write_text('this is new')

    assert watcher.watch(200, 50, 500, None) == {(2, str(test_dir / 'a.txt'))}


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_modify_chmod(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True)

    (test_dir / 'a.txt').chmod(0o444)

    assert watcher.watch(200, 50, 500, None) == {(2, str(test_dir / 'a.txt'))}


def test_delete(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False)

    # notify those files
    (test_dir / 'c.txt').unlink()

    assert watcher.watch(200, 50, 500, None) == {
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

    assert watcher.watch(200, 50, 500, None) == {
        (3, str(f)),
        (1, str(test_dir / 'a.new')),
    }


def test_watch_multiple(tmp_path: Path):
    foo = tmp_path / 'foo'
    foo.mkdir()
    bar = tmp_path / 'bar'
    bar.mkdir()
    watcher = RustNotify([str(foo), str(bar)], False)

    (tmp_path / 'not_included.txt').write_text('foobar')
    (foo / 'foo.txt').write_text('foobar')
    (bar / 'foo.txt').write_text('foobar')

    changes = watcher.watch(200, 50, 500, None)
    # can compare directly since on macos creating the foo and bar directories is included in changes
    assert (1, str(foo / 'foo.txt')) in changes
    assert (1, str(bar / 'foo.txt')) in changes
    assert not any('not_included.txt' in p for c, p in changes)


def test_wrong_type_event(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False)

    with pytest.raises(AttributeError, match="'object' object has no attribute 'is_set'"):
        watcher.watch(100, 1, 500, object())


def test_wrong_type_event_is_set(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False)
    event = type('BadEvent', (), {'is_set': 123})()

    with pytest.raises(TypeError, match="'stop_event.is_set' must be callable"):
        watcher.watch(100, 1, 500, event)


skip_unless_linux = pytest.mark.skipif('linux' not in sys.platform, reason='avoid time differences on other platforms')


@skip_unless_linux
def test_return_timeout(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False)

    with time_taken(40, 70):
        assert watcher.watch(20, 1, 50, None) == 'timeout'


class AbstractEvent:
    def __init__(self, is_set: bool):
        self._is_set = is_set

    def is_set(self) -> bool:
        return self._is_set


@skip_unless_linux
def test_return_event_set(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False)

    with time_taken(0, 20):
        assert watcher.watch(100, 1, 500, AbstractEvent(True)) == 'stop'


@skip_unless_linux
def test_return_event_unset(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False)

    with time_taken(40, 70):
        assert watcher.watch(20, 1, 50, AbstractEvent(False)) == 'timeout'


@skip_unless_linux
def test_return_debounce_no_timeout(test_dir: Path, time_taken):
    # would return sooner if the timeout logic wasn't in an else clause
    watcher = RustNotify([str(test_dir)], True)
    (test_dir / 'debounce.txt').write_text('foobar')

    with time_taken(50, 130):
        assert watcher.watch(100, 50, 20, None) == {(1, str(test_dir / 'debounce.txt'))}
