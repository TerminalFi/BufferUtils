from enum import Enum


class Operation(Enum):
    ADDITIVE = "additive"
    SUBTRACTIVE = "subtractive"


class SelectionMode(Enum):
    PUSH = "push"
    POP = "pop"
    REMOVE = "remove"
    ADD = "add"
    SUBTRACT = "subtract"
    SMART = "smart"
    TOGGLE = "toggle"
    CYCLE = "cycle"

    def should_push(self, has_fields: bool) -> bool:
        return {
            SelectionMode.POP: False,
            SelectionMode.REMOVE: False,
            SelectionMode.PUSH: True,
            SelectionMode.SUBTRACT: False,
            SelectionMode.ADD: False,
        }.get(self, not has_fields)
