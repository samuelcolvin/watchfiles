import logging
import os
import signal
from enum import IntEnum
from functools import partial
from multiprocessing import get_context
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

import anyio

from .filters import Change, DefaultFilter
from ._rust_notify import RustNotify

__all__ = 'watch', 'awatch', 'run_process', 'arun_process'
logger = logging.getLogger('watchgod.main')

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
    path: Union[Path, str],
    *,
    watch_filter: Optional[Callable[['Change', str], bool]] = default_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    stop_event: Optional['AnyEvent'] = None,
    debug: bool = False,
) -> Generator['FileChanges', None, None]:
    """
    Watch a directory and yield a set of changes whenever files change in that directory or its subdirectories.
    """
    _awatch = awatch(path, watch_filter=watch_filter, debug=debug, debounce=debounce, step=step, stop_event=stop_event)
    try:
        while True:
            try:
                yield anyio.run(_awatch.__anext__)
            except StopAsyncIteration:
                break
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt, exiting')


async def awatch(
    path: Union[Path, str],
    *,
    watch_filter: Optional[Callable[['Change', str], bool]] = default_filter,
    debounce: int = default_debounce,
    step: int = default_step,
    stop_event: Optional['AnyEvent'] = None,
    debug: bool = False,
    raise_interrupt: bool = False,
) -> AsyncGenerator['FileChanges', None]:
    """
    asynchronous equivalent of watch using a threaded executor.
    """
    if stop_event is None:
        stop_event = anyio.Event()
    interrupted = False

    async def signal_handler():
        nonlocal interrupted
        with anyio.open_signal_receiver(signal.SIGINT) as signals:
            async for _ in signals:
                interrupted = True
                await stop_event.set()
                break

    watcher = RustNotify(path, debug)
    async with anyio.create_task_group() as tg:
        tg.start_soon(signal_handler)
        while True:
            raw_changes = await anyio.to_thread.run_sync(watcher.watch, debounce, step, stop_event)
            if stop_event.is_set():
                break

            changes = {(Change(change), path) for change, path in raw_changes}
            if watch_filter:
                changes = {c for c in changes if watch_filter(c[0], c[1])}
            if changes:
                yield changes

    if interrupted and raise_interrupt:
        raise KeyboardInterrupt


# Use spawn context to make sure code run in subprocess
# does not reuse imported modules in main process/context
spawn_context = get_context('spawn')


def _start_process(target: 'AnyCallable', args: Tuple[Any, ...], kwargs: Optional[Dict[str, Any]]) -> 'SpawnProcess':
    process = spawn_context.Process(target=target, args=args, kwargs=kwargs or {})
    process.start()
    return process


def _stop_process(process: 'SpawnProcess') -> None:
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
    path: Union[Path, str],
    target: 'AnyCallable',
    *,
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[Set['FileChange']], None]] = None,
    # watcher_cls: Type['AllWatcher'] = PythonWatcher,
    watcher_kwargs: Optional[Dict[str, Any]] = None,
    debounce: int = 400,
    min_sleep: int = 100,
) -> int:
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
    """

    process = _start_process(target=target, args=args, kwargs=kwargs)
    reloads = 0

    try:
        for changes in watch(
            path, watcher_cls=watcher_cls, debounce=debounce, min_sleep=min_sleep, watcher_kwargs=watcher_kwargs
        ):
            callback and callback(changes)
            _stop_process(process)
            process = _start_process(target=target, args=args, kwargs=kwargs)
            reloads += 1
    finally:
        _stop_process(process)
    return reloads


async def arun_process(
    path: Union[Path, str],
    target: 'AnyCallable',
    *,
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[['FileChanges'], Awaitable[None]]] = None,
    # watcher_cls: Type['AllWatcher'] = PythonWatcher,
    debounce: int = 400,
    min_sleep: int = 100,
) -> int:
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
    """
    watcher = awatch(path, watcher_cls=watcher_cls, debounce=debounce, min_sleep=min_sleep)
    start_process = partial(_start_process, target=target, args=args, kwargs=kwargs)
    process = await watcher.run_in_executor(start_process)
    reloads = 0

    async for changes in watcher:
        callback and await callback(changes)
        await watcher.run_in_executor(_stop_process, process)
        process = await watcher.run_in_executor(start_process)
        reloads += 1
    await watcher.run_in_executor(_stop_process, process)
    return reloads
