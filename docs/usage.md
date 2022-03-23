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
