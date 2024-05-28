"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from hmac import new
import io
import cProfile
from contextlib import contextmanager
import itertools
import os
import pprint
import pstats
import sys
from typing import IO, Any, Callable, Iterable, Iterator, Optional, TypeVar
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



var_dump_log_size = 0
var_dump_log_count = 0

def var_dump_log(var: Any) -> None:

    global var_dump_log_size
    global var_dump_log_count

    if var_dump_log_size < (1024 * 1024) and var_dump_log_count < 100_000:
        dump_log_file = os.path.join(os.path.dirname(__file__), '..', '..', 'dump.log')
        with open(dump_log_file, 'a', encoding='utf-8') as file:
            log_entry = pprint.pformat(var, sort_dicts=False, width=160)
            file.write(log_entry+ "\n\n=================================================================\n\n")
        var_dump_log_size += len(log_entry)
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


@contextmanager
def profile_context(amount:int=40) -> Iterator[cProfile.Profile]:

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield profiler
    finally:
        profiler.disable()

        def print_results(output: IO[Any], sort_key: pstats.SortKey) -> None:
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

T = TypeVar('T')

def batched(iterable: Iterable[T], n: int) -> Iterator[tuple[T, ...]]:
    """
    Batch an iterable into smaller batches of a specified size.

    Parameters:
        iterable (Iterable): The iterable to be batched.
        n (int): The size of each batch.

    Yields:
        tuple[T, ...]: A tuple of the batched elements.
    """

    it = iter(iterable)
    while True:
        batch = tuple(itertools.islice(it, n))
        if not batch:
            return
        yield batch

K = TypeVar('K')


def normalize_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    new_dict = input_dict.copy()

    if len(input_dict) == 0:
        return new_dict

    min_value = min(new_dict.values())

    if min_value > 0:
        for key in new_dict:
            new_dict[key] = (new_dict[key]-min_value)+sys.float_info.epsilon
    elif min_value < 0:
        raise Exception("Unexpected below zero value found.")

    max_val = max(new_dict.values())

    if max_val > 0:
        for key in new_dict:
            new_dict[key] = new_dict[key]/max_val

    return new_dict


def normalize_positional_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    new_dict = input_dict.copy()

    if len(input_dict) == 0:
        return new_dict

    assert repr(input_dict) == repr(sort_dict_floats_values(input_dict)), "Input dictionary must be in descending order."

    max_rank = len(new_dict)

    for index, key in enumerate(new_dict.keys()):
        positional_val = (max_rank-(index))/max_rank
        new_dict[key] = positional_val

    return new_dict


def sort_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    return dict(sorted(input_dict.items(), key=lambda x: x[1], reverse=True))


def remove_bottom_percent_dict(input_dict: dict[K, float], percent_remove: float, min_num_preserve: int) -> dict[K, float]:

    assert repr(input_dict) == repr(sort_dict_floats_values(input_dict)), "Input dictionary must be in descending order."

    keep_offset_end = int(len(input_dict) * (1-percent_remove))

    if keep_offset_end < min_num_preserve:
        keep_offset_end = min_num_preserve

    return dict(list(input_dict.items())[0:keep_offset_end])



# Check Python version and import override if available, else use a dummy

if sys.version_info >= (3, 12):
    from typing import override as override
else: # A dummy 'override' decorator for Python < 3.12
    T_CALLABLE = TypeVar('T_CALLABLE', bound=Callable)

    def dummy_override(method: T_CALLABLE) -> T_CALLABLE:
        return method

    override = dummy_override
