from watchgod import awatch


async def test_watch(mocker):
    class FakeWatcher:
        def __init__(self, path):
            self._results = iter([
                {'r1'},
                set(),
                {'r2'},
            ])

        def check(self):
            return next(self._results)

    ans = []
    async for v in awatch('xxx', watcher_cls=FakeWatcher, debounce=5, min_sleep=1):
        ans.append(v)
        if len(ans) == 2:
            break
    assert ans == [{'r1'}, {'r2'}]


async def test_watch_log(mocker, caplog):
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

    assert caplog(('\d+ms', 'Xms')) == 'watchgod.main DEBUG: time=Xms files=3 changes=1\n'
