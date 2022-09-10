# watchfiles

[![CI](https://github.com/samuelcolvin/watchfiles/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchfiles/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchfiles/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchfiles)
[![pypi](https://img.shields.io/pypi/v/watchfiles.svg)](https://pypi.python.org/pypi/watchfiles)
[![CondaForge](https://img.shields.io/conda/v/conda-forge/watchfiles.svg)](https://anaconda.org/conda-forge/watchfiles)
[![license](https://img.shields.io/github/license/samuelcolvin/watchfiles.svg)](https://github.com/samuelcolvin/watchfiles/blob/main/LICENSE)

Simple, modern and high performance file watching and code reload in python.

---

**Documentation**: [watchfiles.helpmanual.io](https://watchfiles.helpmanual.io)

**Source Code**: [github.com/samuelcolvin/watchfiles](https://github.com/samuelcolvin/watchfiles)

---

Underlying file system notifications are handled by the [Notify](https://github.com/notify-rs/notify) rust library.

This package was previously named "watchgod",
see [the migration guide](https://watchfiles.helpmanual.io/migrating/) for more information.

## Installation

**watchfiles** requires Python 3.7 - 3.10.

```bash
pip install watchfiles
```

Binaries are available for:

* **Linux**: `x86_64`, `aarch64`, `i686`, `armv7l`, `musl-x86_64` & `musl-aarch64`
* **MacOS**: `x86_64` & `arm64` (except python 3.7)
* **Windows**: `amd64` & `win32`

Otherwise, you can install from source which requires Rust stable to be installed.

## Usage

Here are some examples of what **watchfiles** can do:

### `watch` Usage

```py
from watchfiles import watch

for changes in watch('./path/to/dir'):
    print(changes)
```
See [`watch` docs](https://watchfiles.helpmanual.io/api/watch/#watchfiles.watch) for more details.

### `awatch` Usage

```py
import asyncio
from watchfiles import awatch

async def main():
    async for changes in awatch('/path/to/dir'):
        print(changes)

asyncio.run(main())
```
See [`awatch` docs](https://watchfiles.helpmanual.io/api/watch/#watchfiles.awatch) for more details.

### `run_process` Usage

```py
from watchfiles import run_process

def foobar(a, b, c):
    ...

if __name__ == '__main__':
    run_process('./path/to/dir', target=foobar, args=(1, 2, 3))
```
See [`run_process` docs](https://watchfiles.helpmanual.io/api/run_process/#watchfiles.run_process) for more details.

### `arun_process` Usage

```py
import asyncio
from watchfiles import arun_process

def foobar(a, b, c):
    ...

async def main():
    await arun_process('./path/to/dir', target=foobar, args=(1, 2, 3))

if __name__ == '__main__':
    asyncio.run(main())
```
See [`arun_process` docs](https://watchfiles.helpmanual.io/api/run_process/#watchfiles.arun_process) for more details.

## CLI

**watchfiles** also comes with a CLI for running and reloading code. To run `some command` when files in `src` change:

```
watchfiles "some command" src
```

For more information, see [the CLI docs](https://watchfiles.helpmanual.io/cli/).

Or run

```bash
watchfiles --help
```
