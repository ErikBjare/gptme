import atexit
import os
import re
import select
import shlex
import subprocess
from typing import Generator

from ..message import Message
from ..util import ask_execute, print_preview


class ShellSession:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered
            universal_newlines=True,
        )
        self.stdout_fd = self.process.stdout.fileno()  # type: ignore
        self.stderr_fd = self.process.stderr.fileno()  # type: ignore
        self.delimiter = "END_OF_COMMAND_OUTPUT"

    def run_command(self, command: str | list[str]) -> tuple[int | None, str, str]:
        assert self.process.stdin
        if isinstance(command, list):
            command = " ".join(shlex.quote(arg) for arg in command)

        full_command = f"{command}; echo ReturnCode:$?; echo {self.delimiter}"
        self.process.stdin.write(full_command + "\n")
        self.process.stdin.flush()

        stdout = []
        stderr = []
        return_code = None
        read_delimiter = False

        while True:
            rlist, _, _ = select.select([self.stdout_fd, self.stderr_fd], [], [])
            for fd in rlist:
                if fd == self.stdout_fd:
                    line = os.read(fd, 4096).decode("utf-8")
                    if "ReturnCode:" in line:
                        return_code_str = (
                            line.split("ReturnCode:")[1].split("\n")[0].strip()
                        )
                        return_code = int(return_code_str)
                    if self.delimiter in line:
                        read_delimiter = True
                        line = line.replace(self.delimiter, "")
                    if line:
                        stdout.append(line)
                elif fd == self.stderr_fd:
                    line = os.read(fd, 4096).decode("utf-8")
                    if line:
                        stderr.append(line)
            if read_delimiter:
                break
        return (
            return_code,
            "".join(stdout).replace(f"ReturnCode:{return_code}", "").strip(),
            "".join(stderr).strip(),
        )

    def close(self):
        assert self.process.stdin
        self.process.stdin.close()
        self.process.terminate()
        self.process.wait(timeout=0.2)
        self.process.kill()


_shell = None


def get_shell() -> ShellSession:
    global _shell
    if _shell is None:
        # init shell
        _shell = ShellSession()

        # close on exit
        atexit.register(_shell.close)
    return _shell


def execute_shell(cmd: str, ask=True) -> Generator[Message, None, None]:
    """Executes a shell command and returns the output."""
    shell = get_shell()

    cmd = cmd.strip()
    if cmd.startswith("$ "):
        cmd = cmd[len("$ ") :]
    if ask:
        print_preview(f"$ {cmd}", "bash")
        confirm = ask_execute()
        print()

    if not ask or confirm:
        returncode, stdout, stderr = shell.run_command(cmd)
        stdout = _shorten_stdout(stdout.strip())
        stderr = _shorten_stdout(stderr.strip())

        msg = f"Ran command:\n```bash\n{cmd}\n```\n\n"
        if stdout:
            msg += f"stdout:\n```\n{stdout}\n```\n\n"
        if stderr:
            msg += f"stderr:\n```\n{stderr}\n```\n\n"
        if not stdout and not stderr:
            msg += "No output\n"
        msg += f"Return code: {returncode}"

        yield Message("system", msg)


def _shorten_stdout(stdout: str) -> str:
    """Shortens stdout to 1000 tokens."""
    lines = stdout.split("\n")

    # strip iso8601 timestamps
    lines = [
        re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.]\d{3,9}Z?", "", line)
        for line in lines
    ]
    # strip dates like "2017-08-02 08:48:43 +0000 UTC"
    lines = [
        re.sub(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}( [+]\d{4})?( UTC)?", "", line
        ).strip()
        for line in lines
    ]

    # strip common prefixes, useful for things like `gh runs view`
    if len(lines) > 5:
        prefix = os.path.commonprefix(lines)
        if prefix:
            lines = [line[len(prefix) :] for line in lines]

    pre_lines = 30
    post_lines = 30
    if len(lines) > pre_lines + post_lines:
        lines = (
            lines[:pre_lines]
            + [f"... ({len(lines) - pre_lines - post_lines} truncated) ..."]
            + lines[-post_lines:]
        )

    return "\n".join(lines)
