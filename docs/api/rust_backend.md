The `_rust_notify.pyi` file defines the interface to rust:

```{.py title="_rust_notify.pyi" test="skip"}
{! watchfiles/_rust_notify.pyi !}
```

The rust backend can be accessed directly as follows:

```py
title="Rust backend example"
from watchfiles._rust_notify import RustNotify

r = RustNotify(['first/path', 'second/path'], False, False, 0)

changes = r.watch(1_600, 50, 100, None)
print(changes)
```

Or using `RustNotify` as a context manager:

```py
title="Rust backend context manager example"
from watchfiles._rust_notify import RustNotify

with RustNotify(['first/path', 'second/path'], False, False, 0) as r:
    changes = r.watch(1_600, 50, 100, None)
    print(changes)
```

(See the documentation on `close` above for when the context manager or `close` method are required.)
