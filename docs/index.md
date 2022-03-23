# watchfiles

[![CI](https://github.com/samuelcolvin/watchfiles/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/watchfiles/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![Coverage](https://codecov.io/gh/samuelcolvin/watchfiles/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/watchfiles)
[![pypi](https://img.shields.io/pypi/v/watchfiles.svg)](https://pypi.python.org/pypi/watchfiles)
[![license](https://img.shields.io/github/license/samuelcolvin/watchfiles.svg)](https://github.com/samuelcolvin/watchfiles/blob/main/LICENSE)

Simple, modern and high performance file watching and code reload in python.

---

## NOTICE


The docs here refer to **watchfiles**, watchfiles was significantly rewritten and renamed for this version.

Documentation for the old package (named `watchgod`) is available [here](https://github.com/samuelcolvin/watchfiles/tree/watchgod).
See [issue #102](https://github.com/samuelcolvin/watchfiles/issues/102) for details on the migration and its rationale.

---

Underlying file system notifications are handled by the [Notify](https://github.com/notify-rs/notify) rust library.

## Usage

Here's a simple example of what *watchfiles* can do:

```py
title="Basic Usage"
from watchfiles import watch

for changes in watch('./path/to/dir'):
    print(changes)
```

TODO more examples and links to docs.

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
