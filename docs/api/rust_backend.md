::: watchfiles._rust_notify.RustNotify

::: watchfiles._rust_notify.WatchfilesRustInternalError

::: watchfiles._rust_notify.__version__

# Rust backend direct usage

The rust backend can be accessed directly as follows:

```py
title="Rust backend example"
from watchfiles._rust_notify import RustNotify

r = RustNotify(['first/path', 'second/path'], False, False, 0)

changes = r.watch(1_600, 50, 100, None)
print(changes)
```
