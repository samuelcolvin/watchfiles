::: watchfiles._rust_notify.RustNotify

::: watchfiles._rust_notify.WatchfilesRustInternalError

::: watchfiles._rust_notify.__version__

# Rust backend direct usage

The rust backend can be accessed directly as follows:

```py
title="Rust backend example"
from watchfiles._rust_notify import RustNotify

r = RustNotify(['first/path', 'second/path'], False, False, 0, True)

changes = r.watch(1_600, 50, 100, None)
print(changes)

r.close()
```

Or using `RustNotify` as a context manager:

```py
title="Rust backend context manager example"
from watchfiles._rust_notify import RustNotify

with RustNotify(['first/path', 'second/path'], False, False, 0, True) as r:
    changes = r.watch(1_600, 50, 100, None)
    print(changes)
```

(See the documentation on [`close`][watchfiles._rust_notify.RustNotify.close] above for when and why the
context manager or `close` method are required.)
