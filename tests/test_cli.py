import random

import gptme.cli
import pytest
from click.testing import CliRunner

CMDFIX = gptme.cli.CMDFIX


@pytest.fixture(scope="session")
def runid():
    return random.randint(0, 100000)


@pytest.fixture
def name(runid, request):
    return f"test-{runid}-{request.node.name}"


@pytest.fixture
def runner():
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


def test_help(runner: CliRunner):
    result = runner.invoke(gptme.cli.main, ["--help"])
    assert result.exit_code == 0


def test_shell(name: str, runner: CliRunner):
    result = runner.invoke(
        gptme.cli.main, ["--name", name, f'{CMDFIX}shell echo "yes"']
    )
    output = result.output.split("System")[-1]
    # check for two 'yes' in output (both command and stdout)
    assert output.count("yes") == 2, result.output
    assert result.exit_code == 0


def test_python(name: str, runner: CliRunner):
    result = runner.invoke(
        gptme.cli.main, ["--name", name, f'{CMDFIX}python print("yes")']
    )
    assert "yes\n" in result.output
    assert result.exit_code == 0


def test_python_error(name: str, runner: CliRunner):
    result = runner.invoke(
        gptme.cli.main,
        ["--name", name, f'{CMDFIX}python raise Exception("yes")'],
    )
    assert "Exception: yes" in result.output
    assert result.exit_code == 0


_block_sh = """function test() {
    echo "start"  # start

    echo "after empty line"
}"""
_block_py = """def test():
    print("start")  # start

    print("after empty line")
"""
blocks = {"python": _block_py, "sh": _block_sh}


@pytest.mark.parametrize("lang", ["python", "sh"])
def test_block(name: str, lang: str, runner: CliRunner):
    # tests that shell codeblocks are formatted correctly such that whitespace and newlines are preserved
    code = blocks[lang]
    code = f"""```{lang}
{code.strip()}
```"""
    assert "'" not in code
    args = [
        "--name",
        name,
        f"{CMDFIX}impersonate {code}",
    ]
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    output = result.output
    print(f"output: {output}\nEND")
    output = output.split("# start")[-1]
    printcmd = "print" if lang == "python" else "echo"
    assert f"\n\n    {printcmd}" in output
    assert result.exit_code == 0


# TODO: these could be fast if we had a cache
@pytest.mark.slow
def test_generate_primes(name: str, runner: CliRunner):
    result = runner.invoke(
        gptme.cli.main,
        [
            "--name",
            name,
            "print the first 10 prime numbers",
            "--model",
            "gpt-3.5-turbo",
        ],
    )
    # check that the 9th and 10th prime is present
    assert "23" in result.output
    assert "29" in result.output
    assert result.exit_code == 0
