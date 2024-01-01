"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import io
import cProfile
from contextlib import contextmanager
import os
import pprint
import pstats
import threading
from typing import IO, Any, Optional, TypeVar
from aqt.utils import showInfo

var_dump_count = 0


def var_dump(var: Any) -> None:
    global var_dump_count
    if var_dump_count < 10:
        var_str = pprint.pformat(var, sort_dicts=False)
        if len(var_str) > 2000:
            var_str = var_str[:2000].rsplit(' ', 1)[0]
        showInfo(var_str)
        var_dump_count += 1


var_dump_log_count = 0


def var_dump_log(var: Any, show_as_info=False) -> None:
    global var_dump_log_count
    if var_dump_log_count < 10:
        dump_log_file = os.path.join(os.path.dirname(__file__), '..', '..', 'dump.log')
        with open(dump_log_file, 'a', encoding='utf-8') as file:
            file.write(pprint.pformat(var, sort_dicts=False, width=160) + "\n\n=================================================================\n\n")
        if (show_as_info):
            var_dump(var)
        var_dump_log_count += 1


def is_numeric_value(val: Any) -> bool:

    return isinstance(val, int) or isinstance(val, float) or str(val).replace(".", "", 1).isnumeric()


def get_float(val: Any) -> Optional[float]:

    if val is None or isinstance(val, float):
        return val

    if isinstance(val, str) and not is_numeric_value(val):
        return None

    try:
        return float(val)
    except ValueError:
        return None

    return None


@contextmanager
def profile_context(amount=40):
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield profiler
    finally:
        profiler.disable()

        def print_results(output: IO[Any], sort_key: pstats.SortKey):
            ps = pstats.Stats(profiler, stream=output).sort_stats(sort_key)
            ps.print_callers(amount)
            output.write("\n\n-------------------------------------------------\n\n\n")
            ps.print_stats(amount)
            output.write("\n\n================================================\n\n\n\n")

        output = io.StringIO()
        print_results(output, pstats.SortKey.CUMULATIVE)
        print_results(output, pstats.SortKey.TIME)
        profiling_results = output.getvalue()

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


K = TypeVar('K')


def normalize_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    new_dict = input_dict.copy()
    min_value = min(new_dict.values())

    if (min_value > 0):
        for key in new_dict:
            new_dict[key] = (new_dict[key]-min_value)+0.00001
    elif (min_value < 0):
        for key in new_dict:
            new_dict[key] = (new_dict[key]+abs(min_value))+0.00001

    max_val = max(new_dict.values())

    if (max_val != 0):
        for key in new_dict:
            new_dict[key] = new_dict[key]/max_val

    return new_dict


def sort_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:
    return dict(sorted(input_dict.items(), key=lambda x: x[1], reverse=True))
