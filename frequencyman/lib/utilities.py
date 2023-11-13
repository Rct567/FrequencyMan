import asyncio
import concurrent.futures
from io import StringIO
import io
import cProfile
from contextlib import contextmanager
import os
import pprint
import pstats
import threading
from typing import Any, Callable, Coroutine
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
def profile_context(sortby=pstats.SortKey.CUMULATIVE):
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield profiler
    finally:
        profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
        ps.print_callers()
        print("\n\n\n=========================================\n\n\n")
        ps.print_stats()
        profiling_results = s.getvalue()
        dump_file = os.path.join(os.path.dirname(__file__), '..', '..', 'profiling_results.txt')
        with open(dump_file, 'w') as f:
            f.write(profiling_results)


def promise_all(async_functions: list[Coroutine]) -> list:
    """
    Run multiple asynchronous functions concurrently and return their results.

    Parameters:
        async_functions (list[Coroutine]): The list of asynchronous functions to run.

    Returns:
        list: The results of the asynchronous functions.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(asyncio.gather(*async_functions))
    finally:
        loop.close()

    return results


def run_async_tasks(async_task: Callable, task_data: list) -> list:
    """
    Run asynchronous tasks using a ThreadPoolExecutor.

    Parameters:
        async_task (Callable): The asynchronous task to be executed.
        task_data (list): The data to be passed to each task.

    Returns:
        list: The results of the asynchronous tasks.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(async_task, task_data))
    return results


def run_async_tasks_process(async_task: Callable, task_data: list) -> list:
    """
    Run asynchronous tasks using a ProcessPoolExecutor.

    Parameters:
        async_task (Callable): The asynchronous task to be executed.
        task_data (list): The data to be passed to each task.

    Returns:
        list: The results of the asynchronous tasks.
    """
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(async_task, task_data))
    return results


def make_async(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Create an asynchronous version of a function.

    Parameters:
        func (Callable[..., Any]): The function to be made asynchronous.

    Returns:
        Callable[..., Any]: The asynchronous version of the function.
    """
    async def async_version(*args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    return async_version


def make_async_wrap(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    A decorator to make a function asynchronous.

    Parameters:
        func (Callable[..., Any]): The function to be made asynchronous.

    Returns:
        Callable[..., Any]: An asynchronous version of the input function.
    """
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        return result
    return wrapper


async def make_async_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Create an asynchronous version of a function and call it with the provided arguments.

    Parameters:
        fn (Callable[..., Any]): The function to be made asynchronous.
        *args (Any): Positional arguments for the function.
        **kwargs (Any): Keyword arguments for the function.

    Returns:
        Any: The result of the asynchronous function call.
    """
    return await asyncio.to_thread(fn, *args, **kwargs)


async def make_async_call_threading(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Create an asynchronous version of a function and call it with the provided arguments.

    Parameters:
        fn (Callable[..., Any]): The function to be made asynchronous.
        *args (Any): Positional arguments for the function.
        **kwargs (Any): Keyword arguments for the function.

    Returns:
        Any: The result of the asynchronous function call.
    """
    def async_fn(result, fn, args, kwargs):
        result[0] = fn(*args, **kwargs)

    result = [None]
    thread = threading.Thread(target=async_fn, args=(result, fn, args, kwargs))
    thread.start()
    thread.join()

    return result[0]


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
