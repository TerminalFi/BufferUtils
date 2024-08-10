from __future__ import annotations

import sublime_plugin

from ..lib.words import get_buffer_name
from .common import BufferUtilsHandler
from .syntax import SyntaxSelectorListInputHandler
from .utils import get_settings


class BufferUtilsNewFileCommand(BufferUtilsHandler, sublime_plugin.WindowCommand):
    def run(self, syntax: str, **kwargs) -> None:
        view = self.window.new_file(syntax=syntax)

        settings = get_settings().get("settings", {})
        if settings.get("random_buffer_names", False):
            view.set_name(get_buffer_name())

        if kwargs.get("scratch", False):
            view.set_scratch(True)

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        return SyntaxSelectorListInputHandler(None, args)
