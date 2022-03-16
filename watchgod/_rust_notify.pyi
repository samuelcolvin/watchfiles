import asyncio
from typing import Set, Tuple, Union

import anyio

__all__ = 'RustNotify', 'WatchgodRustInternalError'

class RustNotify:
    def __init__(self, watch_path: str, debug: bool) -> None: ...
    def watch(
        self,
        debounce_ms: int,
        step_ms: int,
        cancel_event: Union[anyio.Event, asyncio.Event],
    ) -> Set[Tuple[int, str]]: ...

class WatchgodRustInternalError(RuntimeError): ...
