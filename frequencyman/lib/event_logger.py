from typing import Generator, Callable, Optional
from contextlib import contextmanager
import time


class EventLogger:
    def __init__(self):
        self.events: list[str] = []
        self.event_listeners: list[Callable[[str], None]] = []
        self.timed_entries_open = 0

    def addEventLogListener(self, listener: Callable[[str], None]) -> None:
        self.event_listeners.append(listener)

    def addEntry(self, log_msg: str, propagate_fn: Optional[Callable] = None) -> int:
        index = len(self.events)
        if self.timed_entries_open > 0:
            self.events.append(("|"*self.timed_entries_open)+" "+log_msg)
        else:
            self.events.append(log_msg)
        for listener in self.event_listeners:
            listener(log_msg)
        if propagate_fn is not None:
            propagate_fn(log_msg)
        return index

    @contextmanager
    def addBenchmarkedEntry(self, log_msg: str) -> Generator[None, None, None]:
        index = self.addEntry(log_msg)
        start_time = time.time()
        self.timed_entries_open += 1
        yield
        self.timed_entries_open -= 1
        elapsed_time = time.time() - start_time
        self.events[index] += f" (took {elapsed_time:.2f} seconds)"
