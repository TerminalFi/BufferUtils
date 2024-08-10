from __future__ import annotations

from typing import Any, Dict

import sublime
import sublime_plugin

from .utils import get_settings


class EventListener(sublime_plugin.EventListener):
    def on_window_command(
        self, _: sublime.Window, command_name: str, args: Dict[str, Any]
    ):
        if command_name == "new_file":
            if get_settings(key=["settings", "listeners"]).get("new_file"):
                return ("buffer_utils_new_file", args)
