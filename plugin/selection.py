from __future__ import annotations

from typing import Sequence

import sublime
import sublime_plugin

from .constants import SETTING_PREFIX
from .enum import SelectionMode

_FLAGS = sublime.DRAW_EMPTY | sublime.DRAW_NO_FILL


def get_settings(key: str, default: bool = None):
    """Get the setting specified by the key."""
    settings = sublime.load_settings("BufferUtils.sublime-settings")
    return settings.get(key, default)


def get_prefixed_settings(key: str, default: bool = None):
    """
    Get the setting specified by the key,
    with the prefix `selection_fields.`.
    """
    return get_settings("selection_fields.{0}".format(key), default)


class RegionManager:
    view: sublime.View
    added_fields: bool = False

    def get_regions(self, key: str) -> Sequence[sublime.Region]:
        return self.view.get_regions(f"{SETTING_PREFIX}.{key}")

    def add_regions(self, key: str, regions: Sequence[sublime.Region], scope: str):
        self.view.add_regions(
            f"{SETTING_PREFIX}.{key}", regions, scope=scope, flags=_FLAGS
        )

    def erase_regions(self, key: str):
        self.view.erase_regions(f"{SETTING_PREFIX}.{key}")

    def store_selection_fields(self, regions: Sequence[sublime.Region]):
        scope_setting = "scope.added_fields" if self.added_fields else "scope.fields"
        scope = get_prefixed_settings(scope_setting, "comment")
        key = "added_selections" if self.added_fields else "stored_selections"
        self.add_regions(key, regions, scope)

    def restore_selection_fields(self) -> Sequence[sublime.Region]:
        regions = self.get_regions("stored_selections")
        if self.added_fields:
            regions.extend(self.get_regions("added_selections"))
        self.erase_fields()
        return regions

    def erase_fields(self):
        self.erase_regions("stored_selections")
        self.erase_regions("added_selections")


class SelectionHandler:
    view: sublime.View
    mode: SelectionMode
    jump_forward: bool
    only_other: bool

    def process_selection(self):
        region_manager = RegionManager(self.view)
        has_only_added_fields = not region_manager.get_regions(
            "stored_selections"
        ) and get_prefixed_settings("add_separated", True)
        sel_regions = None

        if self.mode.should_push(bool(region_manager.get_regions("stored_selections"))):
            sel_regions = self._change_selection()
        elif self.mode == SelectionMode.SUBTRACT:
            sel_regions = self._subtract_selection()
        elif self.mode == SelectionMode.ADD:
            sel_regions = self._add_selection()
        elif self.mode == SelectionMode.REMOVE:
            sel_regions = self._restore_selection()
        elif self.mode not in [SelectionMode.SMART, SelectionMode.CYCLE]:
            sel_regions = self._restore_selection()
        elif self.mode == SelectionMode.SMART and has_only_added_fields:
            sel_regions = self._restore_selection()
        else:
            sel_regions = self._execute_jump()

        if sel_regions:
            self.view.sel().clear()
            self.view.sel().add_all(sel_regions)
            self.view.show(sel_regions[0])

    def _change_selection(self):
        sels = list(self.view.sel())
        border_pos = 0 if self.jump_forward else len(sels) - 1
        return _change_selection(self.view, sels, border_pos)

    def _subtract_selection(self):
        region_manager = RegionManager(self.view)
        sel_regions = list(self.view.sel())
        pushed_regions = list(
            _subtract_selection(region_manager.restore_selection_fields(), sel_regions)
        )
        region_manager.store_selection_fields(pushed_regions)
        return sel_regions

    def _add_selection(self):
        region_manager = RegionManager(self.view)
        pushed_regions = region_manager.restore_selection_fields()
        sel_regions = list(self.view.sel())
        region_manager.store_selection_fields(sel_regions + pushed_regions)
        return sel_regions

    def _restore_selection(self):
        region_manager = RegionManager(self.view, self.only_other)
        return region_manager.restore_selection_fields()

    def _execute_jump(self):
        region_manager = RegionManager(self.view)
        regions, pos = _execute_jump(self.view, self.jump_forward, self.only_other)
        if self.mode == SelectionMode.CYCLE:
            pos = pos % len(regions)
        pos_valid = pos == pos % len(regions)
        if pos_valid:
            return _change_selection(self.view, regions, pos)
        else:
            return region_manager.restore_selection_fields()


def _set_fields(
    view: sublime.View,
    regions: Sequence[sublime.Region],
    added_fields: bool = False,
):
    """Set the fields as regions in the view."""
    # push the fields to the view, kwargs for ST3 and pos args for ST2
    if not added_fields:
        reg_name = f"{SETTING_PREFIX}.stored_selections"
        scope_setting = "scope.fields"
    else:
        reg_name = f"{SETTING_PREFIX}.added_selections"
        scope_setting = "scope.added_fields"
    scope = get_prefixed_settings(scope_setting, "comment")
    view.add_regions(reg_name, regions, scope=scope, flags=_FLAGS)


def _get_fields(view: sublime.View, added_fields=True):
    fields = view.get_regions(f"{SETTING_PREFIX}.stored_selections")
    if added_fields:
        fields.extend(view.get_regions(f"{SETTING_PREFIX}.added_selections"))
    return fields


def _erase_added_fields(view: sublime.View):
    view.erase_regions(f"{SETTING_PREFIX}.added_selections")


def _erase_fields(view: sublime.View):
    view.erase_regions(f"{SETTING_PREFIX}.stored_selections")
    view.erase_regions(f"{SETTING_PREFIX}.added_selections")


def _change_selection(view: sublime.View, regions: Sequence[sublime.Region], pos: int):
    """Extract the next selection, push all other fields."""
    # save and remove the position in the regions
    sel = regions.pop(pos)
    _set_fields(view, regions)
    return [sel]


def _restore_selection(view: sublime.View, only_other):
    """Restore the selection from the pushed fields."""
    sel_regions = _get_fields(view)
    if not only_other:
        sel_regions.extend(view.sel())
    _erase_fields(view)
    return sel_regions


def _execute_jump(view: sublime.View, jump_forward: bool, only_other: bool):
    """
    Add the selection to the fields and move the selection to the
    next field.
    """
    regions = _get_fields(view)
    try:
        # search for the first field, which is behind the last selection
        end = max(sel.end() for sel in view.sel())
        pos = next(i for i, sel in enumerate(regions) if sel.begin() > end)
    except StopIteration:
        pos = len(regions)
    sel_count = 0 if only_other else len(view.sel())

    if sel_count == 1:
        regions.insert(pos, view.sel()[0])
    else:
        regions = regions[:pos] + list(view.sel()) + regions[pos:]
    delta = sel_count if jump_forward else -1
    pos = pos + delta
    return regions, pos


def _subtract_selection(
    pushed_regions: Sequence[sublime.Region], selections: Sequence[sublime.Region]
):
    """Subtract the selections from the pushed fields."""
    for reg in pushed_regions:
        for sel in selections:
            if sel.begin() <= reg.end() and reg.begin() <= sel.end():
                # yield the region from the start of the field to the selection
                if reg.begin() < sel.begin():
                    yield sublime.Region(reg.begin(), sel.begin())
                # update the region to be from the end of the selection to
                # the end of the field
                reg = sublime.Region(sel.end(), reg.end())
                # if the region is not forward, break and don't add it as field
                if not reg.a < reg.b:
                    break
        else:
            # yield the region as field
            yield reg


class BufferUtilsSelectionFieldsCommand(sublime_plugin.TextCommand):
    def run(
        self,
        edit: sublime.Edit,
        mode: SelectionMode = SelectionMode.SMART,
        jump_forward: bool = True,
        only_other: bool = False,
    ):
        if isinstance(mode, str):
            try:
                mode = SelectionMode(mode.lower())
            except ValueError:
                raise ValueError(f"'{mode}' is not a valid SelectionMode")
        view = self.view
        has_only_added_fields = not _get_fields(
            view, added_fields=False
        ) and get_prefixed_settings("add_separated", True)

        # the regions, which should be selected after executing this command
        sel_regions = None

        if mode.should_push(
            bool(_get_fields(view))
        ):  # push or initial trigger with anything except pop
            sels = list(view.sel())
            border_pos = 0 if jump_forward else len(sels) - 1
            sel_regions = _change_selection(view, sels, border_pos)
        elif (
            mode == SelectionMode.SUBTRACT
        ):  # subtract selections from the pushed fields
            sel_regions = list(view.sel())
            pushed_regions = _get_fields(view)
            regions = list(_subtract_selection(pushed_regions, sel_regions))
            _erase_added_fields(view)
            _set_fields(view, regions, added_fields=has_only_added_fields)
        elif mode == SelectionMode.ADD:  # add selections to the pushed fields
            pushed_regions = _get_fields(view)
            sel_regions = list(view.sel())
            _set_fields(
                view, sel_regions + pushed_regions, added_fields=has_only_added_fields
            )
        elif mode == SelectionMode.REMOVE:  # remove pushed fields
            pop_regions = _restore_selection(view, only_other)
            sel_regions = list(view.sel()) if not only_other else pop_regions
        elif mode not in [
            SelectionMode.SMART,
            SelectionMode.CYCLE,
        ]:  # pop or toggle with regions
            sel_regions = _restore_selection(view, only_other)
        # pop added fields instead of jumping
        elif mode == SelectionMode.SMART and has_only_added_fields:
            sel_regions = _restore_selection(view, only_other)
        else:  # smart or cycle
            # execute the jump
            regions, pos = _execute_jump(view, jump_forward, only_other)
            # if we are in the cycle mode force the position to be valid
            if mode == SelectionMode.CYCLE:
                pos = pos % len(regions)
            # check whether it is a valid position
            pos_valid = pos == pos % len(regions)
            if pos_valid:
                # move the selection to the new field
                sel_regions = _change_selection(view, regions, pos)
            else:
                # if we reached the end restore the selection and
                # remove the highlight regions
                sel_regions = _restore_selection(view, only_other)

        # change to the result selections, if they exists
        if sel_regions:
            view.sel().clear()
            view.sel().add_all(sel_regions)
            view.show(sel_regions[0])


class SelectionFieldsContext(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
        if key not in [
            "is_selection_field",
            "is_selection_field.added_fields",
            "selection_fields_tab_enabled",
            "selection_fields_escape_enabled",
        ]:
            return False

        if key == "is_selection_field":
            # selection field is active if the regions are pushed to the view
            result = bool(_get_fields(view, added_fields=False))
        elif key == "is_selection_field.added_fields":
            # selection field is active if the regions are pushed to the view
            # also if added fields are pushed
            result = bool(_get_fields(view))
        else:
            # the *_enabled key has the same name in the settings
            result = get_settings(key, False)

        if operator == sublime.OP_EQUAL:
            result = result == operand
        elif operator == sublime.OP_NOT_EQUAL:
            result = result != operand
        else:
            raise Exception("Invalid Operator '{0}'.".format(operator))
        return result
