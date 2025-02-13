from __future__ import annotations

from typing import Any

import sublime

from .constants import SETTINGS


class Settings:
    def __init__(self):
        self.default_settings = {
            "selection_fields.scope.fields": "comment",
            "selection_fields.scope.added_fields": "none",
            "selection_fields.add_separated": True,
            "selection_fields_tab_enabled": True,
            "selection_fields_escape_enabled": True,
            "settings": {
                "listeners": {
                    "new_file": True,
                },
                "find": {
                    "preview": True,
                    "persist_expression": True,
                    "regex_additive_scope": "region.greenish",
                    "regex_subtractive_scope": "region.redish",
                },
                "buffer": {
                    "assign_random_name": False,
                },
                "filter": {"preview": True, "disable_debounce": True},
            },
        }
        self._settings = sublime.load_settings(SETTINGS)
        self.settings = self._merge_settings(
            self.default_settings, self._settings.to_dict()
        )
        self.register_on_change()

    def register_on_change(self) -> None:
        self._settings.add_on_change(
            SETTINGS,
            lambda: self._merge_settings(
                self.default_settings, self._settings.to_dict()
            ),
        )
        return

    def _merge_settings(
        self, default: dict[str, Any], user: dict[str, Any] | None
    ) -> dict[str, Any]:
        if user is None:
            return default
        for key, value in user.items():
            if isinstance(value, dict) and key in default:
                default[key] = self._merge_settings(default[key], value)
            else:
                default[key] = value
        return default

    @property
    def selection_fields_scope_fields(self) -> str:
        return self.settings["selection_fields.scope.fields"]

    @selection_fields_scope_fields.setter
    def selection_fields_scope_fields(self, value: str) -> None:
        self.settings["selection_fields.scope.fields"] = value

    @property
    def selection_fields_scope_added_fields(self) -> str:
        return self.settings["selection_fields.scope.added_fields"]

    @selection_fields_scope_added_fields.setter
    def selection_fields_scope_added_fields(self, value: str) -> None:
        self.settings["selection_fields.scope.added_fields"] = value

    @property
    def selection_fields_add_separated(self) -> bool:
        return self.settings["selection_fields.add_separated"]

    @selection_fields_add_separated.setter
    def selection_fields_add_separated(self, value: bool) -> None:
        self.settings["selection_fields.add_separated"] = value

    @property
    def selection_fields_tab_enabled(self) -> bool:
        return self.settings["selection_fields_tab_enabled"]

    @selection_fields_tab_enabled.setter
    def selection_fields_tab_enabled(self, value: bool) -> None:
        self.settings["selection_fields_tab_enabled"] = value

    @property
    def selection_fields_escape_enabled(self) -> bool:
        return self.settings["selection_fields_escape_enabled"]

    @selection_fields_escape_enabled.setter
    def selection_fields_escape_enabled(self, value: bool) -> None:
        self.settings["selection_fields_escape_enabled"] = value

    @property
    def listeners_new_file(self) -> bool:
        return self.settings["settings"]["listeners"]["new_file"]

    @listeners_new_file.setter
    def listeners_new_file(self, value: bool) -> None:
        self.settings["settings"]["listeners"]["new_file"] = value

    @property
    def find_preview(self) -> bool:
        return self.settings["settings"]["find"]["preview"]

    @find_preview.setter
    def find_preview(self, value: bool) -> None:
        self.settings["settings"]["find"]["preview"] = value

    @property
    def find_persist_expression(self) -> bool:
        return self.settings["settings"]["find"]["persist_expression"]

    @find_persist_expression.setter
    def find_persist_expression(self, value: bool) -> None:
        self.settings["settings"]["find"]["persist_expression"] = value

    @property
    def find_regex_additive_scope(self) -> str:
        return self.settings["settings"]["find"]["regex_additive_scope"]

    @find_regex_additive_scope.setter
    def find_regex_additive_scope(self, value: str) -> None:
        self.settings["settings"]["find"]["regex_additive_scope"] = value

    @property
    def find_regex_subtractive_scope(self) -> str:
        return self.settings["settings"]["find"]["regex_subtractive_scope"]

    @find_regex_subtractive_scope.setter
    def find_regex_subtractive_scope(self, value: str) -> None:
        self.settings["settings"]["find"]["regex_subtractive_scope"] = value

    @property
    def buffer_assign_random_name(self) -> bool:
        return self.settings["settings"]["buffer"]["assign_random_name"]

    @buffer_assign_random_name.setter
    def buffer_assign_random_name(self, value: bool) -> None:
        self.settings["settings"]["buffer"]["assign_random_name"] = value

    @property
    def filter_preview(self) -> bool:
        return self.settings["settings"]["filter"]["preview"]

    @filter_preview.setter
    def filter_preview(self, value: bool) -> None:
        self.settings["settings"]["filter"]["preview"] = value

    @property
    def filter_disable_debounce(self) -> bool:
        return self.settings["settings"]["filter"]["disable_debounce"]

    @filter_disable_debounce.setter
    def filter_disable_debounce(self, value: bool) -> None:
        self.settings["settings"]["filter"]["disable_debounce"] = value

    def to_dict(self) -> dict[str, Any]:
        return self.settings


settings = Settings()
