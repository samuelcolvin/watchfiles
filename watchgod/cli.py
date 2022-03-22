import argparse
import contextlib
import logging
import os
import sys
from importlib import import_module
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Generator, List, Optional, Sized

from .filters import PythonFilter
from .main import run_process

logger = logging.getLogger('watchgod.cli')


def import_string(dotted_path: str) -> Any:
    """
    Stolen approximately from django. Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import fails.
    """
    try:
        module_path, class_name = dotted_path.strip(' ').rsplit('.', 1)
    except ValueError as e:
        raise ImportError('"{}" doesn\'t look like a module path'.format(dotted_path)) from e

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError('Module "{}" does not define a "{}" attribute'.format(module_path, class_name)) from e


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(path)
    else:
        return path.resolve()


@contextlib.contextmanager
def set_tty(tty_path: Optional[str]) -> Generator[None, None, None]:
    if tty_path:
        try:
            with open(tty_path) as tty:  # pragma: no cover
                sys.stdin = tty
                yield
        except OSError:
            # eg. "No such device or address: '/dev/tty'", see https://github.com/samuelcolvin/watchgod/issues/40
            yield
    else:
        # currently on windows tty_path is None and there's nothing we can do here
        yield


def run_function(function: str, tty_path: Optional[str]) -> None:
    with set_tty(tty_path):
        func = import_string(function)
        func()


def callback(changes: Sized) -> None:
    logger.info('%d files changed, reloading', len(changes))


def sys_argv(function: str) -> List[str]:
    """
    Remove watchgod-related arguments from sys.argv and prepend with func's script path.
    """
    bases_ = function.split('.')[:-1]  # remove function and leave only file path
    base = os.path.join(*bases_) + '.py'
    base = os.path.abspath(base)
    for i, arg in enumerate(sys.argv):
        if arg in {'-a', '--args'}:
            return [base] + sys.argv[i + 1 :]
    return [base]  # strip all args if no additional args were provided


def cli(*args_: str) -> None:
    """
    Watch one or more directories and execute a python function on changes.

    Note: only changes to python files will prompt the function to be restarted, use `--extensions` to watch
    more file types.
    """
    args = args_ or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog='watchgod',
        description=dedent((cli.__doc__ or '').strip('\n')),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('function', help='Path to python function to execute.')
    parser.add_argument(
        'paths', nargs='*', default='.', help='Filesystem paths to watch, defaults to current directory.'
    )
    parser.add_argument('--verbosity', nargs='?', type=int, default=1, help='0, 1 (default) or 2')
    parser.add_argument(
        '--ignore-paths',
        nargs='*',
        type=str,
        default=[],
        help='Specify paths to files or directories to ignore their updates',
    )
    parser.add_argument('--extensions', nargs='*', type=str, default=(), help='Extra file extensions to watch')
    parser.add_argument(
        '--args',
        '-a',
        nargs=argparse.REMAINDER,
        help='Arguments for argparser inside executed function. Ex.: module.func path --args --inner arg -v',
    )
    arg_namespace = parser.parse_args(args)

    log_level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[arg_namespace.verbosity]
    hdlr = logging.StreamHandler()
    hdlr.setLevel(log_level)
    hdlr.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    wg_logger = logging.getLogger('watchgod')
    wg_logger.addHandler(hdlr)
    wg_logger.setLevel(log_level)

    sys.path.append(os.getcwd())
    try:
        import_string(arg_namespace.function)
    except ImportError as e:
        print(f'ImportError: {e}', file=sys.stderr)
        sys.exit(1)
        return

    try:
        paths = [resolve_path(p) for p in arg_namespace.paths]
    except FileNotFoundError as e:
        print(f'path "{e}" does not exist', file=sys.stderr)
        sys.exit(1)
        return

    try:
        tty_path: Optional[str] = os.ttyname(sys.stdin.fileno())
    except OSError:
        # fileno() always fails with pytest
        tty_path = '/dev/tty'
    except AttributeError:
        # on windows. No idea of a better solution
        tty_path = None
    paths_str = ', '.join(f'"{p}"' for p in paths)
    logger.info('watching %s and reloading "%s" on changes...', paths_str, arg_namespace.function)
    sys.argv = sys_argv(arg_namespace.function)

    watch_filter_kwargs: Dict[str, Any] = {}
    if arg_namespace.ignore_paths:
        watch_filter_kwargs['ignore_paths'] = [Path(p).resolve() for p in arg_namespace.ignore_paths]

    if arg_namespace.extensions:
        watch_filter_kwargs['extra_extensions'] = arg_namespace.extensions

    run_process(
        *paths,
        target=run_function,
        args=(arg_namespace.function, tty_path),
        callback=callback,
        watch_filter=PythonFilter(**watch_filter_kwargs),
    )
