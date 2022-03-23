See [`_rust_notify.py`](https://github.com/samuelcolvin/watchfiles/blob/main/watchfiles/_rust_notify.py)
for docs until [this](https://github.com/mkdocstrings/mkdocstrings/issues/404) is fixed.

The rust backend can be accessed directly as follows:

```{.py title="Rust backend example" test="false"}
from watchfiles._rust_notify import RustNotify

r = RustNotify(['first/path', 'second/path'], False)

changes = r.watch(1_600, 50, None)
print(changes)
```
