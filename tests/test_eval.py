import pytest
from gptme.eval import execute, tests
from gptme.eval.agents import GPTMe


@pytest.mark.slow
def test_eval(test):
    """
    This test will be run for each eval in the tests list.
    See pytest_generate_tests() below.
    """
    agent = GPTMe("openai/gpt-4o")
    result = execute(test, agent, timeout=30)
    assert all(case["passed"] for case in result["results"])


# Hook to generate tests from the tests list
def pytest_generate_tests(metafunc):
    if "test" in metafunc.fixturenames:
        allowlist = ["hello"]  # for now, only run the hello test
        test_set, test_names = zip(
            *[(test, test["name"]) for test in tests if test["name"] in allowlist]
        )
        metafunc.parametrize("test", test_set, ids=test_names)
