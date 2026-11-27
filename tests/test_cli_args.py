import sys

import pytest

from watchfiles.cli import cli, split_args


def test_args_windows_backslashes(mocker, tmp_path, reset_argv):
    mocker.patch('watchfiles.cli.sys.platform', 'win32')
    mocker.patch('watchfiles.cli.run_process')
    cli('--args', r'--config C:\proj\settings.toml --name "John Smith"', 'os.getcwd', str(tmp_path))
    assert sys.argv == ['os.getcwd', '--config', r'C:\proj\settings.toml', '--name', 'John Smith']


@pytest.mark.skipif(sys.platform != 'win32', reason='no need to test native win32 platform check outside windows')
def test_args_native_windows(mocker, tmp_path, reset_argv):
    mocker.patch('watchfiles.cli.run_process')
    cli('--args', r'--config C:\proj\settings.toml --name "John Smith"', 'os.getcwd', str(tmp_path))
    assert sys.argv == ['os.getcwd', '--config', r'C:\proj\settings.toml', '--name', 'John Smith']


@pytest.mark.parametrize(
    'args_str,expected',
    [
        (r'--config C:\proj\settings.toml', ['--config', r'C:\proj\settings.toml']),
        ('--name "John Smith"', ['--name', 'John Smith']),
        ("--name 'Jane Doe'", ['--name', 'Jane Doe']),
        (r'--config "C:\Program Files\a.toml"', ['--config', r'C:\Program Files\a.toml']),
        (r'--dir "C:\Program Files\" #keep', ['--dir', 'C:\\Program Files\\', '#keep']),
    ],
)
def test_split_args_windows(mocker, args_str, expected):
    mocker.patch('watchfiles.cli.sys.platform', 'win32')
    assert split_args(args_str) == expected


def test_split_args_posix(mocker):
    mocker.patch('watchfiles.cli.sys.platform', 'linux')
    assert split_args(r'--name "John\ Smith" --path /tmp/a\ b') == ['--name', 'John\\ Smith', '--path', '/tmp/a b']
