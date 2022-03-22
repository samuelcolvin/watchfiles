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
logger = logging.getLogger('watchgod.main')


class Change(IntEnum):
    added = 1
    modified = 2
    deleted = 3

    def raw_str(self) -> str:
        if self == Change.added:
            return 'added'
        elif self == Change.modified:
            return 'modified'
        else:
            return 'deleted'


if TYPE_CHECKING:
    import asyncio
    from multiprocessing.context import SpawnProcess

    import trio

    FileChange = Tuple[Change, str]
    FileChanges = Set[FileChange]
    AnyCallable = Callable[..., Any]
    AnyEvent = Union[anyio.Event, asyncio.Event, trio.Event]


default_filter = DefaultFilter()
default_debounce = 1_600
default_step = 50


def watch(
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[['Change', str], bool]] = default_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    debug: bool = False,
    raise_interrupt: bool = True,
) -> Generator['FileChanges', None, None]:
    """
    Watch one or more directories and yield a set of changes whenever files change
    in those directories (or subdirectories).
    """
    watcher = RustNotify([str(p) for p in paths], debug)
    while True:
        raw_changes = watcher.watch(debounce, step, None)
        if raw_changes is None:
            if raise_interrupt:
                raise KeyboardInterrupt
            else:
                return

        changes = _prep_changes(raw_changes, watch_filter)
        if changes:
            _log_changes(changes)
            yield changes


async def awatch(
    *paths: Union[Path, str],
    watch_filter: Optional[Callable[['Change', str], bool]] = default_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    stop_event: Optional['AnyEvent'] = None,
    debug: bool = False,
    raise_interrupt: bool = True,
) -> AsyncGenerator['FileChanges', None]:
    """
    asynchronous equivalent of watch using a threaded executor.
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
            if interrupted and raise_interrupt:
                raise KeyboardInterrupt
            else:
                logger.warning('got SIGINT, stopping awatch without raising exception')
                return

        changes = _prep_changes(raw_changes, watch_filter)
        if changes:
            _log_changes(changes)
            yield changes


def _prep_changes(
    raw_changes: Set[Tuple[int, str]], watch_filter: Optional[Callable[['Change', str], bool]]
) -> 'FileChanges':
    # if we wanted to be really snazzy, we could move this into rust
    changes = {(Change(change), path) for change, path in raw_changes}
    if watch_filter:
        changes = {c for c in changes if watch_filter(c[0], c[1])}
    return changes


def _log_changes(changes: 'FileChanges') -> None:
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
    changes: 'Optional[FileChanges]' = None,
) -> 'SpawnProcess':
    if changes is None:
        os.environ['WATCHGOD_CHANGES'] = '[]'
    else:
        os.environ['WATCHGOD_CHANGES'] = json.dumps([[c.raw_str(), p] for c, p in changes])
    process = spawn_context.Process(target=target, args=args, kwargs=kwargs or {})
    process.start()
    return process


def _stop_process(process: 'SpawnProcess') -> None:
    os.environ.pop('WATCHGOD_CHANGES', None)
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


python_filter = PythonFilter()


def run_process(
    *paths: Union[Path, str],
    target: 'AnyCallable',
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[Set['FileChange']], None]] = None,
    watch_filter: Optional[Callable[['Change', str], bool]] = python_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    debug: bool = False,
) -> int:
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
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
    callback: Optional[Callable[['FileChanges'], Any]] = None,
    watch_filter: Optional[Callable[['Change', str], bool]] = python_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    debug: bool = False,
) -> int:
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
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
