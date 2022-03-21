import sys

import pytest

from watchgod import arun_process, run_process
from watchgod.main import Change, _start_process

from .conftest import MockRustType


class FakeProcess:
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self.exitcode = exitcode
        self.pid = pid

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_alive_terminates(mocker, mock_rust_notify: MockRustType):
    mock_start_process = mocker.patch('watchgod.main._start_process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchgod.main.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill


def test_dead_callback(mocker, mock_rust_notify: MockRustType):
    mock_start_process = mocker.patch('watchgod.main._start_process', return_value=FakeProcess(is_alive=False))
    mock_kill = mocker.patch('watchgod.main.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}, {(1, '/path/to/foobar.py')}])

    c = mocker.MagicMock()

    assert run_process('/x/y/z', target=object(), callback=c, debounce=5, step=1) == 2
    assert mock_start_process.call_count == 3
    assert mock_kill.call_count == 0
    assert c.call_count == 2
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_alive_doesnt_terminate(mocker, mock_rust_notify: MockRustType):
    mock_start_process = mocker.patch('watchgod.main._start_process', return_value=FakeProcess(exitcode=None))
    mock_kill = mocker.patch('watchgod.main.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 4  # 2 kills in loop (graceful and termination) + 2 final kills


def test_start_process(mocker):
    mock_process = mocker.patch('watchgod.main.spawn_context.Process')
    v = object()
    _start_process(v, (1, 2, 3), {})
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})


@pytest.mark.skipif(sys.version_info < (3, 8), reason='AsyncMock unavailable')
async def test_async_alive_terminates(mocker, mock_rust_notify: MockRustType):
    mock_start_process = mocker.patch('watchgod.main._start_process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchgod.main.os.kill')
    c = mocker.AsyncMock(return_value=1)
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert await arun_process('/x/y/async', target=object(), callback=c, debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert c.call_count == 1
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})
