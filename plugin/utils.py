from __future__ import annotations

import threading
from functools import wraps
from typing import Any, Callable, List, TypeVar, cast

import sublime

from .constants import SETTINGS

T_Callable = TypeVar("T_Callable", bound=Callable[..., Any])


class Case:
    LOWER = 0
    UPPER = 1
    CAPITALIZED = 2
    MIXED = 3


class StringAttributes:
    def __init__(
        self, delimiter: str, case_types: list[int], groups: list[str]
    ) -> None:
        self.delimiter: str = delimiter
        self.case_types: list[int] = case_types
        self.groups: list[str] = groups


def get_settings(key: str | List[str] = "settings", default: Any = None):
    settings = sublime.load_settings(SETTINGS)
    if key:
        if isinstance(key, list):
            result = settings
            for k in key:
                result = result.get(k, default)
                if result is default:
                    break
            return result
        return settings.get(key, default)
    return settings


# Adapted from LSP-Copilot
def debounce(
    time_s: float = 0.3, disabled: bool = False
) -> Callable[[T_Callable], T_Callable]:
    """
    Debounce a function so that it's called after `time_s` seconds.
    If it's called multiple times in the time frame, it will only run the last call.
    If `disabled` is True, the function is called immediately without debouncing.

    Taken and modified from https://github.com/salesforce/decorator-operations
    """

    def decorator(func: T_Callable) -> T_Callable:
        @wraps(func)
        def debounced(*args: Any, **kwargs: Any) -> None:
            if disabled:
                return func(*args, **kwargs)

            def call_function() -> Any:
                delattr(debounced, "_timer")
                return func(*args, **kwargs)

            timer: threading.Timer | None = getattr(debounced, "_timer", None)
            if timer is not None:
                timer.cancel()

            timer = threading.Timer(time_s, call_function)
            timer.start()
            setattr(debounced, "_timer", timer)

        setattr(debounced, "_timer", None)
        return cast(T_Callable, debounced)

    return decorator


class MutableView:
    def __init__(self, view):
        self.view = view

    def __enter__(self):
        self.view.set_read_only(False)
        return self.view

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.view.set_read_only(True)
