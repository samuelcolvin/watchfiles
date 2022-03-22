import sys
from pathlib import Path

import pytest
from dirty_equals import FunctionCheck, IsInstance

from watchgod import PythonFilter
from watchgod.cli import callback, cli, run_function, set_tty, sys_argv

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='many tests fail on windows')


def test_simple(mocker, tmp_path):
    mocker.patch('watchgod.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('os.getcwd', str(tmp_path))
    mock_run_process.assert_called_once_with(
        tmp_path,
        target=run_function,
        args=('os.getcwd', '/path/to/tty'),
        callback=callback,
        watch_filter=IsInstance(PythonFilter),
    )


def test_ignore_extensions(mocker, tmp_work_path):
    mocker.patch('watchgod.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli(
        'os.getcwd',
        str(tmp_work_path),
        # '--ignore-paths',
        # 'foo',
        # 'bar',
        '--extensions',
        '.md',
    )
    mock_run_process.assert_called_once_with(
        Path(str(tmp_work_path)),
        target=run_function,
        args=('os.getcwd', '/path/to/tty'),
        callback=callback,
        watch_filter=IsInstance(PythonFilter)
        & FunctionCheck(
            lambda f: f.extensions
            == (
                '.py',
                '.pyx',
                '.pyd',
                '.md',
            )
        ),
    )


def test_invalid_import1(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('foobar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: "foobar" doesn\'t look like a module path\n'


def test_invalid_import2(mocker, tmp_work_path, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('pprint.foobar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: Module "pprint" does not define a "foobar" attribute\n'


def test_invalid_path(mocker, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('os.getcwd', '/does/not/exist')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'path "/does/not/exist" does not exist\n'


def test_tty_os_error(mocker, tmp_work_path):
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=OSError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('os.getcwd')
    mock_run_process.assert_called_once_with(
        tmp_work_path,
        target=run_function,
        args=('os.getcwd', '/dev/tty'),
        callback=callback,
        watch_filter=IsInstance(PythonFilter),
    )


def test_tty_attribute_error(mocker, tmp_work_path):
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=AttributeError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('os.getcwd', str(tmp_work_path))
    mock_run_process.assert_called_once_with(
        tmp_work_path,
        target=run_function,
        args=('os.getcwd', None),
        callback=callback,
        watch_filter=IsInstance(PythonFilter),
    )


def test_run_function(tmp_work_path: Path, create_test_function):
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, None)
    assert (tmp_work_path / 'sentinel').exists()


def test_run_function_tty(tmp_work_path: Path, create_test_function):
    # could this cause problems by changing sys.stdin?
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, '/dev/tty')
    assert (tmp_work_path / 'sentinel').exists()


def test_callback(mocker):
    # boring we have to test this directly, but we do
    mock_logger = mocker.patch('watchgod.cli.logger.info')
    callback({1, 2, 3})
    mock_logger.assert_called_once_with('%d files changed, reloading', 3)


def test_set_tty_error():
    with set_tty('/foo/bar'):
        pass


args_list = [
    ([], []),
    (['--foo', 'bar'], []),
    (['--foo', 'bar', '-a'], []),
    (['--foo', 'bar', '--args'], []),
    (['--foo', 'bar', '-a', '--foo', 'bar'], ['--foo', 'bar']),
    (['--foo', 'bar', '-f', 'b', '--args', '-f', '-b', '-z', 'x'], ['-f', '-b', '-z', 'x']),
]


@pytest.mark.parametrize('initial, expected', args_list)
def test_sys_argv(initial, expected, mocker):
    mocker.patch('sys.argv', ['script.py', *initial])  # mocker will restore initial sys.argv after test
    argv = sys_argv('path.to.func')
    assert argv[0] == str(Path('path/to.py').absolute())
    assert argv[1:] == expected


@pytest.mark.parametrize('initial, expected', args_list)
def test_func_with_parser(tmp_work_path, create_test_function, mocker, initial, expected):
    # setup
    mocker.patch('sys.argv', ['foo.py', *initial])
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=AttributeError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    # test
    assert not (tmp_work_path / 'sentinel').exists()
    cli('os.getcwd', str(tmp_work_path))  # run til mock_run_process
    run_function(create_test_function, None)  # run target function once
    file = tmp_work_path / 'sentinel'
    mock_run_process.assert_called_once_with(
        tmp_work_path,
        target=run_function,
        args=('os.getcwd', None),
        callback=callback,
        watch_filter=IsInstance(PythonFilter),
    )
    assert file.exists()
    assert file.read_text(encoding='utf-8') == ' '.join(expected)
