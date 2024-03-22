from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class ToolSpec:
    name: str
    instructions: str
    examples: str
    functions: list[Callable]
    enabled: bool = True

    def __after_init__(self):
        # TODO: register functions
        # TODO: register instructions and example prompt
        ...
