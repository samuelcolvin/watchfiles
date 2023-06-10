import logging
import os
import sys
import warnings
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, Callable, Generator, Optional, Set, Tuple, Union

import anyio

from ._rust_notify import RustNotify
from .filters import DefaultFilter

__all__ = 'watch', 'awatch', 'Change', 'FileChange'
logger = logging.getLogger('watchfiles.main')


class Change(IntEnum):
    """
    Enum representing the type of change that occurred.
    """

    added = 1
    """A new file or directory was added."""
    modified = 2
    """A file or directory was modified, can be either a metadata or data change."""
    deleted = 3
    """A file or directory was deleted."""

    closed = 4
    other = 99

    def raw_str(self) -> str:
        return self.name


FileChange = Tuple[Change, str]
"""
A tuple representing a file change, first element is a [`Change`][watchfiles.Change] member, second is the path
of the file or directory that changed.
"""

if TYPE_CHECKING:
    import asyncio
    from typing import Protocol

    import trio

    AnyEvent = Union[anyio.Event, asyncio.Event, trio.Event]

    class AbstractEvent(Protocol):
        def is_set(self) -> bool:
            ...


def watch(
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[['Change', str], bool]] = DefaultFilter(),
    debounce: int = 1_600,
    step: int = 50,
    stop_event: Optional['AbstractEvent'] = None,
    rust_timeout: int = 5_000,
    yield_on_timeout: bool = False,
    debug: bool = False,
    raise_interrupt: bool = True,
    force_polling: Optional[bool] = None,
    poll_delay_ms: int = 300,
    recursive: bool = True,
) -> Generator[Set[FileChange], None, None]:
    """
    Watch one or more paths and yield a set of changes whenever files change.

    The paths watched can be directories or files, directories are watched recursively - changes in subdirectories
    are also detected.

    #### Force polling

    Notify will fall back to file polling if it can't use file system notifications, but we also force notify
    to us polling if the `force_polling` argument is `True`; if `force_polling` is unset (or `None`), we enable
    force polling thus:

    * if the `WATCHFILES_FORCE_POLLING` environment variable exists and is not empty:
       * if the value is `false`, `disable` or `disabled`, force polling is disabled
       * otherwise, force polling is enabled
    * otherwise, we enable force polling only if we detect we're running on WSL (Windows Subsystem for Linux)

    Args:
        *paths: filesystem paths to watch.
        watch_filter: callable used to filter out changes which are not important, you can either use a raw callable
            or a [`BaseFilter`][watchfiles.BaseFilter] instance,
            defaults to an instance of [`DefaultFilter`][watchfiles.DefaultFilter]. To keep all changes, use `None`.
        debounce: maximum time in milliseconds to group changes over before yielding them.
        step: time to wait for new changes in milliseconds, if no changes are detected in this time, and
            at least one change has been detected, the changes are yielded.
        stop_event: event to stop watching, if this is set, the generator will stop iteration,
            this can be anything with an `is_set()` method which returns a bool, e.g. `threading.Event()`.
        rust_timeout: maximum time in milliseconds to wait in the rust code for changes, `0` means no timeout.
        yield_on_timeout: if `True`, the generator will yield upon timeout in rust even if no changes are detected.
        debug: whether to print information about all filesystem changes in rust to stdout.
        raise_interrupt: whether to re-raise `KeyboardInterrupt`s, or suppress the error and just stop iterating.
        force_polling: See [Force polling](#force-polling) above.
        poll_delay_ms: delay between polling for changes, only used if `force_polling=True`.
        recursive: if `True`, watch for changes in sub-directories recursively, otherwise watch only for changes in the
            top-level directory, default is `True`.

    Yields:
        The generator yields sets of [`FileChange`][watchfiles.main.FileChange]s.

    ```py title="Example of watch usage"
    from watchfiles import watch

    for changes in watch('./first/dir', './second/dir', raise_interrupt=False):
        print(changes)
    ```
    """
    force_polling = _default_force_polling(force_polling)
    with RustNotify([str(p) for p in paths], debug, force_polling, poll_delay_ms, recursive) as watcher:
        while True:
            raw_changes = watcher.watch(
                debounce, step, rust_timeout, stop_event)
            if raw_changes == 'timeout':
                if yield_on_timeout:
                    yield set()
                else:
                    logger.debug('rust notify timeout, continuing')
            elif raw_changes == 'signal':
                if raise_interrupt:
                    raise KeyboardInterrupt
                else:
                    logger.warning('KeyboardInterrupt caught, stopping watch')
                    return
            elif raw_changes == 'stop':
                return
            else:
                changes = _prep_changes(raw_changes, watch_filter)
                if changes:
                    _log_changes(changes)
                    yield changes


async def awatch(  # noqa C901
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[[Change, str], bool]] = DefaultFilter(),
    debounce: int = 1_600,
    step: int = 50,
    stop_event: Optional['AnyEvent'] = None,
    rust_timeout: Optional[int] = None,
    yield_on_timeout: bool = False,
    debug: bool = False,
    raise_interrupt: Optional[bool] = None,
    force_polling: Optional[bool] = None,
    poll_delay_ms: int = 300,
    recursive: bool = True,
) -> AsyncGenerator[Set[FileChange], None]:
    """
    Asynchronous equivalent of [`watch`][watchfiles.watch] using threads to wait for changes.
    Arguments match those of [`watch`][watchfiles.watch] except `stop_event`.

    All async methods use [anyio](https://anyio.readthedocs.io/en/latest/) to run the event loop.

    Unlike [`watch`][watchfiles.watch] `KeyboardInterrupt` cannot be suppressed by `awatch` so they need to be caught
    where `asyncio.run` or equivalent is called.

    Args:
        *paths: filesystem paths to watch.
        watch_filter: matches the same argument of [`watch`][watchfiles.watch].
        debounce: matches the same argument of [`watch`][watchfiles.watch].
        step: matches the same argument of [`watch`][watchfiles.watch].
        stop_event: `anyio.Event` which can be used to stop iteration, see example below.
        rust_timeout: matches the same argument of [`watch`][watchfiles.watch], except that `None` means
            use `1_000` on Windows and `5_000` on other platforms thus helping with exiting on `Ctrl+C` on Windows,
            see [#110](https://github.com/samuelcolvin/watchfiles/issues/110).
        yield_on_timeout: matches the same argument of [`watch`][watchfiles.watch].
        debug: matches the same argument of [`watch`][watchfiles.watch].
        raise_interrupt: This is deprecated, `KeyboardInterrupt` will cause this coroutine to be cancelled and then
            be raised by the top level `asyncio.run` call or equivalent, and should be caught there.
            See [#136](https://github.com/samuelcolvin/watchfiles/issues/136)
        force_polling: if true, always use polling instead of file system notifications, default is `None` where
            `force_polling` is set to `True` if the `WATCHFILES_FORCE_POLLING` environment variable exists.
        poll_delay_ms: delay between polling for changes, only used if `force_polling=True`.
        recursive: if `True`, watch for changes in sub-directories recursively, otherwise watch only for changes in the
            top-level directory, default is `True`.

    Yields:
        The generator yields sets of [`FileChange`][watchfiles.main.FileChange]s.

    ```py title="Example of awatch usage"
    import asyncio
    from watchfiles import awatch

    async def main():
        async for changes in awatch('./first/dir', './second/dir'):
            print(changes)

    if __name__ == '__main__':
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print('stopped via KeyboardInterrupt')
    ```

    ```py title="Example of awatch usage with a stop event"
    import asyncio
    from watchfiles import awatch

    async def main():
        stop_event = asyncio.Event()

        async def stop_soon():
            await asyncio.sleep(3)
            stop_event.set()

        stop_soon_task = asyncio.create_task(stop_soon())

        async for changes in awatch('/path/to/dir', stop_event=stop_event):
            print(changes)

        # cleanup by awaiting the (now complete) stop_soon_task
        await stop_soon_task

    asyncio.run(main())
    ```
    """
    if raise_interrupt is not None:
        warnings.warn(
            'raise_interrupt is deprecated, KeyboardInterrupt will cause this coroutine to be cancelled and then '
            'be raised by the top level asyncio.run call or equivalent, and should be caught there. See #136.',
            DeprecationWarning,
        )

    if stop_event is None:
        stop_event_: 'AnyEvent' = anyio.Event()
    else:
        stop_event_ = stop_event

    force_polling = _default_force_polling(force_polling)
    with RustNotify([str(p) for p in paths], debug, force_polling, poll_delay_ms, recursive) as watcher:
        timeout = _calc_async_timeout(rust_timeout)
        CancelledError = anyio.get_cancelled_exc_class()

        while True:
            async with anyio.create_task_group() as tg:
                try:
                    raw_changes = await anyio.to_thread.run_sync(watcher.watch, debounce, step, timeout, stop_event_)
                except (CancelledError, KeyboardInterrupt):
                    stop_event_.set()
                    # suppressing KeyboardInterrupt wouldn't stop it getting raised by the top level asyncio.run call
                    raise
                tg.cancel_scope.cancel()

            if raw_changes == 'timeout':
                if yield_on_timeout:
                    yield set()
                else:
                    logger.debug('rust notify timeout, continuing')
            elif raw_changes == 'stop':
                return
            elif raw_changes == 'signal':
                # in theory the watch thread should never get a signal
                raise RuntimeError(
                    'watch thread unexpectedly received a signal')
            else:
                changes = _prep_changes(raw_changes, watch_filter)
                if changes:
                    _log_changes(changes)
                    yield changes


def _prep_changes(
    raw_changes: Set[Tuple[int, str]], watch_filter: Optional[Callable[[Change, str], bool]]
) -> Set[FileChange]:
    # if we wanted to be really snazzy, we could move this into rust
    changes = {(Change(change), path) for change, path in raw_changes}
    if watch_filter:
        changes = {c for c in changes if watch_filter(c[0], c[1])}
    return changes


def _log_changes(changes: Set[FileChange]) -> None:
    if logger.isEnabledFor(logging.INFO):  # pragma: no branch
        count = len(changes)
        plural = '' if count == 1 else 's'
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%d change%s detected: %s', count, plural, changes)
        else:
            logger.info('%d change%s detected', count, plural)


def _calc_async_timeout(timeout: Optional[int]) -> int:
    """
    see https://github.com/samuelcolvin/watchfiles/issues/110
    """
    if timeout is None:
        if sys.platform == 'win32':
            return 1_000
        else:
            return 5_000
    else:
        return timeout


def _default_force_polling(force_polling: Optional[bool]) -> bool:
    """
    See docstring for `watch` above for details.

    See samuelcolvin/watchfiles#167 and samuelcolvin/watchfiles#187 for discussion and rationale.
    """
    if force_polling is not None:
        return force_polling
    env_var = os.getenv('WATCHFILES_FORCE_POLLING')
    if env_var:
        return env_var.lower() not in {'false', 'disable', 'disabled'}
    else:
        return _auto_force_polling()


def _auto_force_polling() -> bool:
    """
    Whether to auto-enable force polling, it should be enabled automatically only on WSL.

    See samuelcolvin/watchfiles#187 for discussion.
    """
    import platform

    uname = platform.uname()
    return 'microsoft-standard' in uname.release.lower() and uname.system.lower() == 'linux'
