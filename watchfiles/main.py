import json
import logging
import os
import signal
import sys
from enum import IntEnum
from multiprocessing import get_context
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Dict, Generator, Optional, Set, Tuple, Union, cast

import anyio

from ._rust_notify import RustNotify
from .filters import DefaultFilter, PythonFilter

__all__ = 'watch', 'awatch', 'run_process', 'arun_process', 'Change'
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
    from multiprocessing.context import SpawnProcess

    import trio

    AnyCallable = Callable[..., Any]
    AnyEvent = Union[anyio.Event, asyncio.Event, trio.Event]


def watch(
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[['Change', str], bool]] = DefaultFilter(),
    debounce: int = 1_600,
    step: int = 50,
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
        raw_changes = watcher.watch(debounce, step, None)
        if raw_changes is None:
            if raise_interrupt:
                raise KeyboardInterrupt
            else:
                logger.warning('KeyboardInterrupt caught, stopping watch')
                return

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

        if raw_changes is None:
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
    if logger.isEnabledFor(logging.INFO):
        count = len(changes)
        plural = '' if count == 1 else 's'
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%d change%s detected: %s', count, plural, changes)
        else:
            logger.info('%d change%s detected', count, plural)


# Use spawn context to make sure code run in subprocess
# does not reuse imported modules in main process/context
spawn_context = get_context('spawn')


def _start_process(
    target: 'AnyCallable',
    args: Tuple[Any, ...],
    kwargs: Optional[Dict[str, Any]],
    changes: Optional[Set[FileChange]] = None,
) -> 'SpawnProcess':
    if changes is None:
        changes_env_var = '[]'
    else:
        changes_env_var = json.dumps([[c.raw_str(), p] for c, p in changes])

    os.environ['WATCHFILES_CHANGES'] = changes_env_var
    process = spawn_context.Process(target=target, args=args, kwargs=kwargs or {})
    process.start()
    return process


def _stop_process(process: 'SpawnProcess') -> None:
    os.environ.pop('WATCHFILES_CHANGES', None)
    if process.is_alive():
        logger.debug('stopping process...')
        pid = cast(int, process.pid)
        os.kill(pid, signal.SIGINT)
        process.join(5)
        if process.exitcode is None:
            logger.warning('process has not terminated, sending SIGKILL')
            os.kill(pid, signal.SIGKILL)
            process.join(1)
        else:
            logger.debug('process stopped')
    else:
        logger.warning('process already dead, exit code: %d', process.exitcode)


def run_process(
    *paths: Union[Path, str],
    target: 'AnyCallable',
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[Set[FileChange]], None]] = None,
    watch_filter: Optional[Callable[[Change, str], bool]] = PythonFilter(),
    debounce: int = 1_600,
    step: int = 50,
    debug: bool = False,
) -> int:
    """
    Run a function in a subprocess using `multiprocessing.Process`
    (technically `multiprocessing.get_context('spawn').Process` to avoid forking and improve code reload),
    restart it whenever files change in path.

    Internally, `run_process` uses [`watch`][watchfiles.watch] with `raise_interrupt=False` so the function
    exits cleanly upon `Ctrl+C`.

    Args:
        *paths: matches the same argument of [`watch`][watchfiles.watch]
        target: function to run
        args: arguments to pass to `target`
        kwargs: keyword arguments to pass to `target`
        callback: function to call on each reload, the function should accept a set of changes as the sole argument
        watch_filter: matches the same argument of [`watch`][watchfiles.watch], except an instance of
            [`PythonFilter`][watchfiles.PythonFilter] is used by default so only python files are watched.
        debounce: matches the same argument of [`watch`][watchfiles.watch]
        step: matches the same argument of [`watch`][watchfiles.watch]
        debug: matches the same argument of [`watch`][watchfiles.watch]

    Returns:
        number of times the function was reloaded.

    ```py title="Example of run_process usage"
    from watchfiles import run_process

    def callback(changes):
        print('changes detected:', changes)

    def foobar(a, b):
        print('foobar called with:', a, b)

    if __name__ == '__main__':
        run_process('./path/to/dir', target=foobar, args=(1, 2), callback=callback)
    ```

    As well as using a `callback` function, changes can be accessed from within the target function,
    using the `WATCHFILES_CHANGES` environment variable.

    ```py title="Example of run_process accessing changes"
    from watchfiles import run_process

    def foobar(a, b, c):
        # changes will be an empty list "[]" the first time the function is called
        changes = os.getenv('WATCHFILES_CHANGES')
        changes = json.loads(changes)
        print('foobar called due to changes:', changes)

    if __name__ == '__main__':
        run_process('./path/to/dir', target=foobar, args=(1, 2, 3))
    ```
    """

    process = _start_process(target, args, kwargs)
    reloads = 0

    try:
        for changes in watch(
            *paths, watch_filter=watch_filter, debounce=debounce, step=step, debug=debug, raise_interrupt=False
        ):
            callback and callback(changes)
            _stop_process(process)
            process = _start_process(target, args, kwargs, changes)
            reloads += 1
    finally:
        _stop_process(process)
    return reloads


async def arun_process(
    *paths: Union[Path, str],
    target: 'AnyCallable',
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[Set[FileChange]], Any]] = None,
    watch_filter: Optional[Callable[[Change, str], bool]] = PythonFilter(),
    debounce: int = 1_600,
    step: int = 50,
    debug: bool = False,
) -> int:
    """
    Async equivalent of [`run_process`][watchfiles.run_process], all arguments match those of `run_process` except
    `callback` which can be a coroutine.

    Starting and stopping the process and watching for changes is done in a separate thread.

    As with `run_process`, internally `arun_process` uses [`awatch`][watchfiles.awatch] with `raise_interrupt=False`
    so the function exits cleanly upon `Ctrl+C`.

    ```py title="Example of arun_process usage"
    import asyncio
    from watchfiles import arun_process

    async def callback(changes):
        await asyncio.sleep(0.1)
        print('changes detected:', changes)

    def foobar(a, b):
        print('foobar called with:', a, b)

    async def main():
        await arun_process('.', target=foobar, args=(1, 2), callback=callback)

    if __name__ == '__main__':
        asyncio.run(main())
    ```
    """
    import inspect

    process = await anyio.to_thread.run_sync(_start_process, target, args, kwargs)
    reloads = 0

    async for changes in awatch(
        *paths, watch_filter=watch_filter, debounce=debounce, step=step, debug=debug, raise_interrupt=False
    ):
        if callback is not None:
            r = callback(changes)
            if inspect.isawaitable(r):
                await r

        await anyio.to_thread.run_sync(_stop_process, process)
        process = await anyio.to_thread.run_sync(_start_process, target, args, kwargs, changes)
        reloads += 1
    await anyio.to_thread.run_sync(_stop_process, process)
    return reloads
