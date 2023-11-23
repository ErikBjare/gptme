"""
Evals for code generation tools.
"""
import inspect
import os
import random
import shlex
import subprocess
import sys
import tempfile
import time
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, TypedDict

from gptme.cli import chat as gptme_chat
from gptme.message import Message
from gptme.prompts import get_prompt

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


class CaseResult(TypedDict):
    name: str
    passed: bool


class TestResult(TypedDict):
    name: str
    results: list[CaseResult]
    timings: dict[str, float]


class ExecTest(TypedDict):
    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]


tests: list[ExecTest] = [
    {
        "name": "hello",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Change the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": lambda ctx: ctx.stdout == "Hello, human!\n",
            "correct file": lambda ctx: ctx.files["hello.py"]
            == "print('Hello, human!')\n",
        },
    },
    {
        "name": "hello-patch",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Patch the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": lambda ctx: ctx.stdout == "Hello, human!\n",
            "correct file": lambda ctx: ctx.files["hello.py"]
            == "print('Hello, human!')\n",
        },
    },
    {
        "name": "prime100",
        "files": {},
        "run": "python prime.py",
        "prompt": "write a script prime.py that computes and prints the 100th prime number",
        "expect": {
            "correct output": lambda ctx: "541" in ctx.stdout.split(),
        },
    },
]

tests_map = {test["name"]: test for test in tests}


class GPTMeExecEnv(ExecutionEnv):
    def __init__(self):
        self.working_dir = Path(tempfile.mkdtemp(prefix="gptme-evals-"))
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt: str):
        # change current working dir
        os.chdir(self.working_dir)

        print("--- Start of generation ---")
        # don't exit on sys.exit()
        try:
            gptme_chat(
                [Message("user", prompt)],
                [get_prompt()],
                f"gptme-evals-{random.randint(0, 100000)}",
                "openai",
                "gpt-4-1106-preview",
                no_confirm=True,
                interactive=False,
            )
        except SystemExit:
            pass
        print("--- Finished generation ---")

    def run(self, command):
        start = time.time()
        # while running, also print the stdout and stderr
        p = subprocess.Popen(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.working_dir,
            text=True,
        )
        print("Running command:", command)
        stdout_full, stderr_full = "", ""
        while p.poll() is None:
            assert p.stdout is not None
            assert p.stderr is not None
            stdout = p.stdout.readline()
            stderr = p.stderr.readline()
            if stdout:
                print(stdout, end="")
                stdout_full += stdout
            if stderr:
                print(stderr, end="")
                stderr_full += stderr
            if time.time() - start > 30:
                print("Timeout!")
                p.kill()
                break
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


def execute(test: ExecTest) -> TestResult:
    """
    Executes the code.
    """
    print(f"Running test {test['name']} with prompt: {test['prompt']}")
    env = GPTMeExecEnv()

    # upload files
    env.upload(test["files"])

    # generate code
    gen_start = time.time()
    env.generate(test["prompt"])
    gen_duration = time.time() - gen_start

    # check and collect results
    run_start = time.time()
    stdout, stderr = env.run(test["run"])
    time.time() - run_start

    files = env.download()

    ctx = ResultContext(files, stdout, stderr)
    results: list[CaseResult] = []
    for name, case in test["expect"].items():
        code = inspect.getsource(case).strip()
        print(f"Case {name}")
        print(f" - code: {code}")
        print(" - result: ", end="")
        passed = case(ctx)
        results.append({"name": name, "passed": True})
        if passed:
            print("passed!")
        else:
            print("failed!")

    return {
        "name": test["name"],
        "results": results,
        "timings": {"gen": gen_duration, "run": 0},
    }


def main():
    test_name = sys.argv[1] if len(sys.argv) > 1 else None
    results = []
    if test_name:
        result = execute(tests_map[test_name])
        results.append(result)
    else:
        for test in tests:
            result = execute(test)
            results.append(result)

    print("--- Finished ---\n")
    print(f"Completed {len(results)} tests:")
    for result in results:
        print(
            f"- {result['name']} in {result['timings']['gen']:.2f}s (gen) {result['timings']['run']:.2f}s (run)"
        )
        for case in result["results"]:
            print(f"  - {case['name']}: {'passed' if case['passed'] else 'failed'}")


if __name__ == "__main__":
    main()
