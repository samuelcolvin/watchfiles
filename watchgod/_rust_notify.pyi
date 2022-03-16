from typing import Optional, Protocol, Set, Tuple

__all__ = 'RustNotify', 'WatchgodRustInternalError'

class AbstractEvent(Protocol):
    def is_set(self) -> bool: ...

class RustNotify:
    def __init__(self, watch_path: str, debug: bool) -> None: ...
    def watch(
        self,
        debounce_ms: int,
        step_ms: int,
        cancel_event: Optional[AbstractEvent],
    ) -> Optional[Set[Tuple[int, str]]]: ...

class WatchgodRustInternalError(RuntimeError): ...
