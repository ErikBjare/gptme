import random

import gptme.cli
import pytest
from click.testing import CliRunner


@pytest.fixture(scope="session")
def runid():
    return random.randint(0, 100000)


@pytest.fixture
def name(runid, request):
    return f"test-{runid}-{request.node.name}"


def test_help():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(gptme.cli.main, ["--help"])
        assert result.exit_code == 0


def test_shell(name: str):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            gptme.cli.main, ["-y", "--name", name, '.shell echo "yes"']
        )
        assert result.exit_code == 0
        assert "yes\n" in result.output


def test_python(name: str):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            gptme.cli.main, ["-y", "--name", name, '.python print("yes")']
        )
        assert result.exit_code == 0
        assert "yes\n" in result.output


def test_python_error(name: str):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            gptme.cli.main, ["-y", "--name", name, '.python raise Exception("yes")']
        )
        assert result.exit_code == 0
        assert "Exception: yes" in result.output


@pytest.mark.slow
def test_generate_primes(name: str):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            gptme.cli.main,
            [
                "-y",
                "--name",
                name,
                "print the first 10 prime numbers",
            ],
        )
        assert result.exit_code == 0
        # check that the 9th and 10th prime is present
        assert "23" in result.output
        assert "29" in result.output
