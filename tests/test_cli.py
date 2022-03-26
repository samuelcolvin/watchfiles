import sys
from pathlib import Path

import pytest
from dirty_equals import FunctionCheck, IsInstance

from watchfiles import DefaultFilter, PythonFilter
from watchfiles.cli import cli

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='many tests fail on windows')


def test_function(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(str(tmp_path), 'os.getcwd')
    mock_run_process.assert_called_once_with(
        tmp_path,
        target=['os.getcwd'],
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
    )


def test_ignore_paths(mocker, tmp_work_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(
        '.',
        '--ignore-paths',
        '/foo/bar,/apple/banana',
        '--filter',
        'python',
        'os.getcwd',
    )
    mock_run_process.assert_called_once_with(
        Path(str(tmp_work_path)),
        target=['os.getcwd'],
        target_type='function',
        watch_filter=(
            IsInstance(PythonFilter)
            & FunctionCheck(lambda f: f.extensions == ('.py', '.pyx', '.pyd'))
            & FunctionCheck(lambda f: f._ignore_paths == ('/foo/bar', '/apple/banana'))
        ),
        debug=False,
    )


class SysError(RuntimeError):
    pass


def test_invalid_import1(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('.', 'foo.bar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == "ImportError: No module named 'foo'\n"


def test_invalid_import2(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('.', 'pprint.foobar')

    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: Module "pprint" does not define a "foobar" attribute\n'


def test_invalid_path(mocker, capsys):
    sys_exit = mocker.patch('watchfiles.cli.sys.exit', side_effect=SysError)
    with pytest.raises(SysError):
        cli('/does/not/exist', 'os.getcwd')

    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'path "/does/not/exist" does not exist\n'


def test_command(mocker, tmp_work_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli('.', 'foo', '--bar', '-V', '3')
    mock_run_process.assert_called_once_with(
        tmp_work_path,
        target=['foo', '--bar', '-V', '3'],
        target_type='command',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
    )


args_list = [
    ([], []),
    (['--foo', 'bar'], []),
    (['--foo', 'bar', '-a'], []),
    (['--foo', 'bar', '--args'], []),
    (['--foo', 'bar', '-a', '--foo', 'bar'], ['--foo', 'bar']),
    (['--foo', 'bar', '-f', 'b', '--args', '-f', '-b', '-z', 'x'], ['-f', '-b', '-z', 'x']),
]


def test_verbose(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(str(tmp_path), '--verbosity', 'debug', 'os.getcwd')
    mock_run_process.assert_called_once_with(
        tmp_path,
        target=['os.getcwd'],
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=True,
    )


def test_filter_all(mocker, tmp_path, capsys):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(str(tmp_path), '--filter', 'all', '--ignore-paths', 'foo', 'os.getcwd')
    mock_run_process.assert_called_once_with(
        tmp_path,
        target=['os.getcwd'],
        target_type='function',
        watch_filter=None,
        debug=False,
    )
    out, err = capsys.readouterr()
    assert out == ''
    assert '"--ignore-paths" argument ignored as "all" filter was selected\n' in err


def test_filter_default(mocker, tmp_path):
    mocker.patch('watchfiles.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchfiles.cli.run_process')
    cli(str(tmp_path), '--filter', 'default', 'os.getcwd')
    mock_run_process.assert_called_once_with(
        tmp_path,
        target=['os.getcwd'],
        target_type='function',
        watch_filter=IsInstance(DefaultFilter, only_direct_instance=True),
        debug=False,
    )
