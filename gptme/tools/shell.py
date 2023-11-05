import atexit
import os
import re
import select
import subprocess
from collections.abc import Generator

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
        self.run_command("export GIT_PAGER=cat")

    def run_command(self, command: str) -> tuple[int | None, str, str]:
        assert self.process.stdin

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
                for line in data.split("\n"):
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
                    elif fd == self.stderr_fd:
                        stderr.append(line)
            if read_delimiter:
                break
        return (
            return_code,
            "\n".join(stdout).replace(f"ReturnCode:{return_code}", "").strip(),
            "\n".join(stderr).strip(),
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
        returncode, stdout, stderr = shell.run_command(cmd)
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
