import sublime

from .constants import SETTINGS


class Case:
    lower = 0
    upper = 1
    capitalized = 2
    mixed = 3


class StringMetaData:
    def __init__(self, separator, cases, string_groups):
        self.separator = separator
        self.cases = cases
        self.stringGroups = string_groups


def get_settings():
    return sublime.load_settings(SETTINGS)

