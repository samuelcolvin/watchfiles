from typing import List, Optional, Protocol, Set, Tuple

__all__ = 'RustNotify', 'WatchfilesRustInternalError'

class AbstractEvent(Protocol):
    def is_set(self) -> bool: ...

class RustNotify:
    """
    Interface to the Rust [notify](https://crates.io/crates/notify) crate which does
    the heavy lifting of watching for file changes and grouping them into a single event.
    """

    def __init__(self, watch_paths: List[str], debug: bool) -> None:
        """
        Create a new RustNotify instance and start a thread to watch for changes.

        `FileNotFoundError` is raised if one of the directories does not exist.

        Args:
            watch_paths: file system paths to watch for changes
            debug: if true, print details about all events to stderr
        """
    def watch(
        self,
        debounce_ms: int,
        step_ms: int,
        cancel_event: Optional[AbstractEvent],
    ) -> Optional[Set[Tuple[int, str]]]:
        """
        Watch for changes and return a set of `(event_type, path)` tuples.

        This method will wait indefinitely for changes, but once a change is detected,
        it will group changes and return in no more than `debounce_ms` milliseconds.

        The GIL is released during a `step_ms` sleep on each iteration to avoid
        blocking other threads.

        Args:
            debounce_ms: maximum time in milliseconds to group changes over before returning.
            step_ms: time to wait for new changes in milliseconds, if no changes are detected
                in this time, and at least one change has been detected, the changes are yielded.
            cancel_event: event to check on every iteration to see if this function should return early.

        Returns:
            A set of `(event_type, path)` tuples,
            the event types are ints which match [`Change`][watchfiles.Change].
        """

class WatchfilesRustInternalError(RuntimeError):
    """
    Raised when RustNotify encounters an unknown error.

    If you get this a lot, please file a bug in github.
    """
