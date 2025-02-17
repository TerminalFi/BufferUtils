from __future__ import annotations

import html
import re
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Union

import sublime
import sublime_plugin
from more_itertools import first_true

from ..lib.words import get_buffer_name
from .common import BufferUtilsHandler
from .constants import EXPRESSION_PREVIEW_REGION, LAST_EXPRESSION
from .enum import Operation
from .settings import settings
from .syntax import SyntaxSelectorListInputHandler
from .utils import Case, MutableView, StringAttributes


class BufferUtilsNewFileCommand(BufferUtilsHandler, sublime_plugin.WindowCommand):
    def run(self, syntax: str, **kwargs) -> None:
        view = self.window.new_file(syntax=syntax)
        if settings.buffer_assign_random_name:
            view.set_name(get_buffer_name())

        if kwargs.get("scratch", False):
            view.set_scratch(True)

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        return SyntaxSelectorListInputHandler(None, args)


class OperationInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, view: sublime.View) -> None:
        self.view: sublime.View = view

    def name(self) -> str:
        return "subtractive"

    def list_items(self) -> Sequence[sublime.ListInputItem]:
        return [
            sublime.ListInputItem(
                "Additive",
                False,
                "<strong>Logic:</strong> <em>adds matches to current selection</em>",
            ),
            sublime.ListInputItem(
                "Subtractive",
                True,
                "<strong>Logic:</strong> <em>removes matches from current selection</em>",
            ),
        ]

    def next_input(self, args) -> sublime_plugin.CommandInputHandler:
        return ExpressionInputHandler(self.view, args)


class ExpressionInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view: sublime.View, args) -> None:
        self.view: sublime.View = view
        self.args = args
        self.previous_selections = [r for r in self.view.sel()]

    def initial_text(self) -> str:
        return self.view.settings().get(LAST_EXPRESSION, "")

    def confirm(self, arg):
        self.view.erase_regions(EXPRESSION_PREVIEW_REGION)
        self.view.sel().clear()
        self.view.sel().add_all(self.previous_selections)
        return arg

    def preview(self, value: str) -> Optional[sublime.Html]:
        operation, preview_scope = self.get_operation_and_scope()
        if operation == Operation.SUBTRACTIVE:
            if not first_true(
                self.previous_selections,
                False,
                lambda r: not r.empty() or self.view.substr(r).isspace(),
            ):
                return None

        if not settings.find_preview:
            return

        if not value:
            self.view.erase_regions(EXPRESSION_PREVIEW_REGION)
            return None

        self.view.sel().add_all(self.previous_selections)

        regions = self.view.find_all(value, sublime.IGNORECASE)
        regions = self.update_selection(regions, operation)
        self.view.sel().clear()
        self.view.add_regions(
            EXPRESSION_PREVIEW_REGION,
            regions,
            preview_scope,
            "",
            sublime.DRAW_NO_FILL | sublime.PERSISTENT,
        )

        return sublime.Html(
            "<strong>Expression:</strong> <em>{}</em><br/>"
            "<strong>Instances:</strong> <em>{}</em><br/>"
            "<strong>Selections:</strong> <em>{}</em><br/>".format(
                html.escape(value),
                len(self.view.get_regions(EXPRESSION_PREVIEW_REGION)),
                len(self.view.get_regions(EXPRESSION_PREVIEW_REGION))
                + len(self.view.sel()),
            )
        )

    def get_operation_and_scope(self):
        operation = (
            Operation.ADDITIVE
            if not self.args.get("subtractive", False)
            else Operation.SUBTRACTIVE
        )
        scope = (
            settings.find_regex_additive_scope
            if operation == Operation.ADDITIVE
            else settings.find_regex_subtractive_scope
        )

        return operation, scope

    def update_selection(
        self,
        regions: List[sublime.Region],
        operation: Operation,
    ) -> List[sublime.Region]:
        if operation == Operation.ADDITIVE:
            return regions
        return [r for r in regions if self.view.sel().contains(r)]

    def cancel(self) -> None:
        self.view.erase_regions(EXPRESSION_PREVIEW_REGION)

        if not settings.find_persist_expression:
            self.view.settings().set(LAST_EXPRESSION, "")


class BufferUtilsFindRegexCommand(sublime_plugin.TextCommand):
    def run(self, _, subtractive: bool, expression: str, case: bool = True) -> None:
        flag = sublime.IGNORECASE if not case else 0
        regions = self.view.find_all(expression, flag)

        self.update_selection(regions, subtractive)
        self.remove_empty_regions()

        if settings.find_persist_expression:
            self.view.settings().set(LAST_EXPRESSION, expression)

    def update_selection(
        self, regions: List[sublime.Region], subtractive: bool
    ) -> None:
        selection = self.view.sel()
        if subtractive:
            [selection.subtract(region) for region in regions]
        else:
            selection.add_all(regions)

    def remove_empty_regions(self) -> None:
        for region in self.view.sel():
            if region.empty():
                self.view.sel().subtract(region)

    def input(self, args) -> Union[ExpressionInputHandler, OperationInputHandler]:
        if args.get("subtractive", None):
            return ExpressionInputHandler(self.view, args)
        return OperationInputHandler(self.view)


class PreserveCase:
    def analyze_string(self, value: str) -> StringAttributes:
        separators = "-_/. "
        separator = max(separators, key=value.count)

        if value.count(separator) > 0:
            groups = value.split(separator)
        else:
            separator = ""
            groups = self._split_by_case(value)

        return StringAttributes(
            separator, [self._get_case_type(s) for s in groups], groups
        )

    def _split_by_case(self, value: str) -> List[str]:
        parts = re.findall(r"[A-Z]?[^A-Z]*", value)
        return [part for part in parts if part]

    def _get_case_type(self, value: str) -> int:
        if value.islower():
            return Case.LOWER
        elif value.isupper():
            return Case.UPPER
        elif value.istitle():
            return Case.CAPITALIZED
        return Case.MIXED

    def replace_string_with_case(self, old_string: str, new_strings: List[str]) -> str:
        old_string_meta = self.analyze_string(old_string)
        old_cases = old_string_meta.case_types

        for i, current_str in enumerate(new_strings):
            case_type = old_cases[min(i, len(old_cases) - 1)]

            if case_type == Case.UPPER:
                new_strings[i] = current_str.upper()
            elif case_type == Case.LOWER:
                new_strings[i] = current_str.lower()
            elif case_type == Case.CAPITALIZED:
                new_strings[i] = current_str.capitalize()

        return old_string_meta.delimiter.join(new_strings)


class BufferUtilsPreserveCaseCommand(PreserveCase, sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, value: str, **kwargs) -> None:
        selections: Sequence[sublime.Region] = [r for r in self.view.sel()]

        if not sum(r.size() for r in selections):
            sublime.status_message("Cannot run preserve case on an empty selection.")
            return

        if isinstance(value, str):
            self.preserve_case(edit, selections, value)

    def input(self, args: Dict[str, Any]) -> sublime_plugin.TextInputHandler:
        return PreserveCaseInputHandler(self.view.substr(self.view.sel()[0]), args)

    def preserve_case(
        self, edit: sublime.Edit, selections: Sequence[sublime.Region], value: str
    ) -> None:
        offset = 0
        new_strings = self.analyze_string(value).groups

        for region in selections:
            adjusted_region = sublime.Region(
                region.begin() + offset, region.end() + offset
            )
            current_str = self.view.substr(adjusted_region)
            new_str = self.replace_string_with_case(current_str, new_strings)

            self.view.replace(edit, adjusted_region, new_str)
            offset += len(new_str) - len(current_str)


class PreserveCaseInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, intial_text: str, args: Dict[str, Any]) -> None:
        self.intial_text: str = intial_text
        self.args: Dict[str, Any] = args

    def name(self) -> str:
        return "value"

    def initial_text(self) -> str:
        return self.intial_text

    def confirm(self, arg) -> Dict[str, Any]:
        return arg


class BufferUtilsNormalizeSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _):
        selection: sublime.Selection = self.view.sel()
        if not selection:
            return

        regions = (
            self.normalize(selection)
            if not self.is_normalized(selection)
            else self.invert(selection)
        )

        selection.clear()
        selection.add_all(regions)

        if not (
            region := self.find_first_visible_region(
                self.view.visible_region(), self.view.sel()
            )
        ):
            return
        self.view.show(region.b)

    def find_first_visible_region(
        self, visible_region: sublime.Region, regions: List[sublime.Region]
    ) -> Union[sublime.Region, None]:
        return next(
            (region for region in regions if region.intersects(visible_region)),
            None,
        )

    def normalize(self, regions: sublime.Selection) -> List[sublime.Region]:
        return [sublime.Region(*sorted((region.a, region.b))) for region in regions]

    def invert(self, regions: sublime.Selection) -> List[sublime.Region]:
        return [sublime.Region(r.b, r.a) if r.a < r.b else r for r in regions]

    def is_normalized(self, regions: sublime.Selection) -> bool:
        return all(r.a < r.b for r in regions)


class RgSearchCommand(sublime_plugin.WindowCommand):
    def run(self):
        self.window.show_input_panel("Search for:", "", self.on_done, None, None)

    def on_done(self, input):
        if not input:
            sublime.error_message("You must provide a search term.")
            return

        folders = self.window.folders()
        if not folders:
            sublime.error_message("No folders found in the current window.")
            return

        results = []
        for folder in folders:
            results.extend(self.run_rg_search(folder, input))

        if results:
            self.display_results(results)
        else:
            sublime.error_message("No matches found.")

    def run_rg_search(self, folder, search_term):
        try:
            # Run the ripgrep command
            process = subprocess.Popen(
                ["rg", "--vimgrep", search_term, folder],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output, error = process.communicate()

            if error:
                sublime.error_message(f"Error running ripgrep: {error.decode('utf-8')}")
                return []

            # Decode output and split into lines
            return output.decode("utf-8").splitlines()
        except Exception as e:
            sublime.error_message(f"Error running ripgrep: {str(e)}")
            return []

    def display_results(self, results):
        # Create a new buffer to display the results
        output_view = self.window.new_file()
        output_view.set_name("Ripgrep Results")
        output_view.set_scratch(True)
        output_view.assign_syntax("Find Results.hidden-tmLanguage")
        output_view.settings().set("word_wrap", False)
        output_view.settings().set("result_file_regex", "^([^ \t].*):$")
        output_view.settings().set(
            "result_line_regex",
            "^ +([0-9]+):",
        )

        formatted_results = []
        current_file = ""

        for line in results:
            parts = line.split(":")
            if len(parts) < 4:
                continue

            file_path = parts[0]
            line_number = parts[1]
            matched_text = ":".join(parts[3:]).strip()

            if file_path != current_file:
                if current_file:
                    formatted_results.append(
                        ""
                    )  # Add a blank line between different files
                formatted_results.append(f"{file_path}:")
                current_file = file_path

            formatted_results.append(f" {line_number}: {matched_text}")
        with MutableView(output_view):
            output_view.run_command(
                "append", {"characters": "\n".join(formatted_results)}
            )
