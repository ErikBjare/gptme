from ..message import Message
from ..tools.shell import get_shell


def _gen_context_msg() -> Message:
    shell = get_shell()
    msgstr = ""

    cmd = "pwd"
    ret, pwd, _ = shell.run_command(cmd)
    assert ret == 0
    msgstr += f"$ {cmd}\n{pwd.strip()}\n"

    cmd = "git status -s"
    ret, git, _ = shell.run_command(cmd)
    if ret == 0 and git:
        msgstr += f"$ {cmd}\n{git}\n"

    return Message("system", msgstr.strip(), hide=True)
