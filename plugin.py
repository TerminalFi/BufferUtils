import sublime
import sublime_plugin


class BufferUtils:
    def input_description(self):
        return "Syntax:"


class BufferUtilsNewFileCommand(BufferUtils, sublime_plugin.WindowCommand):
    def run(self, syntax):
        self.window.new_file(syntax=syntax)

    def input(self, args):
        return SyntaxSelectorListInputHandler(None, args)


class BufferUtilsSetSyntaxCommand(BufferUtils, sublime_plugin.TextCommand):
    def run(self, _, syntax: str, **kwargs) -> None:
        self.view.set_syntax_file(syntax)

    def input(self, args):
        args["preselect_current_syntax"] = True
        return SyntaxSelectorListInputHandler(self.view, args)

    def input_description(self):
        return "Syntax:"


class SyntaxSelectorListInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, view, args={}):
        self.view = view
        self.args = args
        self._prev_syntax = None

        if self.view:
            self._prev_syntax = self.view.settings().get("syntax")

    def name(self) -> str:
        return "syntax"

    def placeholder(self):
        return "Choose a syntax..."

    def preview(self, syntax):
        if self.view:
            self.view.set_syntax_file(syntax)
        return sublime.Html(f"<strong>Syntax Path</strong> <div><small>{syntax}</small></div>")

    def cancel(self):
        if self.view:
            self.view.set_syntax_file(self._prev_syntax)

    def list_items(self):
        syntax_list = sorted(
            (syntax for syntax in sublime.list_syntaxes() if self.args.get("show_hidden", False) or not syntax.hidden),
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
                details=f'Provided by: <strong><u>{syntax.path.split("/")[1]}</u></strong>',
                annotation=syntax.scope,
            )
            for syntax in syntax_list
        ]

        return list_input_items, current_index

