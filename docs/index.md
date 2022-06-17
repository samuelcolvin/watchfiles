# watchfiles

[![CI](https://github.com/samuelcolvin/watchfiles/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchfiles/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchfiles/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchfiles)
[![pypi](https://img.shields.io/pypi/v/watchfiles.svg)](https://pypi.python.org/pypi/watchfiles)
[![license](https://img.shields.io/github/license/samuelcolvin/watchfiles.svg)](https://github.com/samuelcolvin/watchfiles/blob/main/LICENSE)

{{ version }}.

Simple, modern and high performance file watching and code reload in python.

Underlying file system notifications are handled by the [Notify](https://github.com/notify-rs/notify) rust library.

This package was previously named "watchgod", see [Migrating from watchgod](./migrating.md) for more information.

## Usage

Here are some examples of what **watchfiles** can do:

```py
title="watch Usage"
from watchfiles import watch

for changes in watch('./path/to/dir'):
    print(changes)
```
See [`watch` docs][watchfiles.watch] for more details.

`watch` (and all other methods) can watch either files or directories and can watch more than one path with
a single instance.

```py
title="awatch Usage"
import asyncio
from watchfiles import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

asyncio.run(main())
```
See [`awatch` docs][watchfiles.awatch] for more details.

```py
title="run_process Usage"
from watchfiles import run_process

def foobar(a, b, c):
    ...

if __name__ == '__main__':
    run_process('./path/to/dir', target=foobar, args=(1, 2, 3))
```
See [`run_process` docs][watchfiles.run_process] for more details.

```py
title="arun_process Usage"
import asyncio
from watchfiles import arun_process

def foobar(a, b, c):
    ...

async def main():
    await arun_process('./path/to/dir', target=foobar, args=(1, 2, 3))

if __name__ == '__main__':
    asyncio.run(main())
```
See [`arun_process` docs][watchfiles.arun_process] for more details.

## Installation

**watchfiles** requires **Python 3.7** to **Python 3.10**.

### From PyPI

Using `pip`:

```bash
pip install watchfiles
```

Binaries are available for:

* **Linux**: `x86_64`, `aarch64`, `i686`, `armv7l`, `musl-x86_64` & `musl-aarch64`
* **MacOS**: `x86_64` & `arm64` (except python 3.7)
* **Windows**: `amd64` & `win32`

### From conda-forge

Using `conda` or `mamba`:

```bash
mamba install -c conda-forge watchfiles
```

Binaries are available for:

* **Linux**: `x86_64`
* **MacOS**: `x86_64` & `arm64` (except python 3.7)
* **Windows**: `amd64`

### From source

You can also install from source which requires Rust stable to be installed.

## How Watchfiles Works

**watchfiles** is based on the [Notify](https://github.com/notify-rs/notify) rust library.

All the hard work of integrating with the OS's file system events notifications and falling back to polling is palmed
off onto the rust library.

"Debouncing" changes - e.g. grouping changes into batches rather than firing a yield/reload for each file changed
is managed in rust.

The rust code takes care of creating a new thread to watch for file changes so in the case of the synchronous methods
(`watch` and `run_process`) no threading logic is required in python. When using the asynchronous methods (`awatch` and
`arun_process`) [`anyio.to_thread.run_sync`](https://anyio.readthedocs.io/en/stable/api.html#anyio.to_thread.run_sync)
is used to wait for changes in a thread.
