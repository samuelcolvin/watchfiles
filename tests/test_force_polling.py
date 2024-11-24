from __future__ import annotations as _annotations

from typing import TYPE_CHECKING

import pytest

from watchfiles import watch
from watchfiles.main import _default_force_polling

if TYPE_CHECKING:
    from .conftest import SetEnv


class MockRustNotify:
    @staticmethod
    def watch(*args):
        return 'stop'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_watch_polling_not_env(mocker):
    m = mocker.patch('watchfiles.main.RustNotify', return_value=MockRustNotify())

    for _ in watch('.'):
        pass

    m.assert_called_once_with(['.'], False, False, 300, True, False)


def test_watch_polling_env(mocker, env: SetEnv):
    env('WATCHFILES_FORCE_POLLING', '1')
    m = mocker.patch('watchfiles.main.RustNotify', return_value=MockRustNotify())

    for _ in watch('.'):
        pass

    m.assert_called_once_with(['.'], False, True, 300, True, False)


def test_watch_polling_env_with_custom_delay(mocker, env: SetEnv):
    env('WATCHFILES_FORCE_POLLING', '1')
    env('WATCHFILES_POLL_DELAY_MS', '1000')
    m = mocker.patch('watchfiles.main.RustNotify', return_value=MockRustNotify())

    for _ in watch('.'):
        pass

    m.assert_called_once_with(['.'], False, True, 1000, True, False)


@pytest.mark.parametrize(
    'env_var,arg,expected',
    [
        (None, True, True),
        (None, False, False),
        (None, None, False),
        ('', True, True),
        ('', False, False),
        ('', None, False),
        ('1', True, True),
        ('1', False, False),
        ('1', None, True),
        ('disable', True, True),
        ('disable', False, False),
        ('disable', None, False),
    ],
)
def test_default_force_polling(mocker, env: SetEnv, env_var, arg, expected):
    uname = type('Uname', (), {'system': 'Linux', 'release': '1'})
    mocker.patch('platform.uname', return_value=uname())
    if env_var is not None:
        env('WATCHFILES_FORCE_POLLING', env_var)
    assert _default_force_polling(arg) == expected


@pytest.mark.parametrize(
    'env_var,arg,expected,call_count',
    [
        (None, True, True, 0),
        (None, False, False, 0),
        (None, None, True, 1),
        ('', True, True, 0),
        ('', False, False, 0),
        ('', None, True, 1),
        ('1', True, True, 0),
        ('1', False, False, 0),
        ('1', None, True, 0),
        ('disable', True, True, 0),
        ('disable', False, False, 0),
        ('disable', None, False, 0),
    ],
)
def test_default_force_polling_wsl(mocker, env: SetEnv, env_var, arg, expected, call_count):
    uname = type('Uname', (), {'system': 'Linux', 'release': 'Microsoft-Standard'})
    m = mocker.patch('platform.uname', return_value=uname())
    if env_var is not None:
        env('WATCHFILES_FORCE_POLLING', env_var)
    assert _default_force_polling(arg) == expected
    assert m.call_count == call_count
