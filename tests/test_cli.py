from argparse import Namespace
from pathlib import Path

from watchgod.cli import callback, cli, run_function


def test_simple(mocker, tmpdir):
    r = Namespace(function='pprint.pprint', path=str(tmpdir), verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno')
    mocker.patch('os.ttyname', return_value='/path/to/tty')
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli()
    mock_run_process.assert_called_once_with(
        Path(str(tmpdir)),
        run_function,
        args=('pprint.pprint', '/path/to/tty'),
        callback=callback
    )


def test_invalid_import1(mocker, tmpdir, capsys):
    r = Namespace(function='foobar', path=str(tmpdir), verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli()
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: "foobar" doesn\'t look like a module path\n'


def test_invalid_import2(mocker, tmpdir, capsys):
    r = Namespace(function='pprint.foobar', path=str(tmpdir), verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli()
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ImportError: Module "pprint" does not define a "foobar" attribute\n'


def test_invalid_path(mocker, capsys):
    r = Namespace(function='pprint.pprint', path='/does/not/exist', verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    sys_exit = mocker.patch('watchgod.cli.sys.exit')
    cli()
    sys_exit.assert_called_once_with(1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'path "/does/not/exist" is not a directory\n'


def test_tty_os_error(mocker, tmpdir):
    r = Namespace(function='pprint.pprint', path=str(tmpdir), verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=OSError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli()
    mock_run_process.assert_called_once_with(
        Path(str(tmpdir)),
        run_function,
        args=('pprint.pprint', '/dev/tty'),
        callback=callback
    )


def test_tty_attribute_error(mocker, tmpdir):
    r = Namespace(function='pprint.pprint', path=str(tmpdir), verbosity=1)
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=r)
    mocker.patch('watchgod.cli.set_start_method')
    mocker.patch('watchgod.cli.sys.stdin.fileno', side_effect=AttributeError)
    mock_run_process = mocker.patch('watchgod.cli.run_process')
    cli()
    mock_run_process.assert_called_once_with(
        Path(str(tmpdir)),
        run_function,
        args=('pprint.pprint', None),
        callback=callback
    )


def test_run_function(mocker):
    mock_pprint = mocker.patch('pprint.pprint')
    run_function('pprint.pprint', None)
    assert mock_pprint.called


def test_run_function_tty(mocker):
    # could this cause problems by changing sys.stdin?
    mock_pprint = mocker.patch('pprint.pprint')
    run_function('pprint.pprint', '/dev/tty')
    assert mock_pprint.called


def test_callback(mocker):
    # boring we have to test this directly, but we do
    mock_logger = mocker.patch('watchgod.cli.logger.info')
    callback({1, 2, 3})
    mock_logger.assert_called_once_with('%d files changed, reloading', 3)
