import logging
import os
from pathlib import Path
from threading import Thread
from time import sleep
from typing import Callable, Dict, List, Set, Tuple, Union

import pytest

PathDict = Dict[str, Union['PathDict', str, bytes]]


def mktree(root_dir: Path, path_dict: PathDict):
    """
    Create a tree of files from a dictionary of name > content lookups.
    """
    for name, content in path_dict.items():
        path = root_dir / name

        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            mktree(path, content)
        elif isinstance(content, str):
            path.write_text(content)
        else:
            assert isinstance(content, bytes), 'content must be a dict, str or bytes'
            path.write_bytes(content)


@pytest.fixture
def tmp_work_path(tmp_path: Path):
    """
    Create a temporary working directory.
    """
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)

    yield tmp_path

    os.chdir(previous_cwd)


@pytest.fixture(scope='session')
def test_dir():
    d = Path(__file__).parent / 'test_files'

    yield d

    for f in d.iterdir():
        f.unlink()

    print('test_dir cleanup')
    (d / 'a.txt').write_text('a')
    (d / 'b.txt').write_text('b')
    (d / 'c.txt').write_text('c')


@pytest.fixture(autouse=True)
def anyio_backend():
    return 'asyncio'


def sleep_write(path: Path):
    sleep(0.1)
    path.write_text('hello')


@pytest.fixture
def write_soon():
    threads = []

    def start(path: Path):
        thread = Thread(target=sleep_write, args=(path,))
        thread.start()
        threads.append(thread)

    yield start

    for t in threads:
        t.join()


ChangesType = List[Set[Tuple[int, str]]]


class MockRustNotify:
    def __init__(self, changes: ChangesType):
        self.iter_changes = iter(changes)
        self.watch_count = 0

    def watch(self, debounce_ms: int, step_ms: int, cancel_event):
        try:
            change = next(self.iter_changes)
        except StopIteration:
            return None
        else:
            self.watch_count += 1
            return change


MockRustType = Callable[[ChangesType], MockRustNotify]


@pytest.fixture
def mock_rust_notify(mocker):
    def mock(changes: ChangesType):
        m = MockRustNotify(changes)
        mocker.patch('watchgod.main.RustNotify', return_value=m)
        return m

    return mock


@pytest.fixture(autouse=True)
def ensure_logging_framework_not_altered():
    """
    https://github.com/pytest-dev/pytest/issues/5743
    """
    wg_logger = logging.getLogger('watchgod')
    before_handlers = list(wg_logger.handlers)

    yield

    wg_logger.handlers = before_handlers
