## Synchronous Methods

To watch for changes in a directory:

```py
title="Synchronous File Watching"
from watchfiles import watch

for changes in watch('./path/to/dir'):
    print(changes)
```

`watch` (and all other methods described below) can take multiple paths as arguments to watch.

To run a function and restart it when code changes:

```py
title="Synchronously calling a function and reloading"
from watchfiles import run_process

def foobar(a, b, c):
    ...

if __name__ == '__main__':
    run_process('./path/to/dir', target=foobar, args=(1, 2, 3))
```

`run_process` uses `PythonFilter` by default so only changes to python files will prompt a reload, 
see **custom event filtering** below.

If you need notifications about change events as well as to restart a process you can
use the `callback` argument to pass a function which will be called on every file change
with one argument: the set of file changes.

File changes are also available via the `WATCHFILES_CHANGES` environment variable which contains JSON encoded
details of changes, see the CLI example below.

## Asynchronous Methods

*watchfiles* comes with an asynchronous equivalents of `watch`: `awatch`.

```py
title="Asynchronous File Watching"
import asyncio
from watchfiles import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

asyncio.run(main())
```

There's also an asynchronous equivalents of `run_process`: `arun_process` which in turn
uses `awatch`:

```py
title="Asynchronously calling a function and reloading"
import asyncio
from watchfiles import arun_process

def foobar(a, b, c):
    ...

async def main():
    await arun_process('./path/to/dir', target=foobar, args=(1, 2, 3))

if __name__ == '__main__':
    asyncio.run(main())
```

The signature of `arun_process` is almost identical to `run_process` except that
the optional `callback` argument may be a coroutine.

## Custom Filters

The `watch_filter` argument to the above methods allows you to specify which file system events **watchfiles** should
react to (either yield or reload code). `watch_filter` should just be a callable which takes a change 
(either "added", "modified" or "deleted") and a path (as a string) and should return whether or not that change
should be registered.

*watchfiles* comes with the following classes, instances of which can be with `watch_filter`:

* **`DefaultFilter`** The watcher used by default by `watch` and `awatch`, commonly ignored files
  like `*.swp`, `*.pyc` and `*~` are ignored along with directories like
  `.git`.
* **`PythonFilter`** Specific to python files, only `*.py`, `*.pyx` and `*.pyd` files are watched.
* **`BaseFilter`**, used by `DefaultFilter` and `PythonFilter`, useful for defining your own filters which leverage
  the same logic

Here's an example of a custom filter which extends `DefaultFilter` to only notice changes to common web files:

```python
from watchfiles import Change, DefaultFilter, watch


class WebFilter(DefaultFilter):
    allowed_extensions = '.html', '.css', '.js'

    def __call__(self, change: Change, path: str) -> bool:
        return super().__call__(change, path) and path.endswith(self.allowed_extensions)

for changes in watch('my/web/project', watch_filter=WebFilter()):
    print (changes)
```

Here's an example of a customer filter which is a simple callable that ignores changes unless they represent
a new file being created:

```py
from watchfiles import Change, watch

def only_added(change: Change, path: str) -> bool:
    return change == Change.added

for changes in watch('my/project', watch_filter=only_added):
    print (changes)
```

For more details, checkout
[`filters.py`](https://github.com/samuelcolvin/watchfiles/blob/main/watchfiles/filters.py),
it's pretty simple.
