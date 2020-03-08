import asyncio
import functools
import logging
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from multiprocessing import Process
from pathlib import Path
from time import time
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple, Type, Union

from .watcher import AllWatcher, Change, DefaultWatcher, PythonWatcher

__all__ = 'watch', 'awatch', 'run_process', 'arun_process'
logger = logging.getLogger('watchgod.main')


def unix_ms():
    return int(round(time() * 1000))


def watch(path: Union[Path, str], **kwargs):
    """
    Watch a directory and yield a set of changes whenever files change in that directory or its subdirectories.
    """
    loop = asyncio.new_event_loop()
    try:
        _awatch = awatch(path, loop=loop, **kwargs)
        while True:
            try:
                yield loop.run_until_complete(_awatch.__anext__())
            except StopAsyncIteration:
                break
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt, exiting')
    finally:
        loop.close()


def correct_aiter(func):  # pragma: no cover
    if sys.version_info >= (3, 5, 2):
        return func
    else:
        return asyncio.coroutine(func)


class awatch:
    """
    asynchronous equivalent of watch using a threaded executor.

    3.5 doesn't support yield in coroutines so we need all this fluff. Yawwwwn.
    """
    __slots__ = (
        '_loop', '_path', '_watcher_cls', '_watcher_kwargs', '_debounce', '_min_sleep', '_stop_event', '_normal_sleep',
        '_w', 'lock', '_executor'
    )

    def __init__(self, path: Union[Path, str], *,
                 watcher_cls: Type[AllWatcher] = DefaultWatcher,
                 watcher_kwargs: Optional[Dict[str, Any]] = None,
                 debounce=1600,
                 normal_sleep=400,
                 min_sleep=50,
                 stop_event: asyncio.Event = None,
                 loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._path = path
        self._watcher_cls = watcher_cls
        self._watcher_kwargs = watcher_kwargs or dict()
        self._debounce = debounce
        self._normal_sleep = normal_sleep
        self._min_sleep = min_sleep
        self._stop_event = stop_event
        self._w = None
        asyncio.set_event_loop(self._loop)
        self.lock = asyncio.Lock()

    @correct_aiter
    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._w:
            self._w = await self.run_in_executor(
                functools.partial(self._watcher_cls, self._path, **self._watcher_kwargs))
        check_time = 0
        changes = set()
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
                    await asyncio.sleep(sleep_time / 1000)

                s = unix_ms()
                new_changes = await self.run_in_executor(self._w.check)
                changes.update(new_changes)
                now = unix_ms()
                check_time = now - s
                debounced = now - last_change
                if logger.isEnabledFor(logging.DEBUG) and changes:
                    logger.debug('%s time=%0.0fms debounced=%0.0fms files=%d changes=%d (%d)',
                                 self._path, check_time, debounced, len(self._w.files), len(changes), len(new_changes))

                if changes and (not new_changes or debounced > self._debounce):
                    logger.debug('%s changes released debounced=%0.0fms', self._path, debounced)
                    return changes

    async def run_in_executor(self, func, *args):
        return await self._loop.run_in_executor(self._executor, func, *args)

    def __del__(self):
        self._executor.shutdown()


def _start_process(target, args, kwargs):
    process = Process(target=target, args=args, kwargs=kwargs or {})
    process.start()
    return process


def _stop_process(process):
    if process.is_alive():
        logger.debug('stopping process...')
        os.kill(process.pid, signal.SIGINT)
        process.join(5)
        if process.exitcode is None:
            logger.warning('process has not terminated, sending SIGKILL')
            os.kill(process.pid, signal.SIGKILL)
            process.join(1)
        else:
            logger.debug('process stopped')
    else:
        logger.warning('process already dead, exit code: %d', process.exitcode)


def run_process(path: Union[Path, str], target: Callable, *,
                args: Tuple = (),
                kwargs: Dict[str, Any] = None,
                callback: Callable[[Set[Tuple[Change, str]]], None] = None,
                watcher_cls: Type[AllWatcher] = PythonWatcher,
                debounce=400,
                min_sleep=100):
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
    """

    process = _start_process(target=target, args=args, kwargs=kwargs)
    reloads = 0

    for changes in watch(path, watcher_cls=watcher_cls, debounce=debounce, min_sleep=min_sleep):
        callback and callback(changes)
        _stop_process(process)
        process = _start_process(target=target, args=args, kwargs=kwargs)
        reloads += 1
    _stop_process(process)
    return reloads


async def arun_process(path: Union[Path, str], target: Callable, *,
                       args: Tuple[Any] = (),
                       kwargs: Dict[str, Any] = None,
                       callback: Callable[[Set[Tuple[Change, str]]], Awaitable] = None,
                       watcher_cls: Type[AllWatcher] = PythonWatcher,
                       debounce=400,
                       min_sleep=100):
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
