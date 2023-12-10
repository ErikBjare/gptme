import pytest

from evals import tests
from main import execute


@pytest.mark.slow
@pytest.mark.eval
def test_eval(test):
    """
    This test will be run for each eval in the tests list.
    See pytest_generate_tests() below.
    """
    result = execute(test)
    assert all(case["passed"] for case in result["results"])


# Hook to generate tests from the tests list
def pytest_generate_tests(metafunc):
    if "test" in metafunc.fixturenames:
        metafunc.parametrize("test", tests, ids=[test["name"] for test in tests])
