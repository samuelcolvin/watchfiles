::: watchfiles.BaseFilter

::: watchfiles.DefaultFilter

::: watchfiles.PythonFilter

## Custom Filters

Here's an example of a custom filter which extends `DefaultFilter` to only notice changes to common web files:

```python
from watchfiles import Change, DefaultFilter, watch


class WebFilter(DefaultFilter):
    allowed_extensions = '.html', '.css', '.js'

    def __call__(self, change: Change, path: str) -> bool:
        return (
            super().__call__(change, path) and 
            path.endswith(self.allowed_extensions)
        )

for changes in watch('my/web/project', watch_filter=WebFilter()):
    print (changes)
```

Here's an example of a customer filter which is a simple callable that ignores changes unless they represent
a new file being created:

```py
from watchfiles import Change, watch

def only_added(change: Change, path: str) -> bool:
    return change == Change.added

for changes in watch('my/project', watch_filter=only_added):
    print (changes)
```

For more details, see [`filters.py`](https://github.com/samuelcolvin/watchfiles/blob/main/watchfiles/filters.py).
