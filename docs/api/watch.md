::: watchfiles.watch

::: watchfiles.awatch

::: watchfiles.Change

# Handling Timeouts

Timeouts work like other changes but the sequence returned is an empty sequence rather than a sequence with change details.  Creating a 1 second timeout looks like this:

```
    for changes in watchfiles.watch('.', rust_timeout=1000, yield_on_timeout=True):
        if not changes:
            print("Timeout occurred")
```
