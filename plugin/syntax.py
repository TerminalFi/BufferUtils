from __future__ import annotations

from typing import Optional, Sequence, Tuple

import sublime
import sublime_plugin
from vision.context import Context

from .common import BufferUtilsHandler

supports_override_audit = False
try:
    from OverrideAudit.lib.packages import PackageInfo

    supports_override_audit = True
except ImportError:
    pass


class BufferUtilsSetSyntaxCommand(BufferUtilsHandler, sublime_plugin.TextCommand):
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
            self.view.assign_syntax(syntax)

        # Extract package and file information
        parts = syntax.split("/")
        package_name = parts[1]
        file_name = parts[-1]

        has_override = False
        if supports_override_audit:
            pkg_info = PackageInfo(name=package_name)
            has_override = file_name in pkg_info.override_files()

        ctx = Context()
        root = ctx.html()
        with root:
            with ctx.body():
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
                    if syntax.path == self._prev_syntax.path
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
