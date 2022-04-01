import logging
import signal
import sys
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
    """A new file was added."""
    modified = 2
    """A file was modified, can be either a metadata or data change."""
    deleted = 3
    """A file was deleted."""

    def raw_str(self) -> str:
        if self == Change.added:
            return 'added'
        elif self == Change.modified:
            return 'modified'
        else:
            return 'deleted'


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
    debug: bool = False,
    raise_interrupt: bool = True,
) -> Generator[Set[FileChange], None, None]:
    """
    Watch one or more directories and yield a set of changes whenever files change
    in those directories (or subdirectories).

    Args:
        *paths: filesystem directories to watch
        watch_filter: callable used to filter out changes which are not important, you can either use a raw callable
            or a [`BaseFilter`][watchfiles.BaseFilter] instance,
            defaults to an instance of [`DefaultFilter`][watchfiles.DefaultFilter]. To keep all changes, use `None`.
        debounce: maximum time in milliseconds to group changes over before yielding them.
        step: time to wait for new changes in milliseconds, if no changes are detected in this time, and
            at least one change has been detected, the changes are yielded.
        stop_event: event to stop watching, if this is set, the generator will stop yielding changes,
            this can be anything with an `is_set()` method which returns a bool, e.g. `threading.Event()`.
        debug: whether to print information about all filesystem changes in rust to stdout.
        raise_interrupt: whether to re-raise `KeyboardInterrupt`s, or suppress the error and just stop iterating.

    Yields:
        The generator yields sets of [`FileChange`][watchfiles.main.FileChange]s.

    ```py title="Example of watch usage"
    from watchfiles import watch

    for changes in watch('./first/dir', './second/dir', raise_interrupt=False):
        print(changes)
    ```
    """
    watcher = RustNotify([str(p) for p in paths], debug)
    while True:
        raw_changes = watcher.watch(debounce, step, stop_event)
        if raw_changes == 'signalled':
            if raise_interrupt:
                raise KeyboardInterrupt
            else:
                logger.warning('KeyboardInterrupt caught, stopping watch')
                return
        elif raw_changes == 'stopped':
            return
        else:
            changes = _prep_changes(raw_changes, watch_filter)
            if changes:
                _log_changes(changes)
                yield changes


async def awatch(
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[[Change, str], bool]] = DefaultFilter(),
    debounce: int = 1_600,
    step: int = 50,
    stop_event: Optional['AnyEvent'] = None,
    debug: bool = False,
    raise_interrupt: bool = True,
) -> AsyncGenerator[Set[FileChange], None]:
    """
    Asynchronous equivalent of [`watch`][watchfiles.watch] using threads to wait for changes.
    Arguments match those of [`watch`][watchfiles.watch] except `stop_event`.

    All async methods use [anyio](https://anyio.readthedocs.io/en/latest/) to run the event loop.

    Args:
        *paths: filesystem directories to watch
        stop_event:
        watch_filter: matches the same argument of [`watch`][watchfiles.watch].
        debounce: matches the same argument of [`watch`][watchfiles.watch].
        step: matches the same argument of [`watch`][watchfiles.watch].
        debug: matches the same argument of [`watch`][watchfiles.watch].
        stop_event: `anyio.Event` which can be used to stop iteration, see example below.
        raise_interrupt: matches the same argument of [`watch`][watchfiles.watch].

    Yields:
        The generator yields sets of [`FileChange`][watchfiles.main.FileChange]s.

    ```py title="Example of awatch usage"
    import asyncio
    from watchfiles import awatch

    async def main():
        async for changes in awatch('./first/dir', './second/dir'):
            print(changes)

    asyncio.run(main())
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
    if stop_event is None:
        stop_event_: 'AnyEvent' = anyio.Event()
    else:
        stop_event_ = stop_event
    interrupted = False

    async def signal_handler() -> None:
        nonlocal interrupted

        if sys.platform == 'win32':
            # add_signal_handler is not implemented on windows
            # repeat ctrl+c should still stop the watcher
            return

        with anyio.open_signal_receiver(signal.SIGINT) as signals:
            async for _ in signals:
                interrupted = True
                stop_event_.set()
                break

    watcher = RustNotify([str(p) for p in paths], debug)
    while True:
        async with anyio.create_task_group() as tg:
            tg.start_soon(signal_handler)
            raw_changes = await anyio.to_thread.run_sync(watcher.watch, debounce, step, stop_event_)
            tg.cancel_scope.cancel()

        # cover both cases here although in theory the watch thread should never get a signal
        if raw_changes == 'stopped' or raw_changes == 'signalled':
            if interrupted:
                if raise_interrupt:
                    raise KeyboardInterrupt
                else:
                    logger.warning('KeyboardInterrupt caught, stopping awatch')
            return

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
