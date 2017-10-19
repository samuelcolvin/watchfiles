import argparse
import contextlib
import logging
import os
import sys
from importlib import import_module
from multiprocessing import set_start_method
from pathlib import Path
from typing import Optional

from watchgod import run_process

logger = logging.getLogger('watchgod.cli')


def import_string(dotted_path):
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


@contextlib.contextmanager
def set_tty(tty_path):
    if tty_path:
        with open(tty_path) as tty:
            sys.stdin = tty
            yield
    else:
        # currently on windows tty_path is None and there's nothing we can do here
        yield


def run_function(function: str, tty_path: Optional[str]):
    with set_tty(tty_path):
        func = import_string(function)
        func()


def callback(changes):
    logger.info('%d files changed, reloading', len(changes))


def cli(*args):
    args = args or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog='watchgod',
        description='Watch a directory and execute a python function on changes.'
    )
    parser.add_argument('function', help='Path to python function to execute.')
    parser.add_argument('path', nargs='?', default='.', help='Filesystem path to watch, defaults to current directory.')
    parser.add_argument('--verbosity', nargs='?', type=int, default=1, help='0, 1 (default) or 2')
    arg_namespace = parser.parse_args(args)

    log_level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[arg_namespace.verbosity]
    hdlr = logging.StreamHandler()
    hdlr.setLevel(log_level)
    hdlr.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    wg_logger = logging.getLogger('watchgod')
    wg_logger.addHandler(hdlr)
    wg_logger.setLevel(log_level)

    try:
        import_string(arg_namespace.function)
    except ImportError as e:
        print('ImportError: {}'.format(e), file=sys.stderr)
        return sys.exit(1)

    path = Path(arg_namespace.path)
    if not path.is_dir():
        print('path "{}" is not a directory'.format(path), file=sys.stderr)
        return sys.exit(1)
    path = path.resolve()

    try:
        tty_path = os.ttyname(sys.stdin.fileno())
    except OSError:
        # fileno() always fails with pytest
        tty_path = '/dev/tty'
    except AttributeError:
        # on windows. No idea of a better solution
        tty_path = None
    logger.info('watching "%s/" and reloading "%s" on changes...', path, arg_namespace.function)
    set_start_method('spawn')
    run_process(path, run_function, args=(arg_namespace.function, tty_path), callback=callback)
