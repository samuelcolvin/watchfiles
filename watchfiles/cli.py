import argparse
import logging
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, List, Tuple, Union

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
    Watch one or more directories and execute a python function on file changes.

    See https://watchfiles.helpmanual.io/cli/ for more information.
    """
    args = args_ or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog='watchfiles',
        description=dedent((cli.__doc__ or '').strip('\n')),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('path', help='Filesystem path to watch, defaults to current directory')
    # argparse.PARSER ("A...") seems to be an undocumented required variant of argparse.REMAINDER ("...")
    parser.add_argument('target', nargs='A...', help='Command to run or dotted path to function')

    parser.add_argument('--extra-path', nargs='*', help='Extra paths to watch')
    parser.add_argument(
        '--target-type',
        nargs='?',
        type=str,
        default='auto',
        choices=['command', 'function', 'auto'],
        help='Whether the command should be a shell command or a python function, defaults to inference',
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
        '--filter',
        nargs='?',
        type=str,
        default='default',
        help=(
            'Which files to watch, defaults to "default" which uses the "DefaultFilter", "all" uses no filter, '
            '"python" uses the "PythonFilter", any other value is interpreted as a python function path'
        ),
    )
    parser.add_argument(
        '--ignore-paths',
        nargs='*',
        type=str,
        default=[],
        help='Specify directories to ignore',
    )
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s v{VERSION}')
    arg_namespace = parser.parse_args(args)

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
        # check that the import works before continuing
        import_exit(arg_namespace.target)

    raw_paths = [arg_namespace.path]
    if arg_namespace.extra_path:
        raw_paths.extend(arg_namespace.extra_path)

    try:
        paths = [resolve_path(p) for p in raw_paths]
    except FileNotFoundError as e:
        print(f'path "{e}" does not exist', file=sys.stderr)
        sys.exit(1)
        return  # required to molify mypy

    watch_filter, watch_filter_str = build_filter(arg_namespace.filter, arg_namespace.ignore_paths)

    logger.info(
        'watchfiles 👀  path=%s target="%s" (%s) filter=%s...',
        ', '.join(f'"{p.relative_to(Path.cwd())}"' for p in paths),
        ' '.join(arg_namespace.target),
        target_type,
        watch_filter_str,
    )

    run_process(
        *paths,
        target=arg_namespace.target,
        target_type=target_type,
        watch_filter=watch_filter,
        debug=arg_namespace.verbosity == 'debug',
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
    filter_name: str, ignore_paths_str: List[str]
) -> Tuple[Union[None, DefaultFilter, Callable[[Change, str], bool]], str]:
    ignore_paths = [Path(p).resolve() for p in ignore_paths_str]

    if filter_name == 'default':
        return DefaultFilter(ignore_paths=ignore_paths), 'DefaultFilter'
    elif filter_name == 'python':
        return PythonFilter(ignore_paths=ignore_paths), 'PythonFilter'
    elif filter_name == 'all':
        if ignore_paths:
            logger.warning('"--ignore-paths" argument ignored as "all" filter was selected')
        return None, 'no filter'

    watch_filter_cls = import_exit(filter_name)
    if issubclass(watch_filter_cls, DefaultFilter):
        return watch_filter_cls(ignore_paths=ignore_paths), watch_filter_cls.__name__

    if ignore_paths:
        logger.warning('"--ignore-paths" argument ignored as filter is not a subclass of DefaultFilter')

    if issubclass(watch_filter_cls, BaseFilter):
        return watch_filter_cls(), watch_filter_cls.__name__
    else:
        return watch_filter_cls, repr(watch_filter_cls)
