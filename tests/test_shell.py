import unittest

from gptme.tools import ShellSession


class TestShellSession(unittest.TestCase):
    def test_cd_command(self):
        # Initialize a shell session
        shell = ShellSession()

        # Run a cd command
        ret, out, err = shell.run_command("cd /tmp")
        self.assertEqual(err.strip(), "")  # Expecting no stderr
        self.assertEqual(ret, None)  # Process should still be running

        # Check the current directory
        ret, out, err = shell.run_command("pwd")
        self.assertEqual(err.strip(), "")  # Expecting no stderr
        self.assertEqual(out.strip(), "/tmp")  # Should be in /tmp now

        # Close the shell session
        shell.close()
