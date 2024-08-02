import html
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import sublime
import sublime_plugin
from more_itertools import first_true
from vision.context import Context

from .constants import VIEW_OR_PANEL_FILTER_PANEL
from .lib.words import get_buffer_name
from .utils import Case, MutableView, StringMetaData, debounce, get_settings

supports_override_audit = False
try:
    from OverrideAudit.lib.packages import PackageInfo

    supports_override_audit = True
except ImportError:
    pass


class BufferUtils:
    def input_description(self) -> str:
        return "Syntax"


class BufferUtilsNewFileCommand(BufferUtils, sublime_plugin.WindowCommand):
    def run(self, syntax: str, **kwargs) -> None:
        view = self.window.new_file(syntax=syntax)

        settings = get_settings().get("settings", {})
        if settings.get("random_buffer_names", False):
            view.set_name(get_buffer_name())

        if kwargs.get("scratch", False):
            view.set_scratch(True)

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        return SyntaxSelectorListInputHandler(None, args)


class BufferUtilsSetSyntaxCommand(BufferUtils, sublime_plugin.TextCommand):
    def run(self, _, syntax: str, **kwargs) -> None:
        self.view.set_syntax_file(syntax)

    def input(self, args):
        args["preselect_current_syntax"] = True
        return SyntaxSelectorListInputHandler(self.view, args)

    def input_description(self):
        return "Syntax"


class SyntaxSelectorListInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, view: Optional[sublime.View], args: dict = {}):
        self.view: sublime.View | None = view
        self.args: dict = args
        self._prev_syntax: sublime.Syntax | None = None

        if self.view:
            self._prev_syntax = self.view.syntax()

    def name(self) -> str:
        return "syntax"

    def placeholder(self):
        return "Choose a syntax…"

    def preview(self, syntax: str):
        if self.view:
            self.view.assign_syntax(self._prev_syntax.path)

        # Extract package and file information
        parts = syntax.path.split("/")
        package_name = parts[1]
        file_name = parts[-1]

        has_override = False
        if supports_override_audit:
            pkg_info = PackageInfo(name=package_name)
            has_override = file_name in pkg_info.override_files()

        ctx = Context()
        root = ctx.html()
        with root:
            ctx.style(
                {
                    "a": {
                        "color": "color(var(--foreground) alpha(0.6))",
                        "text-decoration": "none",
                    },
                    ".override": {
                        "display": "inline-block"
                        if supports_override_audit
                        else "none",
                        "color": "color(var(--foreground) alpha(0.6))",
                        "background-color": "color(var(--foreground) alpha(0.08))",
                        "border-radius": "4px",
                        "padding": "0.05em 4px",
                        "margin-top": "0.2em",
                        "font-size": "0.9em",
                    },
                }
            )
            ctx.strong("Details ")
            ctx.small("(Has Override)" if has_override else "")
            with ctx.div():
                with ctx.small():
                    ctx.strong("Path: ")
                    ctx.small(file_name)
                with ctx.div():
                    with ctx.div().set_classes("append", "override"):
                        with ctx.a(
                            href=sublime.command_url(
                                "override_audit_create_override",
                                {
                                    "file": syntax.split("/")[-1],
                                    "package": package_name,
                                },
                            ),
                        ):
                            ctx.small(
                                "Create Override"
                                if not has_override
                                else "Edit Override"
                            )

        return sublime.Html(root.render())

    def cancel(self):
        if self.view:
            self.view.assign_syntax(self._prev_syntax.path)

    def list_items(self) -> Tuple[Sequence[sublime.ListInputItem], int]:
        syntax_list = sorted(
            (
                syntax
                for syntax in sublime.list_syntaxes()
                if self.args.get("show_hidden", False) or not syntax.hidden
            ),
            key=lambda x: x.name,
        )
        current_index = (
            next(
                (
                    index
                    for index, syntax in enumerate(syntax_list)
                    if syntax.path == self._prev_syntax
                ),
                0,
            )
            if self.args.get("preselect_current_syntax")
            else 0
        )
        list_input_items = [
            sublime.ListInputItem(
                syntax.name,
                syntax.path,
                details="Provided by: <strong><u>{0}</u></strong>".format(
                    syntax.path.split("/")[1]
                ),
                annotation=syntax.scope,
            )
            for syntax in syntax_list
        ]

        return list_input_items, current_index


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

    def initial_text(self) -> str:
        return self.view.settings().get("bu.last_expression", "")

    def confirm(self, arg):
        self.view.erase_regions("bu_expression_preview")
        return arg

    def preview(self, value) -> Union[sublime.Html, None]:
        if not get_settings().get("live_selection", True):
            return

        if not value:
            self.view.erase_regions("bu_expression_preview")
            return None

        operation, preview_scope = self.get_operation_and_scope()

        regions = self.view.find_all(value, sublime.IGNORECASE)
        regions = self.filter_regions_by_operation(regions, operation)

        self.view.add_regions(
            "bu_expression_preview",
            regions,
            preview_scope,
            "",
            sublime.DRAW_NO_FILL | sublime.PERSISTENT,
        )

        return sublime.Html(
            "<strong>Expression:</strong> <em>{0}</em><br/>".format(html.escape(value))
            + "<strong>Instances:</strong> <em>{0}</em><br/>".format(
                len(self.view.get_regions("bu_expression_preview"))
            )
            + "<strong>Selections:</strong> <em>{0}</em><br/>".format(
                len(self.view.get_regions("bu_expression_preview"))
                + len(self.view.sel())
            )
        )

    def get_operation_and_scope(self):
        operation = "Subtractive" if self.args.get("subtractive", False) else "Additive"
        scope_setting = (
            "find.regex.additive.scope"
            if operation == "Additive"
            else "find.regex.subtractive.scope"
        )
        default_scope = (
            "region.greenish" if operation == "Additive" else "region.redish"
        )

        preview_scope = get_settings().get(scope_setting, default_scope)

        return operation, preview_scope

    def filter_regions_by_operation(self, regions, operation):
        if operation == "Additive":
            return [r for r in regions if not self.view.sel().contains(r)]
        return [r for r in regions if self.view.sel().contains(r)]

    def cancel(self) -> None:
        self.view.erase_regions("bu_expression_preview")

        if not get_settings().get("expression.persistence", True):
            self.view.settings().set("bu.last_expression", "")


class BufferUtilsFindRegexCommand(sublime_plugin.TextCommand):
    def run(self, _, subtractive: bool, expression: str, case: bool = True) -> None:
        flag = sublime.IGNORECASE if not case else 0
        regions = self.view.find_all(expression, flag)

        for region in regions:
            if subtractive:
                self.view.sel().subtract(region)
            else:
                self.view.sel().add(region)

        for region in self.view.sel():
            if region.empty():
                self.view.sel().subtract(region)

        if get_settings().get("expression.persistence", True):
            self.view.settings().set("bu.last_expression", expression)

    def input(self, args) -> Union[ExpressionInputHandler, OperationInputHandler]:
        if args.get("subtractive", None):
            return ExpressionInputHandler(self.view, args)
        return OperationInputHandler(self.view)


class PreserveCase:
    def analyze_string(self, value: str) -> StringMetaData:
        separators = "-_/. "
        separator = max(separators, key=value.count)

        if value.count(separator) > 0:
            groups = value.split(separator)
        else:
            separator = ""
            groups = self._split_by_case(value)

        return StringMetaData(
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
        old_cases = old_string_meta.cases

        for i, current_str in enumerate(new_strings):
            case_type = old_cases[min(i, len(old_cases) - 1)]

            if case_type == Case.UPPER:
                new_strings[i] = current_str.upper()
            elif case_type == Case.LOWER:
                new_strings[i] = current_str.lower()
            elif case_type == Case.CAPITALIZED:
                new_strings[i] = current_str.capitalize()

        return old_string_meta.separator.join(new_strings)


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
        new_strings = self.analyze_string(value).string_groups

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
            self.normalize_regions(selection)
            if not self.are_regions_normalized(selection)
            else self.invert_regions(selection)
        )

        selection.clear()
        for region in regions:
            selection.add(region)

        region = self.find_first_visible_region()
        if region:
            self.view.show(region.b, False)

    def find_first_visible_region(self) -> Union[sublime.Region, None]:
        visible_region = self.view.visible_region()
        return next(
            (region for region in self.view.sel() if region.intersects(visible_region)),
            None,
        )

    def normalize_regions(self, regions: sublime.Selection) -> List[sublime.Region]:
        return [
            sublime.Region(min(region.a, region.b), max(region.a, region.b))
            for region in regions
        ]

    def invert_regions(self, regions: sublime.Selection) -> List[sublime.Region]:
        return [sublime.Region(r.b, r.a) if r.a < r.b else r for r in regions]

    def are_regions_normalized(self, regions: sublime.Selection) -> bool:
        return all(r.a < r.b for r in regions)


class FilterViewOrPanel:
    def get_panel(self) -> None:
        self.filter_panel = sublime.active_window().create_output_panel(
            VIEW_OR_PANEL_FILTER_PANEL
        )

    def close(self) -> None:
        if self.filter_panel:
            self.filter_panel.close()

    def filter(self, view_or_panel_id: int, filter_text: str) -> None:
        self.get_panel()
        if not filter_text:
            return None

        if not (view := self.find_view_or_panel(view_or_panel_id)):
            return None

        sublime.active_window().run_command(
            "show_panel", {"panel": f"output.{VIEW_OR_PANEL_FILTER_PANEL}"}
        )

        regions = view.find_all(filter_text, sublime.IGNORECASE)

        if not regions:
            return None

        with MutableView(self.filter_panel):
            self.filter_panel.assign_syntax(view.syntax().path)
            self.filter_panel.settings().set("word_wrap", False)
            self.filter_panel.run_command("erase_view")
            for region in regions:
                text = view.substr(region)
                self.filter_panel.run_command(
                    "append",
                    {
                        "characters": text if text.endswith("\n") else f"{text}\n",
                    },
                )

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
        if (
            get_settings()
            .get("settings", {})
            .get("filter_view_or_panel.live_preview", False)
        ):
            return
        self.filter(int(view_or_panel_id), filter_text)

    def input(self, args) -> sublime_plugin.ListInputHandler:
        return BufferUtilsViewAndPanelListInputHandler(self.window)


class BufferUtilsViewAndPanelListInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, window: sublime.Window) -> None:
        self.window: sublime.Window = window

    def name(self) -> str:
        return "view_or_panel_id"

    def list_items(self) -> Sequence[sublime.ListInputItem]:
        window = sublime.active_window()
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

    def preview(self, value) -> str:
        return f"Filter: {value}"

    def next_input(self, args) -> sublime_plugin.TextInputHandler:
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

    @debounce()
    def preview(self, value) -> Optional[sublime.Html]:
        if (
            not get_settings()
            .get("settings", {})
            .get("filter_view_or_panel.live_preview", False)
        ):
            return None

        self.filter(self.args["view_or_panel_id"], value)

        return sublime.Html(
            "<strong>Instances:</strong> <em>{0}</em><br/>".format(len([]))
        )

    def cancel(self) -> None:
        self.close()
