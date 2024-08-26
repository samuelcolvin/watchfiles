import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from watchfiles._rust_notify import RustNotify
from watchfiles.main import _default_ignore_permission_denied

if TYPE_CHECKING:
    from .conftest import SetEnv

skip_unless_linux = pytest.mark.skipif('linux' not in sys.platform, reason='avoid differences on other systems')
skip_windows = pytest.mark.skipif(sys.platform == 'win32', reason='fails on Windows')


def test_add(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, True, False)
    (test_dir / 'new_file.txt').write_text('foobar')

    assert watcher.watch(200, 50, 500, None) == {(1, str(test_dir / 'new_file.txt'))}


def test_add_non_recursive(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, False, False)

    (test_dir / 'new_file_non_recursive.txt').write_text('foobar')
    (test_dir / 'dir_a' / 'new_file_non_recursive.txt').write_text('foobar')

    assert watcher.watch(200, 50, 500, None) == {(1, str(test_dir / 'new_file_non_recursive.txt'))}


def test_close(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, True, False)
    assert repr(watcher).startswith('RustNotify(Recommended(\n')

    watcher.close()

    assert repr(watcher) == 'RustNotify(None)'
    with pytest.raises(RuntimeError, match='RustNotify watcher closed'):
        watcher.watch(200, 50, 500, None)


def test_modify_write(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, True, False)

    (test_dir / 'a.txt').write_text('this is new')

    assert watcher.watch(200, 50, 500, None) == {(2, str(test_dir / 'a.txt'))}


def test_modify_write_non_recursive(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, False, False)

    (test_dir / 'a_non_recursive.txt').write_text('this is new')
    (test_dir / 'dir_a' / 'a_non_recursive.txt').write_text('this is new')

    assert watcher.watch(200, 50, 500, None) == {
        (2, str(test_dir / 'a_non_recursive.txt')),
    }


@skip_windows
def test_modify_chmod(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 0, True, False)

    (test_dir / 'b.txt').chmod(0o444)

    assert watcher.watch(200, 50, 500, None) == {(2, str(test_dir / 'b.txt'))}


def test_delete(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    (test_dir / 'c.txt').unlink()

    assert watcher.watch(200, 50, 500, None) == {
        (3, str(test_dir / 'c.txt')),
    }


def test_delete_non_recursive(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False, False, 0, False, False)

    (test_dir / 'c_non_recursive.txt').unlink()
    (test_dir / 'dir_a' / 'c_non_recursive.txt').unlink()

    assert watcher.watch(200, 50, 500, None) == {
        (3, str(test_dir / 'c_non_recursive.txt')),
    }


def test_move_in(test_dir: Path):
    # can't use tmp_path as it causes problems on Windows (different drive), and macOS (delayed events)
    src = test_dir / 'dir_a'
    assert src.is_dir()
    dst = test_dir / 'dir_b'
    assert dst.is_dir()
    move_files = 'a.txt', 'b.txt'

    watcher = RustNotify([str(dst)], False, False, 0, True, False)

    for f in move_files:
        (src / f).rename(dst / f)

    assert watcher.watch(200, 50, 500, None) == {
        (1, str(dst / 'a.txt')),
        (1, str(dst / 'b.txt')),
    }


def test_move_out(test_dir: Path):
    # can't use tmp_path as it causes problems on Windows (different drive), and macOS (delayed events)
    src = test_dir / 'dir_a'
    dst = test_dir / 'dir_b'
    move_files = 'c.txt', 'd.txt'

    watcher = RustNotify([str(src)], False, False, 0, True, False)

    for f in move_files:
        (src / f).rename(dst / f)

    assert watcher.watch(200, 50, 500, None) == {
        (3, str(src / 'c.txt')),
        (3, str(src / 'd.txt')),
    }


def test_move_internal(test_dir: Path):
    # can't use tmp_path as it causes problems on Windows (different drive), and macOS (delayed events)
    src = test_dir / 'dir_a'
    dst = test_dir / 'dir_b'
    move_files = 'e.txt', 'f.txt'

    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    for f in move_files:
        (src / f).rename(dst / f)

    expected_changes = {
        (3, str(src / 'e.txt')),
        (3, str(src / 'f.txt')),
        (1, str(dst / 'e.txt')),
        (1, str(dst / 'f.txt')),
    }
    if sys.platform == 'win32':
        # Windows adds a "modified" event for the dst directory
        expected_changes.add((2, str(dst)))

    assert watcher.watch(200, 50, 500, None) == expected_changes


def test_does_not_exist(tmp_path: Path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError):
        RustNotify([str(p)], False, False, 0, True, False)


@skip_unless_linux
def test_does_not_exist_message(tmp_path: Path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError, match='(No such file or directory|No path was found.)'):
        RustNotify([str(p)], False, False, 0, True, False)


def test_does_not_exist_polling(tmp_path: Path):
    p = tmp_path / 'missing'
    with pytest.raises(FileNotFoundError, match='No such file or directory'):
        RustNotify([str(p)], False, True, 0, True, False)


def test_rename(test_dir: Path):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

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
    watcher = RustNotify([str(foo), str(bar)], False, False, 0, True, False)

    (tmp_path / 'not_included.txt').write_text('foobar')
    (foo / 'foo.txt').write_text('foobar')
    (bar / 'foo.txt').write_text('foobar')

    changes = watcher.watch(200, 50, 500, None)
    # can compare directly since on macos creating the foo and bar directories is included in changes
    assert (1, str(foo / 'foo.txt')) in changes
    assert (1, str(bar / 'foo.txt')) in changes
    assert not any('not_included.txt' in p for c, p in changes)


def test_wrong_type_event(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    with pytest.raises(AttributeError, match="'object' object has no attribute 'is_set'"):
        watcher.watch(100, 1, 500, object())


def test_wrong_type_event_is_set(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)
    event = type('BadEvent', (), {'is_set': 123})()

    with pytest.raises(TypeError, match="'int' object is not callable"):
        watcher.watch(100, 1, 500, event)


@skip_unless_linux
def test_return_timeout(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    with time_taken(40, 70):
        assert watcher.watch(20, 1, 50, None) == 'timeout'


class AbstractEvent:
    def __init__(self, is_set: bool):
        self._is_set = is_set

    def is_set(self) -> bool:
        return self._is_set


@skip_unless_linux
def test_return_event_set(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    with time_taken(0, 20):
        assert watcher.watch(100, 1, 500, AbstractEvent(True)) == 'stop'


@skip_unless_linux
def test_return_event_unset(test_dir: Path, time_taken):
    watcher = RustNotify([str(test_dir)], False, False, 0, True, False)

    with time_taken(40, 70):
        assert watcher.watch(20, 1, 50, AbstractEvent(False)) == 'timeout'


@skip_unless_linux
def test_return_debounce_no_timeout(test_dir: Path, time_taken):
    # would return sooner if the timeout logic wasn't in an else clause
    watcher = RustNotify([str(test_dir)], True, False, 0, True, False)
    (test_dir / 'debounce.txt').write_text('foobar')

    with time_taken(50, 130):
        assert watcher.watch(100, 50, 20, None) == {(1, str(test_dir / 'debounce.txt'))}


@skip_unless_linux
def test_rename_multiple_inside(tmp_path: Path):
    d1 = tmp_path / 'd1'

    d1.mkdir()
    f1 = d1 / '1.txt'
    f1.write_text('1')
    f2 = d1 / '2.txt'
    f2.write_text('2')
    f3 = d1 / '3.txt'
    f3.write_text('3')

    d2 = tmp_path / 'd2'
    d2.mkdir()

    watcher_all = RustNotify([str(tmp_path)], False, False, 0, True, False)

    f1.rename(d2 / '1.txt')
    f2.rename(d2 / '2.txt')
    f3.rename(d2 / '3.txt')

    assert watcher_all.watch(200, 50, 500, None) == {
        (3, str(f1)),
        (3, str(f2)),
        (3, str(f3)),
        (1, str(d2 / '1.txt')),
        (1, str(d2 / '2.txt')),
        (1, str(d2 / '3.txt')),
    }


@skip_windows
def test_polling(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, True, 100, True, False)
    (test_dir / 'test_polling.txt').write_text('foobar')

    changes = watcher.watch(200, 50, 500, None)
    assert (1, str(test_dir / 'test_polling.txt')) in changes  # sometimes has an event modify too


def test_not_polling_repr(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, False, 123, True, False)
    r = repr(watcher)
    assert r.startswith('RustNotify(Recommended(\n')


def test_polling_repr(test_dir: Path):
    watcher = RustNotify([str(test_dir)], True, True, 123, True, False)
    r = repr(watcher)
    assert r.startswith('RustNotify(Poll(\n    PollWatcher {\n')
    assert 'delay: Some( 123ms, )' in re.sub(r'\s+', ' ', r)


@skip_unless_linux
def test_ignore_permission_denied():
    path = os.getenv('WATCHFILES_TEST_PERMISSION_DENIED_PATH') or '/'

    RustNotify([path], False, False, 0, True, True)

    with pytest.raises(PermissionError):
        RustNotify([path], False, False, 0, True, False)


@pytest.mark.parametrize(
    'env_var,arg,expected',
    [
        (None, True, True),
        (None, False, False),
        (None, None, False),
        ('', True, True),
        ('', False, False),
        ('', None, False),
        ('1', True, True),
        ('1', False, False),
        ('1', None, True),
    ],
)
def test_default_ignore_permission_denied(env: 'SetEnv', env_var, arg, expected):
    if env_var is not None:
        env('WATCHFILES_IGNORE_PERMISSION_DENIED', env_var)
    assert _default_ignore_permission_denied(arg) == expected
