"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations

import io
import cProfile
from contextlib import contextmanager
import itertools
import json
import math
import os
import pprint
import pstats
import re
import sys
from typing import IO, TYPE_CHECKING, Any, Callable, Literal, Optional, Type, TypeVar, cast
from dataclasses import dataclass, fields

from aqt.qt import Qt, QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle, QVBoxLayout, QWidget
from aqt.utils import showInfo
from typing_extensions import dataclass_transform

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

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
            file.write(log_entry + "\n\n=================================================================\n\n")
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


def remove_trailing_commas_from_json(json_str: str) -> str:

    return re.sub(r'("(?:\\?.)*?")|,(\s*)([]}])', r'\1\2\3', json_str)


if TYPE_CHECKING:
    from typing import Union
    from typing_extensions import TypeAlias
    JSON_TYPE: TypeAlias = Union[dict[str, "JSON_TYPE"], list["JSON_TYPE"], str, int, float, bool, None]
else:
    JSON_TYPE = Any


def load_json(json_data: str) -> JSON_TYPE:

    try:
        return json.loads(json_data)
    except json.JSONDecodeError as e:
        if not "double quotes" in e.msg:
            raise e
        # try again, but throw original exception if it fails
        new_json_data = remove_trailing_commas_from_json(json_data)
        try:
            return json.loads(new_json_data)
        except json.JSONDecodeError:
            raise e from None


@contextmanager
def profile_context(amount: int = 40) -> Iterator[cProfile.Profile]:

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
        with open(dump_file, 'w', encoding='utf-8') as f:
            f.write(profiling_results)


T = TypeVar('T')
K = TypeVar('K')


# batched for Python < 3.12

if sys.version_info >= (3, 12):
    from itertools import batched as batched
else:

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

#  override decorator for Python < 3.12

if sys.version_info >= (3, 12):
    from typing import override
elif TYPE_CHECKING:
    from typing_extensions import override
else:
    # Dummy decorator for runtime on Python < 3.12
    def override(func):
        return func

#  dataclass_with_slots for Python < 3.10

if sys.version_info >= (3, 10):
    @dataclass_transform()
    def dataclass_with_slots(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
        def wrapper(cls: Type[T]) -> Type[T]:
            return dataclass(slots=True, **kwargs)(cls)  # type: ignore[misc]
        return wrapper
else:
    def _make_slots_from_annotations(cls: Any) -> None:
        try:
            slot_names = tuple(f.name for f in fields(cls))
        except Exception:
            ann = getattr(cls, "__annotations__", {})
            slot_names = tuple(ann.keys()) if isinstance(ann, dict) else ()

        if not hasattr(cls, "__slots__"):
            setattr(cls, "__slots__", slot_names)

    @dataclass_transform()
    def dataclass_with_slots(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
        def wrapper(cls: Type[T]) -> Type[T]:
            cls2 = dataclass(**kwargs)(cls)  # type: ignore[misc]
            _make_slots_from_annotations(cls2)
            return cls2
        return wrapper


def normalize_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    new_dict = input_dict.copy()

    if not input_dict:
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


def positional_value_absolute(position: int) -> float:

    positional_val_a = 1.0 / (position ** 0.125)
    positional_val_b = max(0.0, 1.0 - 0.0001 * (position - 1))
    positional_val_c = math.exp(-0.00016 * (position - 1))

    return (positional_val_a + positional_val_b + positional_val_c * 3.0) * 0.2


def normalize_dict_positional_floats_values(input_dict: dict[K, float], absolute_values: bool = True) -> dict[K, float]:

    if not input_dict:
        return {}

    values = list(input_dict.values())

    assert values == sorted(values, reverse=True), "Input dictionary must be in descending order."

    get_position_value: Callable[[int], float]

    if absolute_values:
        get_position_value = positional_value_absolute
    else:
        max_rank = len(set(values))
        inv_max_rank = 1.0 / max_rank
        get_position_value = lambda value_index: (max_rank - value_index + 1) * inv_max_rank

    new_dict = input_dict.copy()
    value_index = 0
    last_value = None

    for key, value in input_dict.items():
        if value != last_value:
            value_index += 1
            last_value = value

        new_dict[key] = get_position_value(value_index)

    return new_dict


def sort_dict_floats_values(input_dict: dict[K, float]) -> dict[K, float]:

    return dict(sorted(input_dict.items(), key=lambda x: x[1], reverse=True))


def remove_bottom_percent_dict(input_dict: dict[K, float], percent_remove: float, min_num_preserve: int) -> dict[K, float]:

    assert list(input_dict.values()) == sorted(input_dict.values(), reverse=True), "Input dictionary must be in descending order."

    keep_offset_end = int(len(input_dict) * (1-percent_remove))

    if keep_offset_end < min_num_preserve:
        keep_offset_end = min_num_preserve

    return dict(list(input_dict.items())[0:keep_offset_end])


ShowResultType = Literal["information", "warning", "error"]

def show_result(message: str, title: str, type: ShowResultType, parent: QWidget) -> bool:

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)

    # Main layout
    layout = QVBoxLayout()
    content_layout = QHBoxLayout()
    content_layout.setSpacing(15)  # Add spacing between icon and text

    # Icon
    if type == 'information':
        style_icon = QStyle.StandardPixmap.SP_MessageBoxInformation
    elif type == 'warning':
        style_icon = QStyle.StandardPixmap.SP_MessageBoxWarning
    elif type == 'error':
        style_icon = QStyle.StandardPixmap.SP_MessageBoxCritical
    else:
        raise ValueError("Invalid type!")

    icon_label = QLabel()
    icon_label.setPixmap(dialog.style().standardIcon(style_icon).pixmap(32, 32))  # type: ignore

    icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align icon to top
    icon_label.setContentsMargins(0, 0, 5, 0)
    content_layout.addWidget(icon_label)

    # Message
    label = QLabel(message)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    content_layout.addWidget(label)
    layout.addLayout(content_layout)

    # Button
    button_layout = QHBoxLayout()
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(dialog.accept)

    button_layout.addStretch()
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    # Dialog
    dialog.setLayout(layout)
    dialog.setMinimumWidth(300)
    dialog.adjustSize()
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
    dialog.setFixedSize(dialog.sizeHint())

    return dialog.exec() == QDialog.DialogCode.Accepted
