The `_rust_notify.pyi` file defines the interface to rust:

```{.py title="_rust_notify.pyi" test="false"}
{! watchfiles/_rust_notify.pyi !}
```

The rust backend can be accessed directly as follows:

```{.py title="Rust backend example" test="false"}
from watchfiles._rust_notify import RustNotify

r = RustNotify(['first/path', 'second/path'], False)

changes = r.watch(1_600, 50, None)
print(changes)
```
