import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING

import anyio
import pytest

from watchfiles import Change, awatch, watch
from watchfiles.main import _calc_async_timeout

if TYPE_CHECKING:
    from conftest import MockRustType

try:
    from exceptiongroup import BaseExceptionGroup
except ImportError:
    # outherwise BaseExceptionGroup should be in builtins
    pass


def test_watch(tmp_path: Path, write_soon):
    sleep(0.05)
    write_soon(tmp_path / 'foo.txt')
    changes = None
    for changes in watch(tmp_path, debounce=50, step=10, watch_filter=None):
        break

    assert changes == {(Change.added, str(tmp_path / 'foo.txt'))}


def test_wait_stop_event(tmp_path: Path, write_soon):
    sleep(0.05)
    write_soon(tmp_path / 'foo.txt')

    stop_event = threading.Event()
    for changes in watch(tmp_path, debounce=50, step=10, watch_filter=None, stop_event=stop_event):
        assert changes == {(Change.added, str(tmp_path / 'foo.txt'))}
        stop_event.set()


async def test_awatch(tmp_path: Path, write_soon):
    sleep(0.05)
    write_soon(tmp_path / 'foo.txt')
    async for changes in awatch(tmp_path, debounce=50, step=10, watch_filter=None):
        assert changes == {(Change.added, str(tmp_path / 'foo.txt'))}
        break


@pytest.mark.filterwarnings('ignore::DeprecationWarning')
async def test_await_stop_event(tmp_path: Path, write_soon):
    sleep(0.05)
    write_soon(tmp_path / 'foo.txt')
    stop_event = anyio.Event()
    async for changes in awatch(tmp_path, debounce=50, step=10, watch_filter=None, stop_event=stop_event):
        assert changes == {(Change.added, str(tmp_path / 'foo.txt'))}
        stop_event.set()


def test_watch_raise_interrupt(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'foo.txt')}], exit_code='signal')

    w = watch('.', raise_interrupt=True)
    assert next(w) == {(Change.added, 'foo.txt')}
    with pytest.raises(KeyboardInterrupt):
        next(w)


def test_watch_dont_raise_interrupt(mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('WARNING', 'watchfiles')
    mock_rust_notify([{(1, 'foo.txt')}], exit_code='signal')

    w = watch('.', raise_interrupt=False)
    assert next(w) == {(Change.added, 'foo.txt')}
    with pytest.raises(StopIteration):
        next(w)

    assert caplog.text == 'watchfiles.main WARNING: KeyboardInterrupt caught, stopping watch\n'


@contextmanager
def mock_open_signal_receiver(signal):
    async def signals():
        yield signal

    yield signals()


async def test_awatch_unexpected_signal(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'foo.txt')}], exit_code='signal')

    count = 0
    with pytest.raises(RuntimeError, match='watch thread unexpectedly received a signal'):
        async for _ in awatch('.'):
            count += 1

    assert count == 1


async def test_awatch_interrupt_warning(mock_rust_notify: 'MockRustType', caplog):
    mock_rust_notify([{(1, 'foo.txt')}])

    count = 0
    with pytest.warns(DeprecationWarning, match='raise_interrupt is deprecated, KeyboardInterrupt will cause this'):
        async for _ in awatch('.', raise_interrupt=False):
            count += 1

    assert count == 1


def test_watch_no_yield(mock_rust_notify: 'MockRustType', caplog):
    mock = mock_rust_notify([{(1, 'spam.pyc')}, {(1, 'spam.py'), (2, 'ham.txt')}])

    caplog.set_level('INFO', 'watchfiles')
    assert next(watch('.')) == {(Change.added, 'spam.py'), (Change.modified, 'ham.txt')}
    assert mock.watch_count == 2
    assert caplog.text == 'watchfiles.main INFO: 2 changes detected\n'


async def test_awatch_no_yield(mock_rust_notify: 'MockRustType', caplog):
    mock = mock_rust_notify([{(1, 'spam.pyc')}, {(1, 'spam.py')}])

    caplog.set_level('DEBUG', 'watchfiles')
    changes = None
    async for changes in awatch('.'):
        pass

    assert changes == {(Change.added, 'spam.py')}
    assert mock.watch_count == 2
    assert caplog.text == (
        "watchfiles.main DEBUG: all changes filtered out, raw_changes={(1, 'spam.pyc')}\n"
        "watchfiles.main DEBUG: 1 change detected: {(<Change.added: 1>, 'spam.py')}\n"
    )


def test_watch_timeout(mock_rust_notify: 'MockRustType', caplog):
    mock = mock_rust_notify(['timeout', {(1, 'spam.py')}])

    caplog.set_level('DEBUG', 'watchfiles')
    change_list = []
    for changes in watch('.'):
        change_list.append(changes)

    assert change_list == [{(Change.added, 'spam.py')}]
    assert mock.watch_count == 2
    assert caplog.text == (
        'watchfiles.main DEBUG: rust notify timeout, continuing\n'
        "watchfiles.main DEBUG: 1 change detected: {(<Change.added: 1>, 'spam.py')}\n"
    )


def test_watch_yield_on_timeout(mock_rust_notify: 'MockRustType'):
    mock = mock_rust_notify(['timeout', {(1, 'spam.py')}])

    change_list = []
    for changes in watch('.', yield_on_timeout=True):
        change_list.append(changes)

    assert change_list == [set(), {(Change.added, 'spam.py')}]
    assert mock.watch_count == 2


async def test_awatch_timeout(mock_rust_notify: 'MockRustType', caplog):
    mock = mock_rust_notify(['timeout', {(1, 'spam.py')}])

    caplog.set_level('DEBUG', 'watchfiles')
    change_list = []
    async for changes in awatch('.'):
        change_list.append(changes)

    assert change_list == [{(Change.added, 'spam.py')}]
    assert mock.watch_count == 2
    assert caplog.text == (
        'watchfiles.main DEBUG: rust notify timeout, continuing\n'
        "watchfiles.main DEBUG: 1 change detected: {(<Change.added: 1>, 'spam.py')}\n"
    )


async def test_awatch_yield_on_timeout(mock_rust_notify: 'MockRustType'):
    mock = mock_rust_notify(['timeout', {(1, 'spam.py')}])

    change_list = []
    async for changes in awatch('.', yield_on_timeout=True):
        change_list.append(changes)

    assert change_list == [set(), {(Change.added, 'spam.py')}]
    assert mock.watch_count == 2


@pytest.mark.skipif(sys.platform == 'win32', reason='different on windows')
def test_calc_async_timeout_posix():
    assert _calc_async_timeout(123) == 123
    assert _calc_async_timeout(None) == 5_000


@pytest.mark.skipif(sys.platform != 'win32', reason='different on windows')
def test_calc_async_timeout_win():
    assert _calc_async_timeout(123) == 123
    assert _calc_async_timeout(None) == 1_000


class MockRustNotifyRaise:
    def __init__(self):
        self.i = 0

    def watch(self, *args):
        if self.i == 1:
            raise KeyboardInterrupt('test error')
        self.i += 1
        return {(Change.added, 'spam.py')}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        pass


async def test_awatch_interrupt_raise(mocker):
    mocker.patch('watchfiles.main.RustNotify', return_value=MockRustNotifyRaise())

    count = 0
    stop_event = threading.Event()
    with pytest.raises(BaseExceptionGroup) as exc_info:
        async for _ in awatch('.', stop_event=stop_event):
            count += 1

    assert len(exc_info.value.exceptions) == 1
    exc = exc_info.value.exceptions[0]
    assert isinstance(exc, KeyboardInterrupt)
    assert exc.args == ('test error',)

    # event is set because it's set while handling the KeyboardInterrupt
    assert stop_event.is_set()
    assert count == 1
