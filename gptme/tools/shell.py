import atexit
import os
import re
import select
import subprocess
import sys
from collections.abc import Generator
from typing import List

import bashlex

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

        # close on exit
        atexit.register(self.close)

        # set GIT_PAGER=cat
        self.run("export GIT_PAGER=cat")

    def run(self, code: str, output=True) -> tuple[int | None, str, str]:
        """Runs a command in the shell and returns the output."""
        commands = split_commands(code)
        res_code: int | None = None
        res_stdout, res_stderr = "", ""
        for cmd in commands:
            res_cur = self._run(cmd, output=output)
            res_code = res_cur[0]
            res_stdout += res_cur[1]
            res_stderr += res_cur[2]
            if res_code != 0:
                return res_code, res_stdout, res_stderr
        return res_code, res_stdout, res_stderr

    def _run(self, command: str, output=True) -> tuple[int | None, str, str]:
        assert self.process.stdin

        # run the command
        full_command = f"{command}; echo ReturnCode:$? {self.delimiter}\n"
        self.process.stdin.write(full_command)
        self.process.stdin.flush()

        stdout = []
        stderr = []
        return_code = None
        read_delimiter = False

        while True:
            rlist, _, _ = select.select([self.stdout_fd, self.stderr_fd], [], [])
            for fd in rlist:
                assert fd in [self.stdout_fd, self.stderr_fd]
                # We use a higher value, because there is a bug which leads to spaces at the boundary
                # 2**12 = 4096
                # 2**16 = 65536
                data = os.read(fd, 2**16).decode("utf-8")
                for line in re.split(r"(\n)", data):
                    if "ReturnCode:" in line:
                        return_code_str = (
                            line.split("ReturnCode:")[1].split(" ")[0].strip()
                        )
                        return_code = int(return_code_str)
                    if self.delimiter in line:
                        read_delimiter = True
                        continue
                    if fd == self.stdout_fd:
                        stdout.append(line)
                        if output:
                            print(line, end="", file=sys.stdout)
                    elif fd == self.stderr_fd:
                        stderr.append(line)
                        if output:
                            print(line, end="", file=sys.stderr)
            if read_delimiter:
                break

        # if command is cd and successful, we need to change the directory
        if command.startswith("cd ") and return_code == 0:
            ex, pwd, _ = self._run("pwd", output=False)
            assert ex == 0
            os.chdir(pwd.strip())

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
    return _shell


# used in testing
def set_shell(shell: ShellSession) -> None:
    global _shell
    _shell = shell


def execute_shell(cmd: str, ask=True) -> Generator[Message, None, None]:
    """Executes a shell command and returns the output."""
    shell = get_shell()

    cmd = cmd.strip()
    if cmd.startswith("$ "):
        cmd = cmd[len("$ ") :]

    confirm = True
    if ask:
        print_preview(f"$ {cmd}", "bash")
        confirm = ask_execute()
        print()

    if not ask or confirm:
        returncode, stdout, stderr = shell.run(cmd)
        stdout = _shorten_stdout(stdout.strip())
        stderr = _shorten_stdout(stderr.strip())

        msg = _format_block_smart("Ran command", cmd, lang="bash") + "\n\n"
        if stdout:
            msg += _format_block_smart("stdout", stdout) + "\n\n"
        if stderr:
            msg += _format_block_smart("stderr", stderr) + "\n\n"
        if not stdout and not stderr:
            msg += "No output\n"
        if returncode:
            msg += f"Return code: {returncode}"

        yield Message("system", msg)


def _format_block_smart(header: str, cmd: str, lang="") -> str:
    # prints block as a single line if it fits, otherwise as a code block
    if len(cmd.split("\n")) == 1:
        return f"{header}: `{cmd}`"
    else:
        return f"{header}:\n```{lang}\n{cmd}\n```"


def _shorten_stdout(stdout: str, pre_lines=None, post_lines=None) -> str:
    """Shortens stdout to 1000 tokens."""
    lines = stdout.split("\n")

    # strip iso8601 timestamps
    lines = [
        re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.]\d{3,9}Z?", "", line)
        for line in lines
    ]
    # strip dates like "2017-08-02 08:48:43 +0000 UTC"
    lines = [
        re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}( [+]\d{4})?( UTC)?", "", line)
        for line in lines
    ]

    # strip common prefixes, useful for things like `gh runs view`
    if len(lines) >= 5:
        prefix = os.path.commonprefix([line.rstrip() for line in lines])
        if prefix:
            lines = [line[len(prefix) :] for line in lines]

    # check that if pre_lines is set, so is post_lines, and vice versa
    assert (pre_lines is None) == (post_lines is None)
    if (
        pre_lines is not None
        and post_lines is not None
        and len(lines) > pre_lines + post_lines
    ):
        lines = (
            lines[:pre_lines]
            + [f"... ({len(lines) - pre_lines - post_lines} truncated) ..."]
            + lines[-post_lines:]
        )

    return "\n".join(lines)


def split_commands(script: str) -> List[str]:
    parts = bashlex.parse(script)
    commands = []
    for part in parts:
        if part.kind == "command":
            command_parts = []
            for word in part.parts:
                start, end = word.pos
                command_parts.append(script[start:end])
            command = " ".join(command_parts)
            commands.append(command)
    return commands


if __name__ == "__main__":
    script = """
# This is a comment
ls -l
echo "Hello, World!"
echo "This is a \
multiline command"
"""

    commands = split_commands(script)
    for command in commands:
        print(command)
