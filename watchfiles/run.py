import contextlib
import json
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
from importlib import import_module
from multiprocessing import get_context
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Generator, List, Optional, Set, Tuple, Union

import anyio

from .filters import PythonFilter
from .main import Change, FileChange, awatch, watch

if TYPE_CHECKING:
    try:
        from typing import Literal
    except ImportError:
        from typing_extensions import Literal  # type: ignore[misc]

__all__ = 'run_process', 'arun_process', 'detect_target_type', 'import_string'
logger = logging.getLogger('watchfiles.main')


def run_process(
    *paths: Union[Path, str],
    target: Union[str, List[str], Callable[..., Any]],
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    target_type: "Literal['function', 'command', 'auto']" = 'auto',
    callback: Optional[Callable[[Set[FileChange]], None]] = None,
    watch_filter: Optional[Callable[[Change, str], bool]] = PythonFilter(),
    debounce: int = 1_600,
    step: int = 50,
    debug: bool = False,
) -> int:
    """
    Run a process and restart it upon file changes.

    `run_process` can work in two ways:

    * Using `multiprocessing.Process` (technically `multiprocessing.get_context('spawn').Process`
        to avoid forking and improve code reload) to run a python function
    * Or, use `subprocess.Popen` to run a shell-like command


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
    if target_type == 'auto':
        target_type = detect_target_type(target)

    logger.debug('running "%s" as %s', target, target_type)
    process = start_process(target, target_type, args, kwargs)
    reloads = 0

    try:
        for changes in watch(
            *paths, watch_filter=watch_filter, debounce=debounce, step=step, debug=debug, raise_interrupt=False
        ):
            callback and callback(changes)
            process.stop()
            process = start_process(target, target_type, args, kwargs, changes)
            reloads += 1
    finally:
        process.stop()
    return reloads


async def arun_process(
    *paths: Union[Path, str],
    target: Union[str, List[str], Callable[..., Any]],
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    target_type: "Literal['function', 'command', 'auto']" = 'auto',
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

    if target_type == 'auto':
        target_type = detect_target_type(target)

    logger.debug('running "%s" as %s', target, target_type)
    process = await anyio.to_thread.run_sync(start_process, target, target_type, args, kwargs)
    reloads = 0

    async for changes in awatch(
        *paths, watch_filter=watch_filter, debounce=debounce, step=step, debug=debug, raise_interrupt=False
    ):
        if callback is not None:
            r = callback(changes)
            if inspect.isawaitable(r):
                await r

        await anyio.to_thread.run_sync(process.stop)
        process = await anyio.to_thread.run_sync(start_process, target, target_type, args, kwargs, changes)
        reloads += 1
    await anyio.to_thread.run_sync(process.stop)
    return reloads


# Use spawn context to make sure code run in subprocess
# does not reuse imported modules in main process/context
spawn_context = get_context('spawn')


def start_process(
    target: Union[str, List[str], Callable[..., Any]],
    target_type: "Literal['function', 'command']",
    args: Tuple[Any, ...],
    kwargs: Optional[Dict[str, Any]],
    changes: Optional[Set[FileChange]] = None,
) -> 'CombinedProcess':
    if changes is None:
        changes_env_var = '[]'
    else:
        changes_env_var = json.dumps([[c.raw_str(), p] for c, p in changes])

    os.environ['WATCHFILES_CHANGES'] = changes_env_var

    process: 'Union[SpawnProcess, subprocess.Popen[bytes]]'
    if target_type == 'function':
        kwargs = kwargs or {}
        if isinstance(target, list):
            target = target[0]

        if isinstance(target, str):
            args = target, get_tty_path(), args, kwargs
            target_ = run_function
            kwargs = {}
        else:
            assert not isinstance(target, (str, list))
            target_ = target

        process = spawn_context.Process(target=target_, args=args, kwargs=kwargs)
        process.start()
    else:
        if isinstance(target, str):
            popen_args = shlex.split(target)
        else:
            assert isinstance(target, list)
            popen_args = target

        process = subprocess.Popen(popen_args)
    return CombinedProcess(process)


def detect_target_type(target: Union[str, List[str], Callable[..., Any]]) -> "Literal['function', 'command']":
    """
    Used by [`run_process`][watchfiles.run_process], [`arun_process`][watchfiles.arun_process]
    and indirectly the CLI to determine the target type with `target_type` is `auto`.

    Detects the target type - either `function` or `command`. This method is only called with `target_type='auto'`.

    The following logic is employed:

    * If `target` is not a string or list of strings, it is assumed to be a function
    * If `target` is a list with more than one element, it is assumed to be a command
    * If `target` (or the first element of target) ends with `.py` or `.sh`, it is assumed to be a command
    * Otherwise, the target is assumed to be a function if it matches the regex `[a-zA-Z0-9_]+(\\.[a-zA-Z0-9_]+)+`

    If this logic does not work for you, specify the target type explicitly using the `target_type` function argument
    or `--target-type` command line argument.

    Args:
        target: The target value

    Returns:
        either `'function'` or `'command'`
    """
    if not isinstance(target, (str, list, tuple)):
        return 'function'

    if isinstance(target, list):
        if len(target) > 1:
            return 'command'
        target_str = target[0]
    else:
        target_str = target

    if not target_str.endswith(('.py', '.sh')) and re.fullmatch(r'[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+', target_str):
        return 'function'
    else:
        return 'command'


class CombinedProcess:
    def __init__(self, p: 'Union[SpawnProcess, subprocess.Popen[bytes]]'):
        self._p = p
        assert self.pid is not None, 'process not yet spawned'

    def stop(self) -> None:
        os.environ.pop('WATCHFILES_CHANGES', None)
        if self.is_alive():
            logger.debug('stopping process...')

            os.kill(self.pid, signal.SIGINT)
            self.join(5)
            if self.exitcode is None:
                logger.warning('process has not terminated, sending SIGKILL')
                os.kill(self.pid, signal.SIGKILL)
                self.join(1)
            else:
                logger.debug('process stopped')
        else:
            logger.warning('process already dead, exit code: %d', self.exitcode)

    def is_alive(self) -> bool:
        if isinstance(self._p, SpawnProcess):
            return self._p.is_alive()
        else:
            return self._p.poll() is None

    @property
    def pid(self) -> int:
        # we check the process has always been spawned when CombinedProcess is initialised
        return self._p.pid  # type: ignore[return-value]

    def join(self, timeout: int) -> None:
        if isinstance(self._p, SpawnProcess):
            self._p.join(timeout)
        else:
            self._p.wait(timeout)

    @property
    def exitcode(self) -> Optional[int]:
        if isinstance(self._p, SpawnProcess):
            return self._p.exitcode
        else:
            return self._p.returncode


def run_function(function: str, tty_path: Optional[str], args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
    with set_tty(tty_path):
        func = import_string(function)
        func(*args, **kwargs)


def import_string(dotted_path: str) -> Any:
    """
    Stolen approximately from django. Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import fails.
    """
    try:
        module_path, class_name = dotted_path.strip(' ').rsplit('.', 1)
    except ValueError as e:
        raise ImportError(f'"{dotted_path}" doesn\'t look like a module path') from e

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute') from e


def get_tty_path() -> Optional[str]:  # pragma: no cover
    """
    Return the path to the current TTY, if any.

    Virtually impossible to test in pytest, hence no cover.
    """
    try:
        return os.ttyname(sys.stdin.fileno())
    except OSError:
        # fileno() always fails with pytest
        return '/dev/tty'
    except AttributeError:
        # on Windows. No idea of a better solution
        return None


@contextlib.contextmanager
def set_tty(tty_path: Optional[str]) -> Generator[None, None, None]:
    if tty_path:
        try:
            with open(tty_path) as tty:  # pragma: no cover
                sys.stdin = tty
                yield
        except OSError:
            # eg. "No such device or address: '/dev/tty'", see https://github.com/samuelcolvin/watchfiles/issues/40
            yield
    else:
        # currently on windows tty_path is None and there's nothing we can do here
        yield
