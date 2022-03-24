import json
import logging
import os
import signal
from multiprocessing import get_context
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple, Union, cast

import anyio

from .filters import PythonFilter
from .main import Change, FileChange, awatch, watch

__all__ = 'run_process', 'arun_process'
logger = logging.getLogger('watchfiles.main')


def run_process(
    *paths: Union[Path, str],
    target: Callable[..., Any],
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
    target: Callable[..., Any],
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


# Use spawn context to make sure code run in subprocess
# does not reuse imported modules in main process/context
spawn_context = get_context('spawn')


def _start_process(
    target: Callable[..., Any],
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
