import os
from typing import Generator, Callable, Optional
from contextlib import contextmanager
import time

from .utilities import var_dump


class EventLogger:

    def __init__(self):
        self.event_log: list[str] = []
        self.event_log_listeners: list[Callable[[str], None]] = []
        self.timed_entries_open: int = 0

    def addEventLogListener(self, listener: Callable[[str], None]) -> None:
        self.event_log_listeners.append(listener)

    def addEntry(self, log_msg: str, propagate_fn: Optional[Callable] = None) -> int:
        index = len(self.event_log)
        if self.timed_entries_open > 0:
            self.event_log.append(("  "*self.timed_entries_open)+" "+log_msg)
        else:
            self.event_log.append(log_msg)
        for listener in self.event_log_listeners:
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
        self.event_log[index] += f" (took {elapsed_time:.2f} seconds)"

    def append_to_file(self, target_file):
        if os.path.exists(target_file) and os.path.getsize(target_file) > 0.5 * 1024 * 1024:
            six_hours_ago = time.time() - 6 * 60 * 60
            if os.path.getmtime(target_file) < six_hours_ago:
                with open(target_file, 'w', encoding='utf-8') as file:
                    file.truncate()
        with open(target_file, 'a', encoding='utf-8') as file:
            file.write(str(self)+"\n\n=================================================================\n\n")

    def __str__(self):
        return "\n".join(self.event_log)
