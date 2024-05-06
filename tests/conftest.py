import logging
import os
import sys
from pathlib import Path
from threading import Thread
from time import sleep, time
from typing import TYPE_CHECKING, Any, List, Set, Tuple

import pytest


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
    files = {p: p.read_text() for p in d.glob('**/*.*')}

    yield d

    for f in d.glob('**/*.*'):
        f.unlink()

    for path, content in files.items():
        path.write_text(content)


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
    def __init__(self, changes: ChangesType, exit_code: str):
        self.iter_changes = iter(changes)
        self.exit_code = exit_code
        self.watch_count = 0

    def watch(self, debounce_ms: int, step_ms: int, timeout_ms: int, cancel_event):
        try:
            change = next(self.iter_changes)
        except StopIteration:
            return self.exit_code
        else:
            self.watch_count += 1
            return change

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        pass


if TYPE_CHECKING:
    from typing import Literal, Protocol

    class MockRustType(Protocol):
        def __call__(
            self, changes: ChangesType, *, exit_code: Literal['signal', 'stop', 'timeout'] = 'stop'
        ) -> Any: ...


@pytest.fixture
def mock_rust_notify(mocker):
    def mock(changes: ChangesType, *, exit_code: str = 'stop'):
        m = MockRustNotify(changes, exit_code)
        mocker.patch('watchfiles.main.RustNotify', return_value=m)
        return m

    return mock


@pytest.fixture(autouse=True)
def ensure_logging_framework_not_altered():
    """
    https://github.com/pytest-dev/pytest/issues/5743
    """
    wg_logger = logging.getLogger('watchfiles')
    before_handlers = list(wg_logger.handlers)

    yield

    wg_logger.handlers = before_handlers


py_code = """
import sys
from pathlib import Path

def foobar():
    Path('sentinel').write_text(' '.join(map(str, sys.argv[1:])))
"""


@pytest.fixture
def create_test_function(tmp_work_path: Path):
    original_path = sys.path[:]

    (tmp_work_path / 'test_function.py').write_text(py_code)
    sys.path.append(str(tmp_work_path))

    yield 'test_function.foobar'

    sys.path = original_path


@pytest.fixture
def reset_argv():
    original_argv = sys.argv[:]

    yield

    sys.argv = original_argv


class TimeTaken:
    def __init__(self, name: str, min_time: int, max_time: int):
        self.name = name
        self.min_time = min_time
        self.max_time = max_time
        self.start = time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        diff = (time() - self.start) * 1000
        if exc_type is None:
            if diff > self.max_time:
                pytest.fail(f'{self.name} code took too long: {diff:0.2f}ms')
                return
            elif diff < self.min_time:
                pytest.fail(f'{self.name} code did not take long enough: {diff:0.2f}ms')
                return

        print(f'{self.name} code took {diff:0.2f}ms')


@pytest.fixture
def time_taken(request):
    def time_taken(min_time: int, max_time: int):
        return TimeTaken(request.node.name, min_time, max_time)

    return time_taken


class SetEnv:
    def __init__(self):
        self.envars = set()

    def __call__(self, name, value):
        self.envars.add(name)
        os.environ[name] = value

    def clear(self):
        for n in self.envars:
            os.environ.pop(n)


@pytest.fixture
def env():
    setenv = SetEnv()

    yield setenv

    setenv.clear()
