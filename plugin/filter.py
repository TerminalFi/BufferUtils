from __future__ import annotations

from typing import Any, Dict, Sequence

import sublime
import sublime_plugin

from .constants import VIEW_OR_PANEL_FILTER_PANEL
from .utils import MutableView, get_settings, debounce


class FilterViewOrPanel:
    disable_debounce = False

    def __init__(self):
        self.filter_output_view = None
        self.filter_input_view = None
        self.current_view_or_panel = None

    def get_io_panel(self) -> None:
        if not (window := sublime.active_window()):
            return

        # Check if IO panel already exists
        output_view, input_view = window.find_io_panel(VIEW_OR_PANEL_FILTER_PANEL)
        if output_view and input_view:
            self.filter_output_view = output_view
            self.filter_input_view = input_view
        else:
            # Create new IO panel with input and output views
            self.filter_output_view, self.filter_input_view = window.create_io_panel(
                VIEW_OR_PANEL_FILTER_PANEL,
                self.on_input_submitted
            )

    def on_input_submitted(self, filter_text: str) -> None:
        """Called when user submits text from the input view"""
        if self.current_view_or_panel:
            self.filter_from_current_view(filter_text)

    def close(self) -> None:
        if self.filter_output_view:
            window = sublime.active_window()
            if window:
                window.destroy_output_panel(VIEW_OR_PANEL_FILTER_PANEL)
                self.filter_output_view = None
                self.filter_input_view = None
                self.current_view_or_panel = None

    def show_panel(self, view_or_panel_id: int) -> None:
        """Show the IO panel and set the current view/panel to filter"""
        target_view = self.find_view_or_panel(view_or_panel_id)
        if not target_view:

            return

        self.current_view_or_panel = target_view

        self.get_io_panel()
        if not self.filter_output_view or not self.filter_input_view:
            print("BufferUtils Filter: Failed to create IO panel")
            return

        # Show the full content of the target view/panel initially
        self.show_full_content(target_view)

        window = sublime.active_window()
        if window:
            window.run_command("show_panel", {"panel": f"output.{VIEW_OR_PANEL_FILTER_PANEL}"})

            # Set focus to input view for immediate typing
            if self.filter_input_view:
                window.focus_view(self.filter_input_view)

    def show_full_content(self, view: sublime.View) -> None:
        """Display the full content of the view in the output panel"""
        if not self.filter_output_view:
            return

        view_size = view.size()
        if view_size == 0:
            content = "(This view/panel is empty)"
        else:
            # Get all content from the view
            content = view.substr(sublime.Region(0, view_size))

        with MutableView(self.filter_output_view):
            # Copy syntax from source view if available
            if view.syntax():
                self.filter_output_view.assign_syntax(view.syntax().path)
            self.filter_output_view.settings().set("word_wrap", False)

            # Clear and populate with full content
            self.filter_output_view.run_command("buffer_utils_erase_view")

            if content:
                # Add each line with line numbers for reference
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    self.filter_output_view.run_command(
                        "append",
                        {
                            "characters": line + "\n",
                        },
                    )

    def filter_from_current_view(self, filter_text: str) -> int:
        """Filter the current view/panel and display results in output view"""
        if not self.current_view_or_panel:
            print("BufferUtils Filter: No current view/panel set")
            return None

        return self.filter_view(self.current_view_or_panel, filter_text)

    def filter_view(self, view: sublime.View, filter_text: str) -> int:
        """Filter the specified view and display results in output view"""
        # Ensure we have the IO panel
        self.get_io_panel()
        if not self.filter_output_view:
            print("BufferUtils Filter: No output view available")
            return None

        # Always clear the output panel first
        with MutableView(self.filter_output_view):
            self.filter_output_view.run_command("buffer_utils_erase_view")

        if not filter_text:
            # If no filter text, show full content again
            self.show_full_content(view)
            return None

        # Debug: Check if view has content
        view_size = view.size()

        if view_size == 0:
            print("BufferUtils Filter: Warning - target view is empty")

        regions = view.find_all(filter_text, sublime.IGNORECASE)

        with MutableView(self.filter_output_view):
            # Copy syntax from source view if available
            if view.syntax():
                self.filter_output_view.assign_syntax(view.syntax().path)
            self.filter_output_view.settings().set("word_wrap", False)

            if not regions:
                self.filter_output_view.run_command(
                    "append",
                    {
                        "characters": f"No matches found for: '{filter_text}'\n",
                        "force": True,
                    },
                )
                # Add debug info about the source view
                if view_size > 0:
                    sample_text = view.substr(sublime.Region(0, min(100, view_size)))
                    self.filter_output_view.run_command(
                        "append",
                        {
                            "characters": f"\nSource view content sample (first 100 chars):\n{sample_text}\n",
                            "force": True,
                        },
                    )
                return 0

            for region in regions:
                # Get the full line containing the match for better context
                line_region = view.line(region)
                line_text = view.substr(line_region)

                self.filter_output_view.run_command(
                    "append",
                    {
                        "characters": line_text if line_text.endswith("\n") else f"{line_text}\n",
                    },
                )
        return len(regions)

    @debounce(time_s=0.2, disabled=disable_debounce)
    def filter_realtime(self, filter_text: str) -> int:
        """Real-time filtering as user types in input view"""
        if get_settings(key=["settings", "filter"]).get("preview", True):
            return self.filter_from_current_view(filter_text)
        return None

    def is_filter_input_view(self, view: sublime.View) -> bool:
        """Check if the given view is our filter input view"""
        return self.filter_input_view and view.id() == self.filter_input_view.id()

    def find_view_or_panel(self, view_or_panel_id: str | int) -> sublime.View | None:
        if not (window := sublime.active_window()):
            return None

        target_id = int(view_or_panel_id)

        # Check regular views first
        for view in window.views():
            if view.id() == target_id:
                return view

        # Check output panels
        for panel_name in sorted(window.panels()):
            if panel_name.startswith("output.") and not panel_name.endswith(VIEW_OR_PANEL_FILTER_PANEL):
                panel_view = window.find_output_panel(panel_name.replace("output.", ""))
                if panel_view and panel_view.id() == target_id:
                    return panel_view

        return None


# Create a global instance to maintain state across commands
_filter_instance = FilterViewOrPanel()


class BufferUtilsFilterViewOrPanelCommand(sublime_plugin.WindowCommand):
    def run(self, view_or_panel_id: str = None):
        """Main command to start filtering"""
        if view_or_panel_id:
            # Direct filtering with specified view/panel
            _filter_instance.show_panel(int(view_or_panel_id))
        else:
            # Show input handler to select view/panel first
            pass  # Input handler will be called

    def input(self, args: Dict[str, Any]) -> sublime_plugin.ListInputHandler:
        if "view_or_panel_id" not in args:
            return BufferUtilsViewAndPanelListInputHandler(self.window)


class BufferUtilsViewAndPanelListInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, window: sublime.Window) -> None:
        self.window: sublime.Window = window

    def name(self) -> str:
        return "view_or_panel_id"

    def list_items(self) -> Sequence[sublime.ListInputItem]:
        if not (window := sublime.active_window()):
            return []

        items = []

        # Add regular views
        for view in window.views():
            name = view.file_name()
            if name:
                name = name.split("/")[-1]
            else:
                name = view.name() or "Untitled"

            items.append(sublime.ListInputItem(
                text=f"View: {name}",
                value=str(view.id())
            ))

        # Add output panels
        for panel_name in sorted(window.panels()):
            if panel_name.startswith("output.") and not panel_name.endswith(VIEW_OR_PANEL_FILTER_PANEL):
                panel_view = window.find_output_panel(panel_name.replace("output.", ""))
                if panel_view:
                    items.append(sublime.ListInputItem(
                        text=f"Panel: {panel_name.replace('output.', '')}",
                        value=str(panel_view.id())
                    ))

        return items

    def preview(self, value: str) -> str:
        return f"Filter View/Panel ID: {value}"

    def confirm(self, value: str) -> None:
        """Called when user selects a view/panel"""
        _filter_instance.show_panel(int(value))


class BufferUtilsCloseFilterPanelCommand(sublime_plugin.WindowCommand):
    """Command to close the filter panel"""

    def run(self):
        _filter_instance.close()


class BufferUtilsFilterEventListener(sublime_plugin.EventListener):
    """Event listener to handle real-time filtering"""

    def on_modified(self, view: sublime.View) -> None:
        """Handle real-time filtering as user types in the input view"""
        if not _filter_instance.is_filter_input_view(view):
            return

        if not _filter_instance.current_view_or_panel:
            return

        # Get the current text and filter
        filter_text = view.substr(sublime.Region(0, view.size()))
        _filter_instance.filter_realtime(filter_text)

    def on_pre_close(self, view: sublime.View) -> None:
        """Clean up when views are closed"""
        if _filter_instance.is_filter_input_view(view):
            _filter_instance.close()
