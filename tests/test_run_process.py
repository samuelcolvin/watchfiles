from watchgod import run_process
from watchgod.main import _start_process


class FakeWatcher:
    def __init__(self, path):
        self._check = 0
        self.files = [1, 2, 3]

    def check(self):
        self._check += 1
        if self._check > 1:
            raise KeyboardInterrupt
        else:
            return {'x'}


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

    assert run_process('/x/y/z', object(), watcher_cls=FakeWatcher, debounce=5, min_sleep=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 1


def test_dead(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess(is_alive=False)
    mock_kill = mocker.patch('watchgod.main.os.kill')

    assert run_process('/x/y/z', object(), watcher_cls=FakeWatcher, debounce=5, min_sleep=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 0


def test_alive_doesnt_terminate(mocker):
    mock_start_process = mocker.patch('watchgod.main._start_process')
    mock_start_process.return_value = FakeProcess(exitcode=None)
    mock_kill = mocker.patch('watchgod.main.os.kill')

    assert run_process('/x/y/z', object(), watcher_cls=FakeWatcher, debounce=5, min_sleep=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2


def test_start_process(mocker):
    mock_process = mocker.patch('watchgod.main.Process')
    v = object()
    _start_process(v, (1, 2, 3), {})
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})
