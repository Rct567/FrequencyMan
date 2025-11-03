"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import os
from typing import Generator, Callable, Optional
from contextlib import contextmanager
import time

from .utilities import override


class EventLogger:

    def __init__(self) -> None:
        self.event_log: list[str] = []
        self.event_log_listeners: list[Callable[[str], None]] = []
        self.timed_entries_open: int = 0
        self.time_started: Optional[float] = None

    def add_event_log_listener(self, listener: Callable[[str], None]) -> None:
        self.event_log_listeners.append(listener)

    def add_entry(self, log_msg: str) -> int:
        index = len(self.event_log)
        indent = ("  " * self.timed_entries_open) + " " if self.timed_entries_open > 0 else ""
        self.event_log.append(indent + log_msg)

        if self.time_started is None:
            self.time_started = time.perf_counter()

        for listener in self.event_log_listeners:
            listener(log_msg)

        return index

    def get_elapsed_time(self) -> float:
        if self.time_started is None:
            return 0.0
        return time.perf_counter() - self.time_started

    @contextmanager
    def add_benchmarked_entry(self, log_msg: str) -> Generator[None, None, None]:
        index = self.add_entry(log_msg)
        start_time = time.perf_counter()
        self.timed_entries_open += 1

        yield

        self.timed_entries_open -= 1
        elapsed_time = time.perf_counter() - start_time
        self.event_log[index] += " (took {:.2f} seconds)".format(elapsed_time)

    def append_to_file(self, target_file: str) -> None:
        if os.path.exists(target_file) and os.path.getsize(target_file) > 0.5 * 1024 * 1024:
            six_hours_ago = time.time() - 6 * 60 * 60
            if os.path.getmtime(target_file) < six_hours_ago:
                with open(target_file, 'w', encoding='utf-8') as file:
                    file.truncate()
        with open(target_file, 'a', encoding='utf-8') as file:
            file.write(str(self)+"\n\n=================================================================\n\n")

    @override
    def __str__(self) -> str:
        return "\n".join(self.event_log)
