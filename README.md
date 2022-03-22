# watchgod

[![CI](https://github.com/samuelcolvin/watchgod/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchgod/actions?query=event%3Apush+branch%3Amaster+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchgod/branch/master/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchgod)
[![pypi](https://img.shields.io/pypi/v/watchgod.svg)](https://pypi.python.org/pypi/watchgod)
[![license](https://img.shields.io/github/license/samuelcolvin/watchgod.svg)](https://github.com/samuelcolvin/watchgod/blob/master/LICENSE)

Simple, modern file watching and code reload in python.

*(watchgod is inspired by [watchdog](https://pythonhosted.org/watchdog/), hence the name, but tries to fix
some of the frustrations I found with watchdog, namely: separate approaches for each OS, an inelegant approach to
concurrency using threading, challenges around debouncing changes and bugs which weren't being fixed)*

## Installation

```bash
pip install watchgod
```

## Usage

### Synchronous Methods

To watch for changes in a directory:

```python
from watchgod import watch

for changes in watch('./path/to/dir'):
    print(changes)
```

`watch` (and all other methods described below) can take multiple paths as arguments to watch.

To run a function and restart it when code changes:

```python
from watchgod import run_process

def foobar(a, b, c):
    ...

run_process('./path/to/dir', target=foobar, args=(1, 2, 3))
```

`run_process` uses `PythonFilter` so only changes to python files will prompt a reload, 
see **custom event filtering** below.

If you need notifications about change events as well as to restart a process you can
use the `callback` argument to pass a function which will be called on every file change
with one argument: the set of file changes.

### Asynchronous Methods

*watchgod* comes with an asynchronous equivalents of `watch`: `awatch`.

```python
import asyncio
from watchgod import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

asyncio.run(main())
```

There's also an asynchronous equivalents of `run_process`: `arun_process` which in turn
uses `awatch`:

```python
import asyncio
from watchgod import arun_process

def foobar(a, b, c):
    ...

async def main():
    await arun_process('./path/to/dir', target=foobar, args=(1, 2, 3))

asyncio.run(main())
```

The signature of `arun_process` is almost identical to `run_process` except that
the optional `callback` argument may be a coroutine.

## Custom Filters

The `watch_filter` argument to the above methods allows you to specify which file system events **watchgod** should
react to (either yield or reload code). `watch_filter` should just be a callable which takes a change 
(either "added", "modified" or "deleted") and a path (as a string) and should return whether or not that change
should be registered.

*watchgod* comes with the following classes, instances of which can be with `watch_filter`:

* **`DefaultFilter`** The watcher used by default by `watch` and `awatch`, commonly ignored files
  like `*.swp`, `*.pyc` and `*~` are ignored along with directories like
  `.git`.
* **`PythonFilter`** Specific to python files, only `*.py`, `*.pyx` and `*.pyd` files are watched.
* **`BaseFilter`**, used by `DefaultFilter` and `PythonFilter`, useful for defining your own filters which leverage
  the same logic

Here's an example of a custom filter which leverages `BaseFilter` to only notice changes to common web files:

```python
from watchgod import BaseFilter, watch
from watchgod.filters import default_ignore_dirs

class WebFilter(BaseFilter):
    def __init__(self):
      super().__init__(
        ignore_dirs=default_ignore_dirs, 
        ignore_entity_patterns=('\.html$', '\.css$', '\.js$'),
      )

for changes in watch('my/web/project', watch_filter=WebFilter()):
    print (changes)
```

Here's an example of a customer filter which is a simple callable that ignores changes unless they represent
a new file being created:

```py
from watchgod import Change, watch

def only_added(change: Change, path: str) -> bool:
    return change == Change.added

for changes in watch('my/project', watch_filter=only_added):
    print (changes)
```

For more details, checkout
[`filters.py`](https://github.com/samuelcolvin/watchgod/blob/master/watchgod/filters.py),
it's pretty simple.

## CLI

*watchgod* also comes with a CLI for running and reloading python code.

Let's say you have `foobar.py`:

```python
from aiohttp import web

async def handle(request):
    return web.Response(text='testing')

app = web.Application()
app.router.add_get('/', handle)

def main():
    web.run_app(app, port=8000)
```

You could run this and reload it when any file in the current directory changes with::

    watchgod foobar.main

In case you need to ignore certain files or directories, you can use the argument
 `--ignore-paths`.

Run `watchgod --help` for more options. *watchgod* is also available as a python executable module
via `python -m watchgod ...`.

## How Watchgod Works

*watchgod* after version `v0.10` is based on the rust [notify library](https://github.com/notify-rs/notify).

All the hard work of integrating with the OS's file system events notifications and falling back to polling is palmed
off on the rust library.

Prior to `v0.10` the library used filesystem polling to watch for changes, 
see the [README for v0.8.1](https://github.com/samuelcolvin/watchgod/tree/v0.8.1) for more details.
