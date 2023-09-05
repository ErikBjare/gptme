import os
import select
import subprocess


class ShellSession:
    def __init__(self):
        self.process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered
            universal_newlines=True,
        )
        self.stdout_fd = self.process.stdout.fileno()
        self.stderr_fd = self.process.stderr.fileno()
        self.delimiter = "END_OF_COMMAND_OUTPUT"

    def run_command(self, command):
        assert self.process.stdin

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
