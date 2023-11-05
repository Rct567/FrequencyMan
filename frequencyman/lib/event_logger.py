from typing import Generator, Callable
from contextlib import contextmanager
import time


class EventLogger:
    def __init__(self):
        self.events: list[str] = []
        self.event_listeners: list[Callable[[str], None]] = []

    def addEventListener(self, listener: Callable[[str], None]) -> None:
        self.event_listeners.append(listener)
    
    def addEvent(self, msg: str) -> int:
        index = len(self.events)
        self.events.append(msg)
        for listener in self.event_listeners:
            listener(msg)
        return index

    @contextmanager
    def addBenchmarkedEvent(self, msg: str) -> Generator[None, None, None]:
        index = self.addEvent(msg)
        start_time = time.time()
        yield
        elapsed_time = time.time() - start_time
        self.events[index] += f" (took {elapsed_time:.2f} seconds)"