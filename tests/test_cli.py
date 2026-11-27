import os
import sys
from pathlib import Path

import pytest
from dirty_equals import HasAttributes, HasLen, IsInstance

from watchfiles import BaseFilter, DefaultFilter, PythonFilter
from watchfiles.cli import build_filter, cli

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='many tests fail on windows')


def test_function(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


def test_ignore_paths(mocker, tmp_work_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(
        '--ignore-paths',
        '/foo/bar,/apple/banana',
        '--filter',
        'python',
        'os.getcwd',
        '.',
    )
    mock_run_process.assert_called_once_with(
        Path(str(tmp_work_path)),
        target='os.getcwd',
        target_type='function',
        watch_filter=(
            IsInstance(PythonFilter)
            & HasAttributes(extensions=('.py', '.pyx', '.pyd'), _ignore_paths=('/foo/bar', '/apple/banana'))
        ),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


class SysError(RuntimeError):
    pass


def test_invalid_import1(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('foo.bar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == "ImportError: No module named 'foo'\n"


def test_invalid_import2(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('pprint.foobar')

    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: Module "pprint" does not define a "foobar" attribute\n'


def test_invalid_path(mocker, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('os.getcwd', '/does/not/exist')

    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'path "/does/not/exist" does not exist\n'


def test_command(mocker, tmp_work_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('foo --bar -V 3', '.')
    mock_run_process.assert_called_once_with(
        tmp_work_path,
        target='foo --bar -V 3',
        target_type='command',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


def test_verbosity(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--verbosity', 'debug', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=True,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


def test_verbose(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--verbose', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=True,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


def test_non_recursive(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--non-recursive', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=False,
        ignore_permission_denied=False,
    )


def test_filter_all(mocker, tmp_path, capsys):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--filter', 'all', '--ignore-paths', 'foo', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=None,
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )
    out, err = capsys.readouterr()
    assert out == ''
    assert '"--ignore-paths" argument ignored as "all" filter was selected\n' in err


def test_filter_default(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--filter', 'default', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


def test_set_type(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--target-type', 'command', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='command',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )


@pytest.mark.parametrize(
    'filter_name,ignore_paths,expected_filter,expected_name',
    [
        ('all', None, None, '(no filter)'),
        (
            'default',
            None,
            IsInstance(DefaultFilter, only_direct_instance=True) & HasAttributes(_ignore_paths=()),
            'DefaultFilter',
        ),
        ('python', None, IsInstance(PythonFilter, only_direct_instance=True), 'PythonFilter'),
        ('watchfiles.PythonFilter', None, IsInstance(PythonFilter, only_direct_instance=True), 'PythonFilter'),
        ('watchfiles.BaseFilter', None, IsInstance(BaseFilter, only_direct_instance=True), 'BaseFilter'),
        ('os.getcwd', None, os.getcwd, '<built-in function getcwd>'),
        (
            'default',
            'foo,bar',
            IsInstance(DefaultFilter, only_direct_instance=True) & HasAttributes(_ignore_paths=HasLen(2)),
            'DefaultFilter',
        ),
    ],
)
def test_build_filter(filter_name, ignore_paths, expected_filter, expected_name):
    assert build_filter(filter_name, ignore_paths) == (expected_filter, expected_name)


def test_build_filter_warning(caplog):
    caplog.set_level('INFO', 'watchfiles')
    watch_filter, name = build_filter('os.getcwd', 'foo')
    assert watch_filter is os.getcwd
    assert name == '<built-in function getcwd>'
    assert caplog.text == (
        'watchfiles.cli WARNING: "--ignore-paths" argument ignored as filter is not a subclass of DefaultFilter\n'
    )


def test_args(mocker, tmp_path, reset_argv, caplog):
    caplog.set_level('INFO', 'watchfiles')
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--args', '--version ', 'os.getcwd', str(tmp_path))

    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )
    assert sys.argv == ['os.getcwd', '--version']
    assert 'WARNING: --args' not in caplog.text


def test_args_command(mocker, tmp_path, caplog):
    caplog.set_level('INFO', 'watchfiles')
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--args', '--version ', 'foobar.sh', str(tmp_path))

    mock_run_process.assert_called_once_with(
        tmp_path,
        target='foobar.sh',
        target_type='command',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=False,
    )
    assert 'WARNING: --args is only used when the target is a function\n' in caplog.text


def test_ignore_permission_denied(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('--ignore-permission-denied', 'os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target='os.getcwd',
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
        grace_period=0,
        sigint_timeout=5,
        sigkill_timeout=1,
        recursive=True,
        ignore_permission_denied=True,
    )
