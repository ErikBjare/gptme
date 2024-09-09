import importlib
import os
import random
from pathlib import Path
from tempfile import TemporaryDirectory

import gptme.cli
import gptme.constants
import pytest
from click.testing import CliRunner
from gptme.constants import CMDFIX

project_root = Path(__file__).parent.parent
logo = project_root / "media" / "logo.png"


@pytest.fixture(scope="session", autouse=True)
def tmp_data_dir():
    tmpdir = TemporaryDirectory().name
    Path(tmpdir).mkdir(parents=True, exist_ok=True)

    # set the environment variable
    print(f"setting XDG_DATA_HOME to {tmpdir}")
    os.environ["XDG_DATA_HOME"] = tmpdir


@pytest.fixture(scope="session")
def runid():
    return random.randint(0, 100000)


@pytest.fixture
def name(runid, request):
    return f"test-{runid}-{request.node.name}"


@pytest.fixture
def args(name: str) -> list[str]:
    return [
        "--name",
        name,
    ]


@pytest.fixture
def runner():
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


def test_help(runner: CliRunner):
    result = runner.invoke(gptme.cli.main, ["--help"])
    assert result.exit_code == 0


def test_command_exit(args: list[str], runner: CliRunner):
    # tests the /exit command
    args.append(f"{CMDFIX}exit")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)

    # check that the /exit command is present
    assert "/exit" in result.output
    assert result.exit_code == 0


def test_command_help(args: list[str], runner: CliRunner):
    # tests the /exit command
    args.append(f"{CMDFIX}help")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)

    # check that the /exit command is present
    assert "/help" in result.output
    assert result.exit_code == 0


@pytest.mark.slow
def test_command_summarize(args: list[str], runner: CliRunner):
    # tests the /summarize command
    args.append(f"{CMDFIX}summarize")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0


def test_command_fork(args: list[str], runner: CliRunner, name: str):
    # tests the /fork command
    name += "-fork"
    args.append(f"{CMDFIX}fork {name}")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0


def test_command_rename(args: list[str], runner: CliRunner, name: str):
    args_orig = args.copy()

    # tests the /rename command
    name += "-rename"
    args.append(f"{CMDFIX}rename {name}")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0

    # test with "auto" name
    args = args_orig.copy()
    args.append(f"{CMDFIX}rename auto")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0


@pytest.mark.slow
def test_fileblock(args: list[str], runner: CliRunner):
    args_orig = args.copy()

    # tests saving with a ```filename.txt block
    args.append(f"{CMDFIX}impersonate ```hello.py\nprint('hello')\n```")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0

    # read the file
    with open("hello.py") as f:
        content = f.read()
    assert content == "print('hello')\n"

    # test append
    args = args_orig.copy()
    args.append(f"{CMDFIX}impersonate ```append hello.py\nprint('world')\n```")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0

    # read the file
    with open("hello.py") as f:
        content = f.read()
    assert content == "print('hello')\nprint('world')\n"

    # test write file to directory that doesn't exist
    args = args_orig.copy()
    args.append(f"{CMDFIX}impersonate ```hello/hello.py\nprint('hello')\n```")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0

    # test patch on file in directory
    args = args_orig.copy()
    args.append(
        f"{CMDFIX}impersonate ```patch hello/hello.py\n<<<<<<< ORIGINAL\nprint('hello')\n=======\nprint('hello world')\n>>>>>>> UPDATED\n```"
    )
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0

    # read the file
    with open("hello/hello.py") as f:
        content = f.read()
    assert content == "print('hello world')\n"


def test_shell(args: list[str], runner: CliRunner):
    args.append(f"{CMDFIX}shell echo 'yes'")
    result = runner.invoke(gptme.cli.main, args)
    output = result.output.split("System")[-1]
    # check for two 'yes' in output (both command and stdout)
    assert output.count("yes") == 2, result.output
    assert result.exit_code == 0


def test_python(args: list[str], runner: CliRunner):
    args.append(f"{CMDFIX}python print('yes')")
    result = runner.invoke(gptme.cli.main, args)
    assert "yes\n" in result.output
    assert result.exit_code == 0


def test_python_error(args: list[str], runner: CliRunner):
    args.append(f"{CMDFIX}python raise Exception('yes')")
    result = runner.invoke(gptme.cli.main, args)
    assert "Exception: yes" in result.output
    assert result.exit_code == 0


_block_sh = """function test() {
    echo "start"  # start

    echo "after empty line"
}
"""
_block_py = """def test():
    print("start")  # start

    print("after empty line")
"""
blocks = {"python": _block_py, "sh": _block_sh}


@pytest.mark.slow
@pytest.mark.parametrize("lang", ["python", "sh"])
def test_block(args: list[str], lang: str, runner: CliRunner):
    # tests that shell codeblocks are formatted correctly such that whitespace and newlines are preserved
    code = blocks[lang]
    code = f"""```{lang}
{code.strip()}
```"""
    assert "'" not in code

    args.append(f"{CMDFIX}impersonate {code}")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    output = result.output
    print(f"output: {output}\nEND")
    # check everything after the second '# start'
    # (get not the user impersonation command, but the assistant message and everything after)
    output = output.split("# start", 2)[-1]
    printcmd = "print" if lang == "python" else "echo"
    assert f"\n\n    {printcmd}" in output
    assert result.exit_code == 0


# TODO: these could be fast if we had a cache
@pytest.mark.slow
def test_generate_primes(args: list[str], runner: CliRunner):
    args.append("print the first 10 prime numbers")
    result = runner.invoke(gptme.cli.main, args)
    # check that the 9th and 10th prime is present
    assert "23" in result.output
    assert "29" in result.output
    assert result.exit_code == 0


def test_stdin(args: list[str], runner: CliRunner):
    args.append(f"{CMDFIX}exit")
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args, input="hello")
    assert "```stdin\nhello\n```" in result.output
    assert result.exit_code == 0


# TODO: move elsewhere
@pytest.mark.slow
def test_tmux(args: list[str], runner: CliRunner):
    """
    $ gptme '/impersonate lets find out the current load
    ```tmux
    new_session top
    ```'
    """
    args.append(
        f"{CMDFIX}impersonate lets find out the current load\n```tmux\nnew_session top\n```"
    )
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    assert "%CPU" in result.output
    assert result.exit_code == 0


# TODO: move elsewhere
@pytest.mark.slow
@pytest.mark.flaky(retries=2, delay=5)
def test_subagent(args: list[str], runner: CliRunner):
    # f14: 377
    # f15: 610
    # f16: 987
    args.append(
        "test the subagent tool by computing `fib(15)` with it, where `fib(1) = 1` and `fib(2) = 1`"
    )
    print(f"running: gptme {' '.join(args)}")
    result = runner.invoke(gptme.cli.main, args)
    print(result.output)

    # apparently this is not obviously 610
    accepteds = ["377", "610"]
    assert any([accepted in result.output for accepted in accepteds])
    assert any(
        [
            accepted in "```".join(result.output.split("```")[-2:])
            for accepted in accepteds
        ]
    )


@pytest.mark.slow
@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)
def test_url(args: list[str], runner: CliRunner):
    args.append("Who is the CEO of https://superuserlabs.org?")
    result = runner.invoke(gptme.cli.main, args)
    assert "Erik Bjäreholt" in result.output
    assert result.exit_code == 0


def test_version(args: list[str], runner: CliRunner):
    args.append("--version")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0
    assert "gptme" in result.output


@pytest.mark.slow
def test_vision(args: list[str], runner: CliRunner):
    args.append(f"can you see the image at {logo}? answer with yes or no")
    result = runner.invoke(gptme.cli.main, args)
    assert result.exit_code == 0
    assert "yes" in result.output
    assert "yes" in result.output
