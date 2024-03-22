from dataclasses import dataclass
from typing import TypedDict
from collections.abc import Callable

Files = dict[str, str | bytes]


@dataclass
class ResultContext:
    """
    Context for the result of a test.
    """

    files: Files
    stdout: str
    stderr: str
    exit_code: int


class CaseResult(TypedDict):
    name: str
    passed: bool
    code: str
    duration: float


class ExecResult(TypedDict):
    name: str
    results: list[CaseResult]
    timings: dict[str, float]


class ExecTest(TypedDict):
    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]
