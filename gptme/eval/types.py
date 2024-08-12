from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict

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
    """
    Result of a single test case on the execution of a prompt.
    """

    name: str
    passed: bool
    code: str
    duration: float


class ExecResult(TypedDict):
    """
    Result of executing a prompt.
    """

    name: str
    status: Literal["success", "error", "timeout"]
    results: list[CaseResult]
    timings: dict[str, float]
    stdout: str
    stderr: str


class ExecTest(TypedDict):
    """
    Test case for executing a prompt.
    """

    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]
