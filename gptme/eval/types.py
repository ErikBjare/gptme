from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict

Files = dict[str, str | bytes]
Status = Literal["success", "error", "timeout"]


@dataclass
class ResultContext:
    """
    Context for the result of a test.
    """

    files: Files
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class CaseResult:
    """
    Result of a single test case on the execution of a prompt.
    """

    name: str
    passed: bool
    code: str
    duration: float


@dataclass
class EvalResult:
    """
    Result of executing an eval.
    """

    name: str
    status: Status
    results: list[CaseResult]
    timings: dict[str, float]
    gen_stdout: str
    gen_stderr: str
    run_stdout: str
    run_stderr: str


class EvalSpec(TypedDict):
    """
    Specification for an eval/test case.
    """

    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]
