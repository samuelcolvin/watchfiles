# watchfiles

[![CI](https://github.com/samuelcolvin/watchfiles/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchfiles/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchfiles/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchfiles)
[![pypi](https://img.shields.io/pypi/v/watchfiles.svg)](https://pypi.python.org/pypi/watchfiles)
[![license](https://img.shields.io/github/license/samuelcolvin/watchfiles.svg)](https://github.com/samuelcolvin/watchfiles/blob/main/LICENSE)

Simple, modern and high performance file watching and code reload in python.

---

## NOTICE

This package was significantly altered and renamed from `watchgod` to `watchfiles`, this files refers to the
`watchfiles` package.

Documentation for the old version (`watchgod`) is available [here](https://github.com/samuelcolvin/watchfiles/tree/watchgod).
See [issue #102](https://github.com/samuelcolvin/watchfiles/issues/102) for details on the migration and its rationale.

---

Underlying file system notifications are handled by the [Notify](https://github.com/notify-rs/notify) rust library.

## Installation

**watchfiles** requires Python 3.7 - 3.10.

```bash
pip install watchfiles
```

Binaries are available for:
* **Linux**: `manylinux-x86_64`, `musllinux-x86_64` & `manylinux-i686`
* **MacOS**: `x86_64` & `arm64` (except python 3.7)
* **Windows**: `amd64` & `win32`

Otherwise, you can install from source which requires Rust stable to be installed.

## Usage

To watch for changes in a directory:

```python
from watchfiles import watch

for changes in watch('./path/to/dir'):
    print(changes)
```

`watch` (and all other methods described below) can take multiple paths as arguments to watch.

To run a function and restart it when code changes:

```python
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

### Asynchronous Methods

*watchfiles* comes with an asynchronous equivalents of `watch`: `awatch`.

```python
import asyncio
from watchfiles import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

asyncio.run(main())
```

There's also an asynchronous equivalents of `run_process`: `arun_process` which in turn
uses `awatch`:

```python
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

## CLI

*watchfiles* also comes with a CLI for running and reloading python code.

Let's say you have `foobar.py` (this is a very simple web server using 
[aiohttp](https://aiohttp.readthedocs.io/en/stable/)) which gets details about recent file changes from the 
`WATCHFILES_CHANGES` environment variable and returns them as JSON.

```python
import os, json
from aiohttp import web

async def handle(request):
    # get the most recent file changes and return them
    changes = os.getenv('WATCHFILES_CHANGES', '[]')
    changes = json.loads(changes)
    return web.json_response(dict(changes=changes))

app = web.Application()
app.router.add_get('/', handle)

def main():
    web.run_app(app, port=8000)
```

You could run this and reload it when any file in the current directory changes with:

    watchfiles foobar.main

Run `watchfiles --help` for more options.

The CLI can also be used via `python -m watchfiles ...`.
