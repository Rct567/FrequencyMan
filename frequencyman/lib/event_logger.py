"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import os
from typing import Generator, Callable, Optional
from contextlib import contextmanager
import time

from .utilities import var_dump


class EventLogger:

    def __init__(self) -> None:
        self.event_log: list[str] = []
        self.event_log_listeners: list[Callable[[str], None]] = []
        self.timed_entries_open: int = 0

    def addEventLogListener(self, listener: Callable[[str], None]) -> None:
        self.event_log_listeners.append(listener)

    def add_entry(self, log_msg: str) -> int:
        index = len(self.event_log)
        if self.timed_entries_open > 0:
            self.event_log.append(("  "*self.timed_entries_open)+" "+log_msg)
        else:
            self.event_log.append(log_msg)
        for listener in self.event_log_listeners:
            listener(log_msg)
        return index

    @contextmanager
    def add_benchmarked_entry(self, log_msg: str) -> Generator[None, None, None]:
        index = self.add_entry(log_msg)
        start_time = time.time()
        self.timed_entries_open += 1
        yield
        self.timed_entries_open -= 1
        elapsed_time = time.time() - start_time
        self.event_log[index] += " (took {:.2f} seconds)".format(elapsed_time)

    def append_to_file(self, target_file: str) -> None:
        if os.path.exists(target_file) and os.path.getsize(target_file) > 0.5 * 1024 * 1024:
            six_hours_ago = time.time() - 6 * 60 * 60
            if os.path.getmtime(target_file) < six_hours_ago:
                with open(target_file, 'w', encoding='utf-8') as file:
                    file.truncate()
        with open(target_file, 'a', encoding='utf-8') as file:
            file.write(str(self)+"\n\n=================================================================\n\n")

    def __str__(self) -> str:
        return "\n".join(self.event_log)
