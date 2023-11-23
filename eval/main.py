"""
Evals for code generation tools.
"""
import inspect
import os
import random
import shlex
import subprocess
import tempfile
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, TypedDict

from gptme.cli import chat as gptme_chat
from gptme.message import Message

Files = Dict[str, str]


class ExecutionEnv:
    @abstractmethod
    def generate(self, prompt: str):
        """
        Generates code in the execution environment.
        """
        raise NotImplementedError

    @abstractmethod
    def run(self, command: str):
        """
        Runs a command in the execution environment.
        """
        raise NotImplementedError

    @abstractmethod
    def upload(self, files: Files):
        """
        Uploads files to the execution environment.
        """
        raise NotImplementedError

    @abstractmethod
    def download(self) -> Files:
        """
        Downloads files from the execution environment.
        """
        raise NotImplementedError


@dataclass
class ResultContext:
    """
    Context for the result of a test.
    """

    files: Files
    stdout: str
    stderr: str


class ExecTest(TypedDict):
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]


example_tests: dict[str, ExecTest] = {
    "test1": {
        "files": {"main.py": "print('Hello, world!')"},
        "run": "python main.py",
        "prompt": "Change the code in main.py to print 'Hello, human!'",
        "expect": {
            "correct output": lambda ctx: ctx.stdout == "Hello, human!\n",
            "correct file": lambda ctx: ctx.files["main.py"]
            == "print('Hello, human!')\n",
        },
    },
}


class GPTMeExecEnv(ExecutionEnv):
    def __init__(self):
        self.working_dir = Path(tempfile.mkdtemp(prefix="gptme-evals-"))

    def generate(self, prompt: str):
        # change current working dir
        os.chdir(self.working_dir)

        # don't exit on sys.exit()
        try:
            gptme_chat(
                [Message("user", prompt)],
                [],
                f"gptme-evals-{random.randint(0, 100000)}",
                "openai",
                "gpt-4",
                no_confirm=True,
                interactive=False,
            )
        except SystemExit:
            pass

    def run(self, command):
        # while running, also print the stdout and stderr
        p = subprocess.Popen(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.working_dir,
        )
        print("Running command:", command)
        stdout_full, stderr_full = "", ""
        while p.poll() is None:
            stdout = p.stdout.readline().decode("utf-8")
            stderr = p.stderr.readline().decode("utf-8")
            if stdout:
                print(stdout, end="")
                stdout_full += stdout
            if stderr:
                print(stderr, end="")
                stderr_full += stderr
        return stdout_full, stderr_full

    def upload(self, files: Files):
        for name, content in files.items():
            path = self.working_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)

    def download(self) -> Files:
        files = {}
        for path in self.working_dir.glob("**/*"):
            if path.is_file():
                with open(path, "r") as f:
                    files[str(path.relative_to(self.working_dir))] = f.read()
        return files


def execute(test: ExecTest):
    """
    Executes the code.
    """
    env = GPTMeExecEnv()
    env.upload(test["files"])
    env.generate(test["prompt"])
    stdout, stderr = env.run(test["run"])
    files = env.download()
    ctx = ResultContext(files, stdout, stderr)
    for name, case in test["expect"].items():
        code = inspect.getsource(case).strip()
        print(f"Case {name}")
        print(f" - code: {code}")
        print(" - result: ", end="")
        if case(ctx):
            print("passed!")
        else:
            print("failed!")


if __name__ == "__main__":
    for name, test in example_tests.items():
        print(f"Running test {name}...")
        execute(test)
