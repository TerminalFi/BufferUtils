from __future__ import annotations

import sublime_plugin

from .utils import get_settings


class EventListener(sublime_plugin.EventListener):
    def on_window_command(self, window, command_name, args):
        settings = get_settings(default={})
        if command_name == "new_file":
            if settings.get("listeners", {}).get("new_file"):
                return ("buffer_utils_new_file", args)
