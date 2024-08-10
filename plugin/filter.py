from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import sublime
import sublime_plugin
from more_itertools import first_true

from .constants import VIEW_OR_PANEL_FILTER_PANEL
from .utils import MutableView, debounce, get_settings


class FilterViewOrPanel:
    disable_debounce = False

    def get_panel(self) -> None:
        if not (window := sublime.active_window()):
            return
        self.filter_panel = window.create_output_panel(VIEW_OR_PANEL_FILTER_PANEL)

    def close(self) -> None:
        if self.filter_panel:
            self.filter_panel.close()

    def filter(self, view_or_panel_id: int, filter_text: str) -> int:
        self.get_panel()
        if not filter_text:
            return None

        if not (view := self.find_view_or_panel(view_or_panel_id)):
            return None

        sublime.active_window().run_command(
            "show_panel", {"panel": f"output.{VIEW_OR_PANEL_FILTER_PANEL}"}
        )

        regions = view.find_all(filter_text, sublime.IGNORECASE)

        with MutableView(self.filter_panel):
            self.filter_panel.assign_syntax(view.syntax().path)
            self.filter_panel.settings().set("word_wrap", False)
            self.filter_panel.run_command("erase_view")

            if not regions:
                self.filter_panel.run_command(
                    "append",
                    {
                        "characters": f"No matches found for: {filter_text}\n",
                        "force": True,
                    },
                )
                return None
            for region in regions:
                text = view.substr(region)
                self.filter_panel.run_command(
                    "append",
                    {
                        "characters": text if text.endswith("\n") else f"{text}\n",
                    },
                )
        return len(regions)

    def find_view_or_panel(self, view_or_panel_id: str) -> Optional[sublime.View]:
        views: Sequence[sublime.View] = sublime.active_window().views()
        panels: Sequence[sublime.View] = list(
            filter(
                None,
                (
                    sublime.active_window().find_output_panel(
                        panel.replace("output.", "")
                    )
                    for panel in sorted(sublime.active_window().panels())
                    if panel.startswith("output.")
                    and not panel.endswith(VIEW_OR_PANEL_FILTER_PANEL)
                ),
            )
        )
        return first_true(
            views + panels, pred=lambda x: x.id() == int(view_or_panel_id)
        )


class BufferUtilsFilterViewOrPanelCommand(
    FilterViewOrPanel, sublime_plugin.WindowCommand
):
    def run(self, view_or_panel_id: str, filter_text: str):
        if get_settings(default={}).get("filter_view_or_panel.live_preview", False):
            return
        self.filter(int(view_or_panel_id), filter_text)

    def input(self, args: Dict[str, Any]) -> sublime_plugin.ListInputHandler:
        return BufferUtilsViewAndPanelListInputHandler(self.window)


class BufferUtilsViewAndPanelListInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, window: sublime.Window) -> None:
        self.window: sublime.Window = window

    def name(self) -> str:
        return "view_or_panel_id"

    def list_items(self) -> Sequence[sublime.ListInputItem]:
        if not (window := sublime.active_window()):
            return
        views: Sequence[tuple[str, sublime.View]] = [
            (view.file_name() or view.name(), view) for view in window.views()
        ]
        panels: Sequence[tuple[str, sublime.View]] = [
            (
                panel.replace("output.", ""),
                window.find_output_panel(panel.replace("output.", "")),
            )
            for panel in sorted(window.panels())
            if panel.startswith("output.")
            and not panel.endswith(VIEW_OR_PANEL_FILTER_PANEL)
        ]

        return [
            sublime.ListInputItem(text=name, value=str(view.id()))
            for name, view in views + panels
        ]

    def preview(self, value: str) -> str:
        return f"Filter View ID: {value}"

    def next_input(self, args: Dict[str, Any]) -> sublime_plugin.TextInputHandler:
        return BufferUtilsFilterInputHandler(args)


class BufferUtilsFilterInputHandler(FilterViewOrPanel, sublime_plugin.TextInputHandler):
    def __init__(self, args: Dict[str, Any]) -> None:
        self.args: Dict[str, Any] = args

    def name(self) -> str:
        return "filter_text"

    def initial_text(self) -> str:
        return ""

    def confirm(self, arg) -> Dict[str, Any]:
        return arg

    @debounce(disabled=FilterViewOrPanel.disable_debounce)
    def preview(self, value) -> Optional[sublime.Html]:
        if not get_settings(default={}).get("filter_view_or_panel.live_preview", False):
            return None

        total_matches = self.filter(self.args["view_or_panel_id"], value)
        return sublime.Html(f"<strong>Instances:</strong> <em>{total_matches}</em>")

    def cancel(self) -> None:
        self.close()
