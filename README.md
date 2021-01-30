# watchgod

[![CI](https://github.com/samuelcolvin/watchgod/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchgod/actions?query=event%3Apush+branch%3Amaster+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchgod/branch/master/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchgod)
[![pypi](https://img.shields.io/pypi/v/watchgod.svg)](https://pypi.python.org/pypi/watchgod)
[![license](https://img.shields.io/github/license/samuelcolvin/watchgod.svg)](https://github.com/samuelcolvin/watchgod/blob/master/LICENSE)

Simple, modern file watching and code reload in python.

*(watchgod is inspired by [watchdog](https://pythonhosted.org/watchdog/), hence the name, but tries to fix
some of the frustrations I found with watchdog, namely: separate approaches for each OS, an inelegant approach to
concurrency using threading, challenges around debouncing changes and bugs which weren't being fixed)*

## Usage

To watch for changes in a directory:

```python
from watchgod import watch

for changes in watch('./path/to/dir'):
    print(changes)
```

To run a function and restart it when code changes:

```python
from watchgod import run_process

def foobar(a, b, c):
    ...

run_process('./path/to/dir', foobar, args=(1, 2, 3))
```

`run_process` uses `PythonWatcher` so only changes to python files will prompt a
reload, see **custom watchers** below.

If you need notifications about change events as well as to restart a process you can
use the `callback` argument to pass a function which will be called on every file change
with one argument: the set of file changes.

## Asynchronous Methods

*watchgod* comes with an asynchronous equivalents of `watch`: `awatch` which uses
a `ThreadPoolExecutor` to iterate over files.

```python
import asyncio
from watchgod import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

There's also an asynchronous equivalents of `run_process`: `arun_process` which in turn
uses `awatch`:

```python
import asyncio
from watchgod import arun_process

def foobar(a, b, c):
    ...

async def main():
    await arun_process('./path/to/dir', foobar, args=(1, 2, 3))

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

`arun_process` uses `PythonWatcher` so only changes to python files will prompt a
reload, see **custom watchers** below.

The signature of `arun_process` is almost identical to `run_process` except that
the optional `callback` argument must be a coroutine, not a function.

## Custom Watchers


*watchgod* comes with the following watcher classes which can be used via the `watcher_cls`
keyword argument to any of the methods above.

For example:

```python
for changes in watch(directoryin, watcher_cls=RegExpWatcher, watcher_kwargs=dict(re_files=r'^.*(\.mp3)$')):
   print (changes)
```

For more details, checkout
[`watcher.py`](https://github.com/samuelcolvin/watchgod/blob/master/watchgod/watcher.py),
it's pretty simple.

* **AllWatcher** The base watcher, all files are checked for changes.

* **DefaultWatcher** The watcher used by default by `watch` and `awatch`, commonly ignored files
  like `*.swp`, `*.pyc` and `*~` are ignored along with directories like
  `.git`.

* **PythonWatcher** Specific to python files, only `*.py`, `*.pyx` and `*.pyd` files are watched.

* **DefaultDirWatcher** Is the base for `DefaultWatcher` and `DefaultDirWatcher`. It takes care of ignoring
  some regular directories.


If these classes aren't sufficient you can define your own watcher, in particular
you will want to override `should_watch_dir` and `should_watch_file`. Unless you're
doing something very odd, you'll want to inherit from `DefaultDirWatcher`.

Note that events related to *directories* are not reported (e.g. creation of a
directory), but new files in new directories will be reported.

## CLI

*watchgod* also comes with a CLI for running and reloading python code.

Lets say you have `foobar.py`:

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

## Why no inotify / kqueue / fsevent / winapi support

*watchgod* (for now) uses file polling rather than the OS's built in file change notifications.

This is not an oversight, it's a decision with the following rationale:

1. Polling is "fast enough", particularly since PEP 471 introduced fast `scandir`.
  For reasonably large projects like the TutorCruncher code base with 850 files and 300k lines
  of code, *watchgod* can scan the entire tree in ~24ms. With a scan interval of 400ms that is roughly
  5% of one CPU - perfectly acceptable load during development.
2. The clue is in the title, there are at least 4 different file notification systems to integrate
  with, most of them not trivial. That is all before we get to changes between different OS versions.
3. Polling works well when you want to group or "debounce" changes.
  Let's say you're running a dev server and you change branch in git, 100 files change.
  Do you want to reload the dev server 100 times or once? Right.
  Polling periodically will likely group these changes into one event. If you're receiving a
  stream of events you need to delay execution of the reload when you receive the first event
  to see if it's part of a group of file changes. This is not trivial.

All that said, I might still use rust's "notify" crate to do the heavy lifting of file watching,
see[#25](https://github.com/samuelcolvin/watchgod/issues/25).
