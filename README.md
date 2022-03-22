# watchgod

[![CI](https://github.com/samuelcolvin/watchgod/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchgod/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchgod/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchgod)
[![pypi](https://img.shields.io/pypi/v/watchgod.svg)](https://pypi.python.org/pypi/watchgod)
[![license](https://img.shields.io/github/license/samuelcolvin/watchgod.svg)](https://github.com/samuelcolvin/watchgod/blob/main/LICENSE)

Simple, modern and high performance file watching and code reload in python.

## NOTE! New Unstable Version

The docs here refer to watchgod version `v0.10a1` which is a significant rewrite from `v0.8`,
the docs for `v0.8` are available [here](https://github.com/samuelcolvin/watchgod/tree/v0.8.1).

Please try `v0.10a1` (installed via `pip install watchgod==v0.10a1`) and give feedback,
[here](https://github.com/samuelcolvin/watchgod/issues/25).

---

Underlying file system notifications are now handled by the [Notify](https://github.com/notify-rs/notify) rust library.

*(watchgod is inspired by [watchdog](https://pythonhosted.org/watchdog/), hence the name, but tries to fix
some of the frustrations I found with watchdog, namely: separate approaches for each OS, an inelegant approach to
concurrency using threading, challenges around debouncing changes and bugs which weren't being fixed)*

## Installation

**watchgod** requires Python 3.7 - 3.10.

```bash
pip install watchgod==v0.10a1
```

Binaries are available for:
* **Linux**: `manylinux-x86_64`, `musllinux-x86_64` & `manylinux-i686`
* **MacOS**: `x86_64` & `arm64` (except python 3.7)
* **Windows**: `amd64` & `win32`

Otherwise, you can install from source which requires Rust stable to be installed.

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

`run_process` uses `PythonFilter` by default so only changes to python files will prompt a reload, 
see **custom event filtering** below.

If you need notifications about change events as well as to restart a process you can
use the `callback` argument to pass a function which will be called on every file change
with one argument: the set of file changes.

File changes are also available via the `WATCHGOD_CHANGES` environment variable which contains JSON encoded
details of changes, see the CLI example below.

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

Here's an example of a custom filter which extends `DefaultFilter` to only notice changes to common web files:

```python
from watchgod import Change, DefaultFilter, watch


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
from watchgod import Change, watch

def only_added(change: Change, path: str) -> bool:
    return change == Change.added

for changes in watch('my/project', watch_filter=only_added):
    print (changes)
```

For more details, checkout
[`filters.py`](https://github.com/samuelcolvin/watchgod/blob/main/watchgod/filters.py),
it's pretty simple.

## CLI

*watchgod* also comes with a CLI for running and reloading python code.

Let's say you have `foobar.py` (this is a very simple web server using 
[aiohttp](https://aiohttp.readthedocs.io/en/stable/)) which gets details about recent file changes from the 
`WATCHGOD_CHANGES` environment variable and returns them as JSON.

```python
import os, json
from aiohttp import web

async def handle(request):
    # get the most recent file changes and return them
    changes = os.getenv('WATCHGOD_CHANGES', '[]')
    changes = json.loads(changes)
    return web.json_response(dict(changes=changes))

app = web.Application()
app.router.add_get('/', handle)

def main():
    web.run_app(app, port=8000)
```

You could run this and reload it when any file in the current directory changes with:

    watchgod foobar.main

Run `watchgod --help` for more options.

The CLI can also be used via `python -m watchgod ...`.

## How Watchgod Works

*watchgod* after version `v0.10` is based on the [Notify](https://github.com/notify-rs/notify) rust library.

All the hard work of integrating with the OS's file system events notifications and falling back to polling is palmed
off on the rust library.

"Debouncing" changes - e.g. grouping changes into batches rather than firing a yield/reload for each file changed
is managed in rust.

The rust code takes care of creating a new thread to watch for file changes so in the case of the synchronous methods
(`watch` and `run_process`) no threading logic is required in python. When using the asynchronous methods (`awatch` and
`arun_process`) [`anyio.to_thread.run_sync](https://anyio.readthedocs.io/en/stable/api.html#anyio.to_thread.run_sync)
is used to wait for changes in rust within a thread.

Prior to `v0.10` the library used filesystem polling to watch for changes, 
see the [README for v0.8.1](https://github.com/samuelcolvin/watchgod/tree/v0.8.1) for more details.
