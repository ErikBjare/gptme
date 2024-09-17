import os
import subprocess
import time
from abc import abstractmethod

from .filestore import Files, FileStore


class ExecutionEnv:
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


class SimpleExecutionEnv(FileStore, ExecutionEnv):
    """
    A simple execution environment that runs the code in the files.

    upload() and download() are inherited from FileStore.
    """

    def run(self, command, silent=True) -> tuple[str, str, int]:
        os.chdir(self.working_dir)

        start = time.time()
        if not silent:
            print("\n--- Start of run ---")
        # while running, also print the stdout and stderr
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.working_dir,
            text=True,
            shell=True,
        )
        if not silent:
            print("$", command)
        stdout_full, stderr_full = "", ""
        while p.poll() is None or p.stdout or p.stderr:
            assert p.stdout is not None
            assert p.stderr is not None
            stdout = p.stdout.readline()
            stderr = p.stderr.readline()
            if stdout:
                if not silent:
                    print(stdout, end="")
                stdout_full += stdout
            if stderr:
                if not silent:
                    print(stderr, end="")
                stderr_full += stderr
            if not stdout and not stderr and p.poll() is not None:
                break
            if time.time() - start > 30:
                if not silent:
                    print("Timeout!")
                p.kill()
                break
        if not silent:
            print("--- Finished run ---\n")
        return stdout_full, stderr_full, p.returncode
