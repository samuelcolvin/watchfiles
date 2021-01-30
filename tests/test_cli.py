import sys
from pathlib import Path

import pytest

from watchgod.cli import callback, cli, run_function, set_tty, sys_argv

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='many tests fail on windows')


def foobar():
    # used by tests below
    Path('sentinel').write_text('ok')


def with_parser():
    # used by tests below
    Path('sentinel').write_text(' '.join(map(str, sys.argv[1:])))


def test_simple(mocker, tmpdir):
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('tests.test_cli.foobar', str(tmpdir))
    mock_run_process.assert_called_once_with(
        Path(str(tmpdir)),
        run_function,
        args=('tests.test_cli.foobar', '/path/to/tty'),
        callback=callback,
        watcher_kwargs={'ignored_paths': set()},
    )


def test_invalid_import1(mocker, tmpdir, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('foobar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: "foobar" doesn\'t look like a module path\n'


def test_invalid_import2(mocker, tmpdir, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('pprint.foobar')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: Module "pprint" does not define a "foobar" attribute\n'


def test_invalid_path(mocker, capsys):
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli('tests.test_cli.foobar', '/does/not/exist')
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'path "/does/not/exist" does not exist\n'


def test_tty_os_error(mocker, tmpworkdir):
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=OSError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('tests.test_cli.foobar')
    mock_run_process.assert_called_once_with(
        Path(str(tmpworkdir)),
        run_function,
        args=('tests.test_cli.foobar', '/dev/tty'),
        callback=callback,
        watcher_kwargs={'ignored_paths': set()},
    )


def test_tty_attribute_error(mocker, tmpdir):
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=AttributeError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli('tests.test_cli.foobar', str(tmpdir))
    mock_run_process.assert_called_once_with(
        Path(str(tmpdir)),
        run_function,
        args=('tests.test_cli.foobar', None),
        callback=callback,
        watcher_kwargs={'ignored_paths': set()},
    )


def test_run_function(tmpworkdir):
    assert not tmpworkdir.join('sentinel').exists()
    run_function('tests.test_cli.foobar', None)
    assert tmpworkdir.join('sentinel').exists()


def test_run_function_tty(tmpworkdir):
    # could this cause problems by changing sys.stdin?
    assert not tmpworkdir.join('sentinel').exists()
    run_function('tests.test_cli.foobar', '/dev/tty')
    assert tmpworkdir.join('sentinel').exists()


def test_callback(mocker):
    # boring we have to test this directly, but we do
    mock_logger = mocker.patch('watchgod.cli.logger.info')
    callback({1, 2, 3})
    mock_logger.assert_called_once_with('%d files changed, reloading', 3)


def test_set_tty_error():
    with set_tty('/foo/bar'):
        pass


@pytest.mark.parametrize(
    'initial, expected',
    [
        ([], []),
        (['--foo', 'bar'], []),
        (['--foo', 'bar', '-a'], []),
        (['--foo', 'bar', '--args'], []),
        (['--foo', 'bar', '-a', '--foo', 'bar'], ['--foo', 'bar']),
        (['--foo', 'bar', '-f', 'b', '--args', '-f', '-b', '-z', 'x'], ['-f', '-b', '-z', 'x']),
    ],
)
def test_sys_argv(initial, expected, mocker):
    mocker.patch('sys.argv', ['script.py', *initial])  # mocker will restore initial sys.argv after test
    argv = sys_argv('path.to.func')
    assert argv[0] == str(Path('path/to.py').absolute())
    assert argv[1:] == expected


@pytest.mark.parametrize(
    'initial, expected',
    [
        ([], []),
        (['--foo', 'bar'], []),
        (['--foo', 'bar', '-a'], []),
        (['--foo', 'bar', '--args'], []),
        (['--foo', 'bar', '-a', '--foo', 'bar'], ['--foo', 'bar']),
        (['--foo', 'bar', '-f', 'b', '--args', '-f', '-b', '-z', 'x'], ['-f', '-b', '-z', 'x']),
    ],
)
def test_func_with_parser(tmpworkdir, mocker, initial, expected):
    # setup
    mocker.patch('sys.argv', ['foo.py', *initial])
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=AttributeError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    # test
    assert not tmpworkdir.join('sentinel').exists()
    cli('tests.test_cli.with_parser', str(tmpworkdir))  # run til mock_run_process
    run_function('tests.test_cli.with_parser', None)  # run target function once
    file = tmpworkdir.join('sentinel')
    mock_run_process.assert_called_once_with(
        Path(str(tmpworkdir)),
        run_function,
        args=('tests.test_cli.with_parser', None),
        callback=callback,
        watcher_kwargs={'ignored_paths': set()},
    )
    assert file.exists()
    assert file.read_text(encoding='utf-8') == ' '.join(expected)
