from ..types import ExecTest
from .basic import tests as tests_basic
from .browser import tests as tests_browser
from .init_projects import tests as tests_init_projects

suites: dict[str, list[ExecTest]] = {
    "basic": tests_basic,
    "init_projects": tests_init_projects,
    "browser": tests_browser,
}

tests: list[ExecTest] = [test for suite in suites.values() for test in suite]
tests_map: dict[str, ExecTest] = {test["name"]: test for test in tests}

tests_default_ids: list[str] = [
    "hello",
    "hello-patch",
    "hello-ask",
    "prime100",
    "init-git",
]
tests_default: list[ExecTest] = [tests_map[test_id] for test_id in tests_default_ids]
