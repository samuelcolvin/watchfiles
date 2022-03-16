import sys

import pytest

from watchgod import arun_process, run_process
from watchgod.main import Change, _start_process


class MockNotify:
    def __init__(self, count: int):
        self.count = count
        self.step = 0

    def watch(self, debounce_ms: int, step_ms: int, cancel_event):
        self.step += 1
        if self.step <= self.count:
            return {(1, '/path/to/foobar.py')}


class FakeProcess:
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self.exitcode = exitcode
        self.pid = pid

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_alive_terminates(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess()
    mock_kill = mocker.patch('watchgod.main.os.kill')
    mocker.patch('watchgod.main.RustNotify', return_value=MockNotify(1))

    assert run_process('/x/y/z', object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill


def test_dead_callback(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess(is_alive=False)
    mock_kill = mocker.patch('watchgod.main.os.kill')
    c = mocker.MagicMock()
    mocker.patch('watchgod.main.RustNotify', return_value=MockNotify(2))

    assert run_process('/x/y/z', object(), callback=c, debounce=5, step=1) == 2
    assert mock_start_process.call_count == 3
    assert mock_kill.call_count == 0
    assert c.call_count == 2
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_alive_doesnt_terminate(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess(exitcode=None)
    mock_kill = mocker.patch('watchgod.main.os.kill')
    mocker.patch('watchgod.main.RustNotify', return_value=MockNotify(1))

    assert run_process('/x/y/z', object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 4  # 2 kills in loop (graceful and termination) + 2 final kills


def test_start_process(mocker):
    mock_process = mocker.patch('watchgod.main.spawn_context.Process')
    v = object()
    _start_process(v, (1, 2, 3), {})
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})


@pytest.mark.skipif(sys.version_info < (3, 8), reason='AsyncMock unavailable')
async def test_async_alive_terminates(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess()
    mock_kill = mocker.patch('watchgod.main.os.kill')
    c = mocker.AsyncMock(return_value=1)
    mocker.patch('watchgod.main.RustNotify', return_value=MockNotify(1))

    assert await arun_process('/x/y/async', object(), callback=c, debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert c.call_count == 1
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})
