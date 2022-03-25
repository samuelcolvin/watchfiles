import argparse
import logging
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Optional

from .filters import DefaultFilter, PythonFilter
from .run import run_process, import_string, detect_target_type
from .version import VERSION

logger = logging.getLogger('watchfiles.cli')


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(path)
    else:
        return path.resolve()


def cli(*args_: str) -> None:  # noqa: C901 (ignore complexity)
    """
    Watch one or more directories and execute a python function on file changes.

    Note: only changes to python files will prompt the function to be restarted,
    use `--extensions` to watch more file types.

    See https://watchfiles.helpmanual.io/cli/ for more information.
    """
    args = args_ or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog='watchfiles',
        description=dedent((cli.__doc__ or '').strip('\n')),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('command', nargs='...', help='Path to python function to execute')
    parser.add_argument(
        '--path', nargs='*', default='.', help='Filesystem paths to watch, defaults to current directory'
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
        default='python',
        choices=['python', 'default', 'all'],
        help='which files to watch, defaults to "python" files',
    )
    parser.add_argument(
        '--ignore-paths',
        nargs='*',
        type=str,
        default=[],
        help='Specify directories to ignore',
    )
    parser.add_argument(
        '--extensions',
        nargs='*',
        type=str,
        default=(),
        help='Extra file extensions to watch, applies only if "--filter" is "python"',
    )
    # parser.add_argument(
    #     '--args',
    #     '-a',
    #     nargs=argparse.REMAINDER,
    #     help='Arguments for argv inside executed function',
    # )
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s v{VERSION}')
    arg_namespace = parser.parse_args(args)

    log_level = getattr(logging, arg_namespace.verbosity.upper())
    hdlr = logging.StreamHandler()
    hdlr.setLevel(log_level)
    hdlr.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    wg_logger = logging.getLogger('watchfiles')
    wg_logger.addHandler(hdlr)
    wg_logger.setLevel(log_level)

    target_type = detect_target_type(arg_namespace.command)
    if target_type == 'function':
        sys.path.append(os.getcwd())
        try:
            import_string(arg_namespace.command)
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

    paths_str = ', '.join(f'"{p}"' for p in paths)
    logger.info('watching %s and reloading "%s" as %s on changes...', paths_str, arg_namespace.function, target_type)

    watch_filter_kwargs: Dict[str, Any] = {}
    if arg_namespace.ignore_paths:
        if arg_namespace.filter != 'all':
            watch_filter_kwargs['ignore_paths'] = [Path(p).resolve() for p in arg_namespace.ignore_paths]
        else:
            logger.warning('"--ignore-paths" argument ignored as "all" filter was selected')

    if arg_namespace.extensions:
        if arg_namespace.filter == 'python':
            watch_filter_kwargs['extra_extensions'] = arg_namespace.extensions
        else:
            logger.warning('"--extensions" argument ignored as "%s" filter was selected', arg_namespace.filter)

    if arg_namespace.filter == 'python':
        watch_filter: Optional[DefaultFilter] = PythonFilter(**watch_filter_kwargs)
    elif arg_namespace.filter == 'default':
        watch_filter = DefaultFilter(**watch_filter_kwargs)
    else:
        watch_filter = None

    run_process(
        *paths,
        target=arg_namespace.command,
        watch_filter=watch_filter,
        debug=arg_namespace.verbosity == 'debug',
    )
