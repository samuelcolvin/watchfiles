import argparse
import logging
import os
import shlex
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, List, Optional, Tuple, Union, cast

from . import Change
from .filters import BaseFilter, DefaultFilter, PythonFilter
from .run import detect_target_type, import_string, run_process
from .version import VERSION

logger = logging.getLogger('watchfiles.cli')


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(path)
    else:
        return path.resolve()


def cli(*args_: str) -> None:
    """
    Watch one or more directories and execute either a shell command or a python function on file changes.

    Example of watching the current directory and calling a python function:

        watchfiles foobar.main

    Example of watching python files in two local directories and calling a shell command:

        watchfiles --filter python 'pytest --lf' src tests

    See https://watchfiles.helpmanual.io/cli/ for more information.
    """
    args = args_ or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog='watchfiles',
        description=dedent((cli.__doc__ or '').strip('\n')),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('target', help='Command or dotted function path to run')
    parser.add_argument(
        'paths', nargs='*', default='.', help='Filesystem paths to watch, defaults to current directory'
    )

    parser.add_argument(
        '--ignore-paths',
        nargs='?',
        type=str,
        help=(
            'Specify directories to ignore, '
            'to ignore multiple paths use a comma as separator, e.g. "env" or "env,node_modules"'
        ),
    )
    parser.add_argument(
        '--target-type',
        nargs='?',
        type=str,
        default='auto',
        choices=['command', 'function', 'auto'],
        help=(
            'Whether the target should be intercepted as a shell command or a python function, '
            'defaults to "auto" which infers the target type from the target string'
        ),
    )
    parser.add_argument(
        '--filter',
        nargs='?',
        type=str,
        default='default',
        help=(
            'Which files to watch, defaults to "default" which uses the "DefaultFilter", '
            '"python" uses the "PythonFilter", "all" uses no filter, '
            'any other value is interpreted as a python function/class path which is imported'
        ),
    )
    parser.add_argument(
        '--args',
        nargs='?',
        type=str,
        help='Arguments to set on sys.argv before calling target function, used only if the target is a function',
    )
    parser.add_argument('--env', action='store_true', help='Pass environment variables to target')
    parser.add_argument('--verbose', action='store_true', help='Set log level to "debug", wins over `--verbosity`')
    parser.add_argument(
        '--non-recursive', action='store_true', help='Do not watch for changes in sub-directories recursively'
    )
    parser.add_argument(
        '--verbosity',
        nargs='?',
        type=str,
        default='info',
        choices=['warning', 'info', 'debug'],
        help='Log level, defaults to "info"',
    )
    parser.add_argument(
        '--sigint-timeout',
        nargs='?',
        type=int,
        default=5,
        help='How long to wait for the sigint timeout before sending sigkill.',
    )
    parser.add_argument(
        '--sigkill-timeout',
        nargs='?',
        type=int,
        default=1,
        help='How long to wait for the sigkill timeout before issuing a timeout exception.',
    )
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s v{VERSION}')
    arg_namespace = parser.parse_args(args)

    if arg_namespace.verbose:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, arg_namespace.verbosity.upper())

    hdlr = logging.StreamHandler()
    hdlr.setLevel(log_level)
    hdlr.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    wg_logger = logging.getLogger('watchfiles')
    wg_logger.addHandler(hdlr)
    wg_logger.setLevel(log_level)

    if arg_namespace.target_type == 'auto':
        target_type = detect_target_type(arg_namespace.target)
    else:
        target_type = arg_namespace.target_type

    if target_type == 'function':
        logger.debug('target_type=function, attempting import of "%s"', arg_namespace.target)
        import_exit(arg_namespace.target)
        if arg_namespace.args:
            sys.argv = [arg_namespace.target] + shlex.split(arg_namespace.args)
    elif arg_namespace.args:
        logger.warning('--args is only used when the target is a function')

    try:
        paths = [resolve_path(p) for p in arg_namespace.paths]
    except FileNotFoundError as e:
        print(f'path "{e}" does not exist', file=sys.stderr)
        sys.exit(1)

    watch_filter, watch_filter_str = build_filter(arg_namespace.filter, arg_namespace.ignore_paths)

    logger.info(
        'watchfiles v%s 👀  path=%s target="%s" (%s) filter=%s...',
        VERSION,
        ', '.join(f'"{p}"' for p in paths),
        arg_namespace.target,
        target_type,
        watch_filter_str,
    )

    run_process(
        *paths,
        target=arg_namespace.target,
        target_type=target_type,
        watch_filter=watch_filter,
        debug=log_level == logging.DEBUG,
        sigint_timeout=arg_namespace.sigint_timeout,
        sigkill_timeout=arg_namespace.sigkill_timeout,
        recursive=not arg_namespace.non_recursive,
        env=arg_namespace.env,
    )


def import_exit(function_path: str) -> Any:
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.append(cwd)

    try:
        return import_string(function_path)
    except ImportError as e:
        print(f'ImportError: {e}', file=sys.stderr)
        sys.exit(1)


def build_filter(
    filter_name: str, ignore_paths_str: Optional[str]
) -> Tuple[Union[None, DefaultFilter, Callable[[Change, str], bool]], str]:
    ignore_paths: List[Path] = []
    if ignore_paths_str:
        ignore_paths = [Path(p).resolve() for p in ignore_paths_str.split(',')]

    if filter_name == 'default':
        return DefaultFilter(ignore_paths=ignore_paths), 'DefaultFilter'
    elif filter_name == 'python':
        return PythonFilter(ignore_paths=ignore_paths), 'PythonFilter'
    elif filter_name == 'all':
        if ignore_paths:
            logger.warning('"--ignore-paths" argument ignored as "all" filter was selected')
        return None, '(no filter)'

    watch_filter_cls = import_exit(filter_name)
    if isinstance(watch_filter_cls, type) and issubclass(watch_filter_cls, DefaultFilter):
        return watch_filter_cls(ignore_paths=ignore_paths), watch_filter_cls.__name__

    if ignore_paths:
        logger.warning('"--ignore-paths" argument ignored as filter is not a subclass of DefaultFilter')

    if isinstance(watch_filter_cls, type) and issubclass(watch_filter_cls, BaseFilter):
        return watch_filter_cls(), watch_filter_cls.__name__
    else:
        watch_filter = cast(Callable[[Change, str], bool], watch_filter_cls)
        return watch_filter, repr(watch_filter_cls)
