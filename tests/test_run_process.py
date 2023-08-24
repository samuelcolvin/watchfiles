import os
import subprocess
import sys
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dirty_equals import IsStr

from watchfiles import arun_process, run_process
from watchfiles.main import Change
from watchfiles.run import detect_target_type, import_string, run_function, set_tty, split_cmd, start_process

if TYPE_CHECKING:
    from conftest import MockRustType


class FakeProcess(SpawnProcess):
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self._exitcode = exitcode
        self._pid = pid

    @property
    def exitcode(self):
        return self._exitcode

    @property
    def pid(self):
        return self._pid

    def start(self):
        pass

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_alive_terminates(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('DEBUG', 'watchfiles')
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_popen = mocker.patch('watchfiles.run.subprocess.Popen', return_value=FakePopen())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=os.getcwd, debounce=5, grace_period=0.01, step=1) == 1
    assert mock_spawn_process.call_count == 2
    assert mock_popen.call_count == 0
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert 'watchfiles.main DEBUG: running "<built-in function getcwd>" as function\n' in caplog.text
    assert 'sleeping for 0.01 seconds before watching for changes' in caplog.text


def test_dead_callback(mocker, mock_rust_notify: 'MockRustType'):
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess(is_alive=False))
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}, {(1, '/path/to/foobar.py')}])

    c = mocker.MagicMock()

    assert run_process('/x/y/z', target=object(), callback=c, debounce=5, step=1) == 2
    assert mock_spawn_process.call_count == 3
    assert mock_kill.call_count == 0
    assert c.call_count == 2
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})


@pytest.mark.skipif(sys.platform != 'win32', reason='no need to test this except on windows')
def test_split_cmd_non_posix():
    assert split_cmd('C:\\Users\\default\\AppData\\Local\\Programs\\Python\\Python311\\python.exe -V') == [
        'C:\\Users\\default\\AppData\\Local\\Programs\\Python\\Python311\\python.exe',
        '-V',
    ]


@pytest.mark.skipif(sys.platform == 'win32', reason='no need to test this on windows')
def test_split_cmd_posix():
    assert split_cmd('/usr/bin/python3 -v') == ['/usr/bin/python3', '-v']


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_alive_doesnt_terminate(mocker, mock_rust_notify: 'MockRustType'):
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess(exitcode=None))
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 2
    assert mock_kill.call_count == 4  # 2 kills in loop (graceful and termination) + 2 final kills


class FakeProcessTimeout(FakeProcess):
    def join(self, wait):
        if wait == 'sigint_timeout':
            raise subprocess.TimeoutExpired('/x/y/z', wait)


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_sigint_timeout(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('WARNING', 'watchfiles')
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcessTimeout())

    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1, sigint_timeout='sigint_timeout') == 1
    assert mock_spawn_process.call_count == 2
    assert mock_kill.call_count == 2
    assert "SIGINT timed out after 'sigint_timeout' seconds" in caplog.text


def test_start_process(mocker):
    mock_process = mocker.patch('watchfiles.run.spawn_context.Process')
    v = object()
    start_process(v, 'function', (1, 2, 3), {})
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})
    assert os.getenv('WATCHFILES_CHANGES') == '[]'


def test_start_process_env(mocker):
    mock_process = mocker.patch('watchfiles.run.spawn_context.Process')
    v = object()
    changes = [(Change.added, 'a.py'), (Change.modified, 'b.py'), (Change.deleted, 'c.py')]  # use a list to keep order
    start_process(v, 'function', (1, 2, 3), {}, changes)
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})
    assert os.getenv('WATCHFILES_CHANGES') == '[["added", "a.py"], ["modified", "b.py"], ["deleted", "c.py"]]'


def test_function_string_not_win(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('DEBUG', 'watchfiles')
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target='os.getcwd', debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 2

    # get_tty_path returns None on windows
    tty_path = None if sys.platform == 'win32' else IsStr(regex='/dev/.+')
    mock_spawn_process.assert_called_with(target=run_function, args=('os.getcwd', tty_path, (), {}), kwargs={})

    assert 'watchfiles.main DEBUG: running "os.getcwd" as function\n' in caplog.text


def test_function_list(mocker, mock_rust_notify: 'MockRustType'):
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=['os.getcwd'], debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill


async def test_async_alive_terminates(mocker, mock_rust_notify: 'MockRustType'):
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    callback_calls = []

    async def c(changes):
        callback_calls.append(changes)

    assert await arun_process('/x/y/async', target=object(), callback=c, debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert callback_calls == [{(Change.added, '/path/to/foobar.py')}]


async def test_async_sync_callback(mocker, mock_rust_notify: 'MockRustType'):
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foo.py')}, {(2, '/path/to/bar.py')}])

    callback_calls = []

    v = await arun_process(
        '/x/y/async',
        target='os.getcwd',
        target_type='function',
        callback=callback_calls.append,
        grace_period=0.01,
        debounce=5,
        step=1,
    )
    assert v == 2
    assert mock_spawn_process.call_count == 3
    assert mock_kill.call_count == 3
    assert callback_calls == [{(Change.added, '/path/to/foo.py')}, {(Change.modified, '/path/to/bar.py')}]


def test_run_function(tmp_work_path: Path, create_test_function):
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, None, (), {})
    assert (tmp_work_path / 'sentinel').exists()


def test_run_function_tty(tmp_work_path: Path, create_test_function):
    # could this cause problems by changing sys.stdin?
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, '/dev/tty', (), {})
    assert (tmp_work_path / 'sentinel').exists()


def test_set_tty_error():
    with set_tty('/foo/bar'):
        pass


class FakePopen:
    def __init__(self, is_alive=True, returncode=1, pid=123):
        self._is_alive = is_alive
        self.returncode = returncode
        self.pid = pid

    def poll(self):
        return None if self._is_alive else self.returncode

    def wait(self, wait):
        pass


def test_command(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('DEBUG', 'watchfiles')
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_popen = mocker.patch('watchfiles.run.subprocess.Popen', return_value=FakePopen())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target='echo foobar', debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 0
    assert mock_popen.call_count == 2
    mock_popen.assert_called_with(['echo', 'foobar'])
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert 'watchfiles.main DEBUG: running "echo foobar" as command\n' in caplog.text


def test_command_with_args(mocker, mock_rust_notify: 'MockRustType', caplog):
    caplog.set_level('INFO', 'watchfiles')
    mock_spawn_process = mocker.patch('watchfiles.run.spawn_context.Process', return_value=FakeProcess())
    mock_popen = mocker.patch('watchfiles.run.subprocess.Popen', return_value=FakePopen())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target='echo foobar', args=(1, 2), target_type='command', debounce=5, step=1) == 1
    assert mock_spawn_process.call_count == 0
    assert mock_popen.call_count == 2
    mock_popen.assert_called_with(['echo', 'foobar'])
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert 'watchfiles.main WARNING: ignoring args and kwargs for "command" target\n' in caplog.text


def test_import_string():
    assert import_string('os.getcwd') == os.getcwd

    with pytest.raises(ImportError, match='"os" doesn\'t look like a module path'):
        import_string('os')


@pytest.mark.parametrize(
    'target, expected',
    [
        ('os.getcwd', 'function'),
        (os.getcwd, 'function'),
        ('foobar.py', 'command'),
        ('foobar.sh', 'command'),
        ('foobar.pyt', 'function'),
        ('foo bar', 'command'),
    ],
)
def test_detect_target_type(target, expected):
    assert detect_target_type(target) == expected
