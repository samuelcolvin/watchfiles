import asyncio
from typing import List, Tuple, Union

import anyio

__all__ = 'rust_watch', 'WatchgodRustInternalError'

def rust_watch(
    watch_path: str,
    debounce_ms: int,
    step_ms: int,
    cancel_event: Union[anyio.Event, asyncio.Event],
    debug: bool,
) -> List[Tuple[int, str]]: ...

class WatchgodRustInternalError(RuntimeError): ...
