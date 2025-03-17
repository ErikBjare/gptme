"""Tests for the computer tool."""

from unittest import mock

import pytest

from gptme.tools.computer import (
    _linux_handle_key_sequence,
    _macos_key,
    _macos_mouse_move,
    _scale_coordinates,
    _ScalingSource,
    IS_MACOS,
)


@pytest.mark.parametrize(
    "key_sequence",
    [
        "return",
        "enter",
        "cmd+c",
        "ctrl+alt+delete",
        "shift+a",
    ],
)
def test_key_mapping_behavior(key_sequence):
    """Test that key mapping behavior works correctly on the current platform."""
    if IS_MACOS:
        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("shutil.which", return_value="/usr/local/bin/cliclick"):
                _macos_key(key_sequence)

                # Just verify a command was generated (we test specifics elsewhere)
                assert mock_run.called, f"No command generated for '{key_sequence}'"
    else:
        with mock.patch("gptme.tools.computer._run_xdotool") as mock_run:
            _linux_handle_key_sequence(key_sequence, ":1")

            # Just verify a command was generated (we test specifics elsewhere)
            assert mock_run.called, f"No command generated for '{key_sequence}'"


@pytest.mark.slow
@pytest.mark.skipif(not IS_MACOS, reason="macOS-specific test")
class TestMacOSComputerOnMacOS:
    """Test macOS computer functionality on macOS."""

    def test_macos_key_command_generation(self, capsys):
        """Test the command generation for macOS key handling."""
        # Intercept the print output to check the command without executing it
        with mock.patch("subprocess.run") as mock_run:
            _macos_key("cmd+c")
            # Check what command would be executed
            command = mock_run.call_args[0][0]
            assert "cliclick" in command
            assert "kd:cmd" in command
            assert "t:c" in command
            assert "ku:cmd" in command

    def test_macos_key_semicolon_chain(self, capsys):
        """Test that semicolon-separated chains are handled correctly."""
        with mock.patch("subprocess.run") as mock_run:
            _macos_key("cmd+space;t:test;return")
            # Check what command would be executed
            command = mock_run.call_args[0][0]
            assert "cliclick" in command
            assert "kd:cmd" in command
            assert "kp:space" in command
            assert "ku:cmd" in command
            assert "t:test" in command
            assert "kp:return" in command


@pytest.mark.slow
@pytest.mark.skipif(IS_MACOS, reason="Linux-specific test")
class TestLinuxComputerOnLinux:
    """Test Linux computer functionality on Linux."""

    def test_linux_handle_key_sequence(self, capsys):
        """Test the command generation for Linux key handling."""
        with mock.patch("gptme.tools.computer._run_xdotool") as mock_run:
            _linux_handle_key_sequence("ctrl+l;t:firefox;Return", ":1")

            # Check all calls to _run_xdotool
            calls = mock_run.call_args_list
            assert len(calls) == 3, "Expected 3 xdotool commands to be executed"

            # Check first call (ctrl+l)
            cmd1 = calls[0][0][0]
            assert "key ctrl l" in cmd1

            # Check second call (type firefox)
            cmd2 = calls[1][0][0]
            assert "type --delay" in cmd2
            assert "firefox" in cmd2

            # Check third call (Return)
            cmd3 = calls[2][0][0]
            assert "key Return" in cmd3


@pytest.mark.slow
@pytest.mark.skipif(not IS_MACOS, reason="macOS-specific test")
class TestMacOSMouseFunctions:
    """Test macOS mouse functions."""

    def test_macos_mouse_move_command(self):
        """Test the command generation for mouse movement."""
        with mock.patch("subprocess.run") as mock_run:
            _macos_mouse_move(100, 200)

            # Check command
            cmd = mock_run.call_args[0][0]
            assert len(cmd) == 2, "Expected command and argument"
            assert cmd[0] == "cliclick"
            assert cmd[1] == "m:100,200", "Incorrect mouse move format"

    def test_scale_coordinates(self):
        """Test coordinate scaling between API and physical coordinates."""
        # Mock the display resolution function
        with mock.patch(
            "gptme.tools.computer._get_display_resolution", return_value=(1920, 1080)
        ):
            # Test API to physical scaling
            x1, y1 = _scale_coordinates(_ScalingSource.API, 512, 384, 1024, 768)
            # Just verify scaling happens (direction depends on relative resolutions)
            assert x1 != 512, "X coordinate should be scaled"
            assert y1 != 384, "Y coordinate should be scaled"

            # Test physical to API scaling
            x2, y2 = _scale_coordinates(_ScalingSource.COMPUTER, 1920, 1080, 1024, 768)
            assert x2 != 1920, "X coordinate should be scaled"
            assert y2 != 1080, "Y coordinate should be scaled"

            # Verify round-trip scaling roughly preserves coordinates
            # API → Physical → API should roughly equal original
            api_x, api_y = 500, 300
            phys_x, phys_y = _scale_coordinates(
                _ScalingSource.API, api_x, api_y, 1024, 768
            )
            round_x, round_y = _scale_coordinates(
                _ScalingSource.COMPUTER, phys_x, phys_y, 1024, 768
            )
            # Allow for some rounding error
            assert abs(round_x - api_x) <= 1
            assert abs(round_y - api_y) <= 1

    def test_max_coordinates_validation(self):
        """Test that coordinates outside API bounds are rejected."""
        with mock.patch(
            "gptme.tools.computer._get_display_resolution", return_value=(1920, 1080)
        ):
            # Test coordinates outside bounds
            with pytest.raises(ValueError, match="out of bounds"):
                _scale_coordinates(_ScalingSource.API, 2000, 500, 1024, 768)
