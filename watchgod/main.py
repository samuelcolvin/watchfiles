import functools
import logging
import os
import signal
from functools import partial
from multiprocessing import get_context
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Generator, Optional, Set, Tuple, Type, Union, cast

import anyio

from .watcher import DefaultWatcher, PythonWatcher

__all__ = 'watch', 'awatch', 'run_process', 'arun_process'
logger = logging.getLogger('watchgod.main')

if TYPE_CHECKING:
    import asyncio
    from multiprocessing.context import SpawnProcess

    import trio

    from .watcher import AllWatcher, FileChange

    FileChanges = Set[FileChange]
    AnyCallable = Callable[..., Any]
    AnyEvent = Union[anyio.Event, asyncio.Event, trio.Event]

# Use spawn context to make sure code run in subprocess
# does not reuse imported modules in main process/context
spawn_context = get_context('spawn')


def unix_ms() -> int:
    return int(round(time() * 1000))


def watch(path: Union[Path, str], **kwargs: Any) -> Generator['FileChanges', None, None]:
    """
    Watch a directory and yield a set of changes whenever files change in that directory or its subdirectories.
    """
    try:
        _awatch = awatch(path, **kwargs)
        while True:
            try:
                yield anyio.run(_awatch.__anext__)
            except StopAsyncIteration:
                break
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt, exiting')


class awatch:
    """
    asynchronous equivalent of watch using a threaded executor.

    3.5 doesn't support yield in coroutines so we need all this fluff. Yawwwwn.
    """

    __slots__ = (
        '_path',
        '_watcher_cls',
        '_watcher_kwargs',
        '_debounce',
        '_min_sleep',
        '_stop_event',
        '_normal_sleep',
        '_w',
        'lock',
        '_thread_limiter',
    )

    def __init__(
        self,
        path: Union[Path, str],
        *,
        watcher_cls: Type['AllWatcher'] = DefaultWatcher,
        watcher_kwargs: Optional[Dict[str, Any]] = None,
        debounce: int = 1600,
        normal_sleep: int = 400,
        min_sleep: int = 50,
        stop_event: Optional['AnyEvent'] = None,
    ) -> None:
        self._thread_limiter: Optional[anyio.CapacityLimiter] = None
        self._path = path
        self._watcher_cls = watcher_cls
        self._watcher_kwargs = watcher_kwargs or dict()
        self._debounce = debounce
        self._normal_sleep = normal_sleep
        self._min_sleep = min_sleep
        self._stop_event = stop_event
        self._w: Optional['AllWatcher'] = None
        self.lock = anyio.Lock()

    def __aiter__(self) -> 'awatch':
        return self

    async def __anext__(self) -> 'FileChanges':
        if self._w:
            watcher = self._w
        else:
            watcher = self._w = await self.run_in_executor(
                functools.partial(self._watcher_cls, self._path, **self._watcher_kwargs)
            )
        check_time = 0
        changes: 'FileChanges' = set()
        last_change = 0
        while True:
            if self._stop_event and self._stop_event.is_set():
                raise StopAsyncIteration()
            async with self.lock:
                if not changes:
                    last_change = unix_ms()

                if check_time:
                    if changes:
                        sleep_time = self._min_sleep
                    else:
                        sleep_time = max(self._normal_sleep - check_time, self._min_sleep)
                    await anyio.sleep(sleep_time / 1000)

                s = unix_ms()
                new_changes = await self.run_in_executor(watcher.check)
                changes.update(new_changes)
                now = unix_ms()
                check_time = now - s
                debounced = now - last_change
                if logger.isEnabledFor(logging.DEBUG) and changes:
                    logger.debug(
                        '%s time=%0.0fms debounced=%0.0fms files=%d changes=%d (%d)',
                        self._path,
                        check_time,
                        debounced,
                        len(watcher.files),
                        len(changes),
                        len(new_changes),
                    )

                if changes and (not new_changes or debounced > self._debounce):
                    logger.debug('%s changes released debounced=%0.0fms', self._path, debounced)
                    return changes

    async def run_in_executor(self, func: 'AnyCallable', *args: Any) -> Any:
        if self._thread_limiter is None:
            self._thread_limiter = anyio.CapacityLimiter(4)
        return await anyio.to_thread.run_sync(func, *args, limiter=self._thread_limiter)


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
    watcher_cls: Type['AllWatcher'] = PythonWatcher,
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
    watcher_cls: Type['AllWatcher'] = PythonWatcher,
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
