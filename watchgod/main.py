import logging
import os
import signal
from multiprocessing import Process
from pathlib import Path
from time import sleep, time
from typing import Any, Callable, Dict, Tuple, Type, Union

from .watcher import AllWatcher, DefaultWatcher, PythonWatcher

__all__ = 'watch', 'run_process'
logger = logging.getLogger('watchgod.main')


def unix_ms():
    return int(round(time() * 1000))


def watch(path: Union[Path, str], *,
          watcher_cls: Type[AllWatcher]=DefaultWatcher,
          debounce=400,
          min_sleep=100):
    """
    Watch a directory and yield a set of changes whenever files change in that directory or its subdirectories.
    """
    p = watcher_cls(path)
    try:
        while True:
            start = unix_ms()
            changes = p.check()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('time=%0.0fms files=%d changes=%d', unix_ms() - start, len(p.files), len(changes))

            if changes:
                yield changes
            sleep_time = debounce - (unix_ms() - start)
            if sleep_time < min_sleep:
                sleep_time = min_sleep
            sleep(sleep_time / 1000)
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt, exiting')


def _start_process(target, args, kwargs):
    process = Process(target=target, args=args, kwargs=kwargs or {})
    process.start()
    return process


def run_process(path: Union[Path, str], target: Callable, *,
                args: Tuple[Any]=(),
                kwargs: Dict[str, Any]=None,
                watcher_cls: Type[AllWatcher]=PythonWatcher,
                debounce=400,
                min_sleep=100):
    """
    Run a function in a subprocess using multiprocessing.Process, restart it whenever files change in path.
    """

    process = _start_process(target=target, args=args, kwargs=kwargs)
    reloads = 0

    for _ in watch(path, watcher_cls=watcher_cls, debounce=debounce, min_sleep=min_sleep):
        if process.is_alive():
            logger.debug('stopping server process...')
            os.kill(process.pid, signal.SIGINT)
            process.join(5)
            if process.exitcode is None:
                logger.warning('process has not terminated, sending SIGKILL')
                os.kill(process.pid, signal.SIGKILL)
                process.join(1)
            else:
                logger.debug('process stopped')
        else:
            logger.warning('server process already dead, exit code: %d', process.exitcode)

        process = _start_process(target=target, args=args, kwargs=kwargs)
        reloads += 1
    return reloads
