import asyncio
import re
import threading
from time import sleep

from pytest_toolbox import mktree

from watchgod import AllWatcher, Change, DefaultWatcher, PythonWatcher, awatch, watch

tree = {
    'foo': {
        'bar.txt': 'bar',
        'spam.py': 'whatever',
        'spam.pyc': 'splosh',
        'recursive_dir': {
            'a.js': 'boom',
        },
        '.git': {
            'x': 'y',
        }
    }
}


def test_add(tmpdir):
    watcher = AllWatcher(str(tmpdir))
    changes = watcher.check()
    assert changes == set()

    sleep(0.01)
    tmpdir.join('foo.txt').write('foobar')

    changes = watcher.check()
    assert changes == {(Change.added, str(tmpdir.join('foo.txt')))}


def test_modify(tmpdir):
    mktree(tmpdir, tree)

    watcher = AllWatcher(str(tmpdir))
    assert watcher.check() == set()

    sleep(0.01)
    tmpdir.join('foo/bar.txt').write('foobar')

    assert watcher.check() == {(Change.modified, str(tmpdir.join('foo/bar.txt')))}


def test_delete(tmpdir):
    mktree(tmpdir, tree)

    watcher = AllWatcher(str(tmpdir))

    sleep(0.01)
    tmpdir.join('foo/bar.txt').remove()

    assert watcher.check() == {(Change.deleted, str(tmpdir.join('foo/bar.txt')))}


def test_ignore_file(tmpdir):
    mktree(tmpdir, tree)

    watcher = DefaultWatcher(str(tmpdir))

    sleep(0.01)
    tmpdir.join('foo/spam.pyc').write('foobar')

    assert watcher.check() == set()


def test_ignore_dir(tmpdir):
    mktree(tmpdir, tree)

    watcher = DefaultWatcher(str(tmpdir))

    sleep(0.01)
    tmpdir.join('foo/.git/abc').write('xxx')

    assert watcher.check() == set()


def test_python(tmpdir):
    mktree(tmpdir, tree)

    watcher = PythonWatcher(str(tmpdir))

    sleep(0.01)
    tmpdir.join('foo/spam.py').write('xxx')
    tmpdir.join('foo/bar.txt').write('xxx')

    assert watcher.check() == {(Change.modified, str(tmpdir.join('foo/spam.py')))}


def test_watch(mocker):
    class FakeWatcher:
        def __init__(self, path):
            self._results = iter([
                {'r1'},
                set(),
                {'r2'},
                set(),
            ])

        def check(self):
            return next(self._results)

    iter_ = watch('xxx', watcher_cls=FakeWatcher, debounce=5, normal_sleep=2, min_sleep=1)
    assert next(iter_) == {'r1'}
    assert next(iter_) == {'r2'}


def test_watch_stop():
    class FakeWatcher:
        def __init__(self, path):
            self._results = iter([
                {'r1'},
                set(),
                {'r2'},
            ])

        def check(self):
            return next(self._results)

    stop_event = threading.Event()
    stop_event.set()
    ans = []
    for c in watch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=1, stop_event=stop_event):
        ans.append(c)
    assert ans == []


def test_watch_keyboard_error():
    class FakeWatcher:
        def __init__(self, path):
            pass

        def check(self):
            raise KeyboardInterrupt()

    iter = watch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=1)
    assert list(iter) == []


def test_watch_log(mocker, caplog):
    mock_log_enabled = mocker.patch('watchgod.main.logger.isEnabledFor')
    mock_log_enabled.return_value = True

    class FakeWatcher:
        def __init__(self, path):
            self.files = [1, 2, 3]

        def check(self):
            return {'r1'}

    iter = watch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=10)
    assert next(iter) == {'r1'}

    assert 'DEBUG    xxx time=Xms debounced=Xms files=3 changes=1 (1)\n' in re.sub('\dms', 'Xms', caplog.text)


async def test_awatch(mocker):
    class FakeWatcher:
        def __init__(self, path):
            self._results = iter([
                set(),
                set(),
                {'r1'},
                set(),
                {'r2'},
                set(),
            ])

        def check(self):
            return next(self._results)

    ans = []
    async for v in awatch('xxx', watcher_cls=FakeWatcher, debounce=5, normal_sleep=2, min_sleep=1):
        ans.append(v)
        if len(ans) == 2:
            break
    assert ans == [{'r1'}, {'r2'}]


async def test_awatch_stop():
    class FakeWatcher:
        def __init__(self, path):
            self._results = iter([
                {'r1'},
                set(),
                {'r2'},
            ])

        def check(self):
            return next(self._results)

    stop_event = asyncio.Event()
    stop_event.set()
    ans = []
    async for v in awatch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=1, stop_event=stop_event):
        ans.append(v)
    assert ans == []


async def test_awatch_log(mocker, caplog):
    mock_log_enabled = mocker.patch('watchgod.main.logger.isEnabledFor')
    mock_log_enabled.return_value = True

    class FakeWatcher:
        def __init__(self, path):
            self.files = [1, 2, 3]

        def check(self):
            return {'r1'}

    async for v in awatch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=1):
        assert v == {'r1'}
        break

    assert 'DEBUG    xxx time=Xms debounced=Xms files=3 changes=1 (1)\n' in re.sub('\dms', 'Xms', caplog.text)
