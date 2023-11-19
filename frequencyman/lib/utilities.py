import asyncio
import concurrent.futures
from functools import partial, wraps
from io import StringIO
import io
import cProfile
from contextlib import contextmanager
import os
import pprint
import pstats
import threading
from typing import Any, Callable, Coroutine, TypeVar
from aqt.utils import showInfo

var_dump_count = 0


def var_dump(var) -> None:
    global var_dump_count
    if var_dump_count < 10:
        var_str = pprint.pformat(var, sort_dicts=False)
        if len(var_str) > 2000:
            var_str = var_str[:2000].rsplit(' ', 1)[0]
        showInfo(var_str)
        var_dump_count += 1


var_dump_log_count = 0


def var_dump_log(var, show_as_info=False) -> None:
    global var_dump_log_count
    if var_dump_log_count < 10:
        dump_log_file = os.path.join(os.path.dirname(__file__), '..', '..', 'dump.log')
        with open(dump_log_file, 'a', encoding='utf-8') as file:
            file.write(pprint.pformat(var, sort_dicts=False) + "\n\n=================================================================\n\n")
        if (show_as_info):
            var_dump(var)
        var_dump_log_count += 1


@contextmanager
def profile_context(sortby=pstats.SortKey.TIME, amount=40):
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield profiler
    finally:
        profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
        ps.print_callers(amount)
        print("\n\n\n=========================================\n\n\n")
        ps.print_stats(amount)
        profiling_results = s.getvalue()
        dump_file = os.path.join(os.path.dirname(__file__), '..', '..', 'profiling_results.txt')
        with open(dump_file, 'w') as f:
            f.write(profiling_results) 


def chunked_list(input_list: list, chunk_size: int) -> list[list]:
    """
    Split a list into smaller lists of a specified chunk size.

    Parameters:
        input_list (list): The list to be split.
        chunk_size (int): The size of each chunk.

    Returns:
        list[list]: A list of smaller lists, each containing chunk_size elements.
    """
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]
