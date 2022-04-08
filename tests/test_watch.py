import asyncio
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING

import anyio
import pytest

from watchfiles import Change, awatch, watch

if TYPE_CHECKING:
    from conftest import MockRustType


def test_watch(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    changes = None
    for changes in watch(tmp_path, watch_filter=None):
        break

    assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}


def test_wait_stop_event(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')

    stop_event = threading.Event()
    for changes in watch(tmp_path, watch_filter=None, stop_event=stop_event):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        stop_event.set()


async def test_awatch(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    async for changes in awatch(tmp_path, watch_filter=None):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        break


async def test_await_stop_event(tmp_path: Path, write_soon):
    sleep(0.1)
    write_soon(tmp_path / 'foo.txt')
    stop_event = anyio.Event()
    async for changes in awatch(tmp_path, watch_filter=None, stop_event=stop_event):
        assert changes == {(Change.added, str((tmp_path / 'foo.txt')))}
        stop_event.set()


def test_watch_interrupt(mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'foo.txt')}])

    w = watch('.', raise_interrupt=True)
    assert next(w) == {(Change.added, 'foo.txt')}
    with pytest.raises(KeyboardInterrupt):
        next(w)


@contextmanager
def mock_open_signal_receiver(signal):
    async def signals():
        yield signal

    yield signals()


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
async def test_awatch_interrupt_raise(mocker, mock_rust_notify: 'MockRustType'):
    mocker.patch('watchfiles.main.anyio.open_signal_receiver', side_effect=mock_open_signal_receiver)
    mock_rust_notify([{(1, 'foo.txt')}])

    count = 0
    with pytest.raises(KeyboardInterrupt):
        async for _ in awatch('.'):
            count += 1

    assert count == 1


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
async def test_awatch_interrupt_warning(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('INFO', 'watchfiles')
    mocker.patch('watchfiles.main.anyio.open_signal_receiver', side_effect=mock_open_signal_receiver)
    mock_rust_notify([{(1, 'foo.txt')}])

    count = 0
    async for _ in awatch('.', raise_interrupt=False):
        count += 1

    assert count == 1
    assert 'WARNING: KeyboardInterrupt caught, stopping awatch' in caplog.text


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
    assert caplog.text == "watchfiles.main DEBUG: 1 change detected: {(<Change.added: 1>, 'spam.py')}\n"


async def test_watch_directory(tmp_path: Path):
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.4)
        stop_event.set()

    async def change_dir():
        await asyncio.sleep(0.1)
        (tmp_path / 'file0').write_text('foo')
        await asyncio.sleep(0.1)
        with open(tmp_path / 'file0', 'a') as f:
            f.write(' bar')
        await asyncio.sleep(0.1)
        (tmp_path / 'file0').unlink()

    tasks = [asyncio.create_task(stop_soon()), asyncio.create_task(change_dir())]

    changes = []
    async for change in awatch(tmp_path, stop_event=stop_event, step=1):
        changes.append(change)

    assert changes == [
        {(Change.added, str(tmp_path / 'file0'))},
        {(Change.modified, str(tmp_path / 'file0'))},
        {(Change.deleted, str(tmp_path / 'file0'))},
    ]

    await asyncio.gather(*tasks)
