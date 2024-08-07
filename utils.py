from __future__ import annotations

import threading
from functools import wraps
from typing import Any, Callable, TypeVar

import sublime

from .constants import SETTINGS

T_Callable = TypeVar("T_Callable", bound=Callable[..., Any])


class Case:
    LOWER = 0
    UPPER = 1
    CAPITALIZED = 2
    MIXED = 3


class StringMetaData:
    def __init__(
        self, separator: str, cases: list[int], string_groups: list[str]
    ) -> None:
        self.separator = separator
        self.cases = cases
        self.string_groups = string_groups


def get_settings():
    return sublime.load_settings(SETTINGS)


def debounce(time_s: float = 1) -> Callable[[T_Callable], T_Callable]:
    def decorator(func: T_Callable) -> T_Callable:
        @wraps(func)
        def debounced(*args: Any, **kwargs: Any) -> None:
            if hasattr(debounced, "_timer"):
                debounced._timer.cancel()

            def call_function() -> Any:
                del debounced._timer
                return func(*args, **kwargs)

            debounced._timer = threading.Timer(time_s, call_function)
            debounced._timer.start()

        return debounced

    return decorator


class MutableView:
    def __init__(self, view):
        self.view = view

    def __enter__(self):
        self.view.set_read_only(False)
        return self.view

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.view.set_read_only(True)
