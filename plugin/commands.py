import html
from typing import Any
from typing import Dict
from typing import List
from typing import Union
import re
import sublime
import sublime_plugin


from ..lib.words import get_buffer_name
from .utils import get_settings
from .utils import Case
from .utils import StringMetaData

supports_override_audit = False
try:
    from OverrideAudit.lib.packages import PackageInfo
    supports_override_audit = True
except:
    pass


class BufferUtils:
    def input_description(self):
        return "Syntax:"


class BufferUtilsNewFileCommand(BufferUtils, sublime_plugin.WindowCommand):
    def run(self, syntax: str, **kwargs) -> None:
        view = self.window.new_file(syntax=syntax)

        settings = get_settings().get('settings', {})
        if settings.get('random_buffer_names', False):
            view.set_name(get_buffer_name())

        if kwargs.get('scratch', False):
            view.set_scratch(True)

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

        # Extract package and file information
        parts = syntax.split("/")
        package_name = parts[1]
        file_name = parts[-1]

        has_override = False
        if supports_override_audit:
            pkg_info = PackageInfo(name=package_name)
            has_override = file_name in pkg_info.override_files()

        # Construct the HTML template
        html_template = """
            <style>
            a {{
                color: color(var(--foreground) alpha(0.6));
                text-decoration: none;
            }}
            .override {{
                display: {0};
                color: color(var(--foreground) alpha(0.6));
                background-color: color(var(--foreground) alpha(0.08));
                border-radius: 4px;
                padding: 0.05em 4px;
                margin-top: 0.2em;
                font-size: 0.9em;
            }}
            </style>
            <strong>Details </strong><small>{1}</small>
            <div>
                <small><strong>Path: </strong></small><small>{2}</small>
            </div>
            <div>
                <div class="override">
                    <a title="Create/Edit Override" href='subl:override_audit_create_override {{"file": "{3}", "package": "{4}"}}'><small>{5}</small></a>
                </div>
            </div>
        """

        return sublime.Html(html_template.format('inline-block' if supports_override_audit else 'none', "(Has Override)" if has_override else "", file_name, syntax.split("/")[-1], package_name, "Create Override" if not has_override else "Edit Override"))

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
                details='Provided by: <strong><u>{0}</u></strong>'.format(syntax.path.split("/")[1]),
                annotation=syntax.scope,
            )
            for syntax in syntax_list
        ]

        return list_input_items, current_index


class OperationInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, view) -> None:
        self.view = view

    def name(self):
        return 'subtractive'

    def list_items(self):
        return [
            sublime.ListInputItem(
                'Additive', False,  '<strong>Logic:</strong> <em>adds matches to current selection</em>'),
            sublime.ListInputItem(
                'Subtractive', True,  '<strong>Logic:</strong> <em>removes matches from current selection</em>')
        ]

    def next_input(self, args):
        return ExpressionInputHandler(self.view, args)


class ExpressionInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view, args) -> None:
        self.view = view
        self.args = args

    def initial_text(self) -> str:
        return self.view.settings().get('bu.last_expression', '')

    def confirm(self, arg):
        self.view.erase_regions(
            'bu_expression_preview')
        return arg

    def preview(self, value) -> Union[sublime.Html, None]:
        if not get_settings().get('live_selection', True):
            return

        if not value:
            self.view.erase_regions('bu_expression_preview')
            return None

        operation, preview_scope = self.get_operation_and_scope()

        regions = self.view.find_all(value, sublime.IGNORECASE)
        regions = self.filter_regions_by_operation(regions, operation)

        self.view.add_regions(
            'bu_expression_preview', regions, preview_scope, '',
            sublime.DRAW_NO_FILL | sublime.PERSISTENT
        )

        return sublime.Html(
            '<strong>Expression:</strong> <em>{0}</em><br/>'.format(html.escape(value)) +
            '<strong>Instances:</strong> <em>{0}</em><br/>'.format(len(self.view.get_regions("bu_expression_preview"))) +
            '<strong>Selections:</strong> <em>{0}</em><br/>'.format(len(self.view.get_regions("bu_expression_preview")) + len(self.view.sel()))
        )

    def get_operation_and_scope(self):
        operation = 'Subtractive' if self.args.get('subtractive', False) else 'Additive'
        scope_setting = 'find.regex.additive.scope' if operation == 'Additive' else 'find.regex.subtractive.scope'
        default_scope = 'region.greenish' if operation == 'Additive' else 'region.redish'

        preview_scope = get_settings().get(scope_setting, default_scope)

        return operation, preview_scope

    def filter_regions_by_operation(self, regions, operation):
        if operation == 'Additive':
            return [r for r in regions if not self.view.sel().contains(r)]
        return [r for r in regions if self.view.sel().contains(r)]

    def cancel(self) -> None:
        self.view.erase_regions(
            'bu_expression_preview')

        if not get_settings().get('expression.persistence', True):
            self.view.settings().set('bu.last_expression', '')


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

        if get_settings().get('expression.persistence', True):
            self.view.settings().set('bu.last_expression', expression)

    def input(self, args) -> Union[ExpressionInputHandler, OperationInputHandler]:
        if args.get('subtractive', None):
            return ExpressionInputHandler(self.view, args)
        return OperationInputHandler(self.view)


class PreserveCase:
    def analyze_string(self, value):
        separators = '-_/. '
        counts = [value.count(sep) for sep in separators]

        if max(counts):
            separator = separators[counts.index(max(counts))]
            groups = value.split(separator)
        else:
            separator = ''
            groups = self.split_by_case(value)

        return StringMetaData(separator, [self.get_case_type(s) for s in groups], groups)

    def split_by_case(self, value):
        parts = re.split(r'(?<!^)((?:[^A-Z][^a-z])|(?:[^a-z][^A-Z]))', value)
        groups = [parts[0]]

        for i in range(1, len(parts), 2):
            groups.append(parts[i] + parts[i + 1])

        return groups

    def get_case_type(self, value):
        if value.islower():
            return Case.lower
        elif value.isupper():
            return Case.upper
        elif value[0].isupper():
            return Case.capitalized
        return Case.mixed

    def replace_string_with_case(self, old_string, new_strings):
        old_string_meta = self.analyze_string(old_string)
        old_cases = old_string_meta.cases

        for i, current_str in enumerate(new_strings):
            index = min(i, len(old_cases) - 1)
            case_type = old_cases[index]

            if case_type == Case.upper:
                new_strings[i] = current_str.upper()
            elif case_type == Case.lower:
                new_strings[i] = current_str.lower()
            elif case_type == Case.capitalized:
                new_strings[i] = current_str.capitalize()

        return old_string_meta.separator.join(new_strings)

class BufferUtilsPreserveCaseCommand(PreserveCase, sublime_plugin.TextCommand):
    def run(self, edit, value: str, **kwargs) -> None:
        self.edit = edit
        self.savedSelection = [r for r in self.view.sel()]

        if not sum(r.size() for r in self.savedSelection):
            sublime.status_message('Cannot run preserve case on an empty selection.')
            return

        if isinstance(value, str):
            self.preserve_case(value)

    def input(self, args: Dict[str, Any]):
        self.savedSelection = [r for r in self.view.sel()]
        return PreserveCaseInputHandler(self.view.substr(self.savedSelection[0]), args)

    def preserve_case(self, value):
        offset = 0
        new_strings = self.analyze_string(value).stringGroups

        for region in self.savedSelection:
            adjusted_region = sublime.Region(region.begin() + offset, region.end() + offset)
            current_str = self.view.substr(adjusted_region)
            new_str = self.replace_string_with_case(current_str, new_strings)

            self.view.replace(self.edit, adjusted_region, new_str)
            offset += len(new_str) - len(current_str)


class PreserveCaseInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, intial_text, args) -> None:
        self.intial_text = intial_text
        self.args = args

    def name(self):
        return 'value'

    def initial_text(self) -> str:
        return self.intial_text

    def confirm(self, arg):
        return arg



class BufferUtilsNormalizeSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _):
        selection = self.view.sel()
        if not selection:
            return

        regions = self.normalize_regions(selection) if not self.are_regions_normalized(selection) else self.invert_regions(selection)

        selection.clear()
        for region in regions:
            selection.add(region)

        region = self.find_first_visible_region()
        if region:
            self.view.show(region.b, False)

    def find_first_visible_region(self) -> Union[sublime.Region, None]:
        visible_region = self.view.visible_region()
        return next((region for region in self.view.sel() if region.intersects(visible_region)), None)

    def normalize_regions(self, regions: List[sublime.Region]) -> List[sublime.Region]:
        return [sublime.Region(min(r.a, r.b), max(r.a, r.b)) for r in regions]

    def invert_regions(self, regions: List[sublime.Region]) -> List[sublime.Region]:
        return [sublime.Region(r.b, r.a) if r.a < r.b else r for r in regions]

    def are_regions_normalized(self, regions: List[sublime.Region]) -> bool:
        return all(r.a < r.b for r in regions)
