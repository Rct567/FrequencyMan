from typing import Generator, List, Callable
from contextlib import contextmanager
import time

class EventLogger:
    def __init__(self):
        self._events: List[str] = []
        self._event_listeners: List[Callable[[str], None]] = []

    def addEventListener(self, listener: Callable[[str], None]) -> None:
        self._event_listeners.append(listener)
    
    def addEvent(self, msg: str) -> int:
        index = len(self._events)
        self._events.append(msg)
        for listener in self._event_listeners:
            listener(msg)
        return index
 

    @contextmanager
    def addBenchmarkedEvent(self, msg: str) -> Generator[None, None, None]:
        index = self.addEvent(msg)
        start_time = time.time()
        yield
        elapsed_time = time.time() - start_time
        self._events[index] += f" (took {elapsed_time:.2f} seconds)"