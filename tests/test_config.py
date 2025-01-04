import os
from unittest.mock import patch

import pytest
from gptme.cli import get_name
from gptme.config import get_config

CONFIG_TEST = """
unknown_key = "test"

[prompt]
about_user = "about"
response_preference = "pref"

[prompt.project]
prj1 = "Some text"
prj2 = "Another text"

[env]
OPEN_API_KEY= "<key>"
MODEL = "openai/gpt-4o-mini"
"""


def test_global_config(tmp_path):
    config_file = tmp_path / "config.toml"

    config_file.write_text(CONFIG_TEST)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    os.chdir(project_dir)

    with patch("gptme.config.config_path", str(config_file)):
        config = get_config(True)

    assert config.env == {"MODEL": "openai/gpt-4o-mini", "OPEN_API_KEY": "<key>"}
    with pytest.raises(AttributeError):
        config.rag

    assert not config.has_project_config()
    assert config.to_dict() == {
        "prompt": {
            "about_user": "about",
            "response_preference": "pref",
            "project": {"prj1": "Some text", "prj2": "Another text"},
        },
        "env": {"OPEN_API_KEY": "<key>", "MODEL": "openai/gpt-4o-mini"},
    }


def test_global_config_missing(tmp_path):
    config_file = tmp_path / "config.toml"

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    os.chdir(project_dir)

    with patch("gptme.config.config_path", str(config_file)):
        config = get_config(True)

    # We should have the default config
    assert config.to_dict()["env"] == {}
    assert (
        config.to_dict()["prompt"]["about_user"] == "I am a curious human programmer."
    )


PROJECT_CONFIG_TEST = """
prompt = "Project prompt"
files = ["file.txt"]

[rag]
enabled = true

[env]
OPEN_API_KEY= "<key_from_project>"
"""


def test_project_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(CONFIG_TEST)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    os.chdir(project_dir)

    project_config_file = project_dir / "gptme.toml"
    project_config_file.write_text(PROJECT_CONFIG_TEST)

    os.environ["SESSION_NAME"] = get_name("random")

    with patch("gptme.config.config_path", str(config_file)):
        config = get_config(True)

    assert config.has_project_config()
    assert config.env == {
        "MODEL": "openai/gpt-4o-mini",
        "OPEN_API_KEY": "<key_from_project>",
    }
    assert config.rag == {"enabled": True}
    assert config.to_dict() == {
        "prompt": {
            "about_user": "about",
            "response_preference": "pref",
            "project": {"prj1": "Some text", "prj2": "Another text"},
        },
        "env": {
            "OPEN_API_KEY": "<key_from_project>",  # Overridden from project
            "MODEL": "openai/gpt-4o-mini",
        },
        "project_prompt": "Project prompt",
        "files": ["file.txt"],
        "rag": {"enabled": True},
    }


def test_project_config_with_user_defined_workspace(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(CONFIG_TEST)

    os.chdir(tmp_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    project_config_file = project_dir / "gptme.toml"
    project_config_file.write_text(PROJECT_CONFIG_TEST)

    os.environ["SESSION_NAME"] = get_name("random")
    os.environ["WORKSPACE"] = str(project_dir)

    with patch("gptme.config.config_path", str(config_file)):
        config = get_config(True)

    assert config.has_project_config()
    assert config.to_dict() == {
        "prompt": {
            "about_user": "about",
            "response_preference": "pref",
            "project": {"prj1": "Some text", "prj2": "Another text"},
        },
        "env": {
            "OPEN_API_KEY": "<key_from_project>",  # Overridden from project
            "MODEL": "openai/gpt-4o-mini",
        },
        "project_prompt": "Project prompt",
        "files": ["file.txt"],
        "rag": {"enabled": True},
    }


def test_project_config_using_logdir(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(CONFIG_TEST)

    os.chdir(tmp_path)

    session_name = get_name("random")

    # Force log dir in the tmp directory
    logsdir = tmp_path / "logs"
    os.environ["GPTME_LOGS_HOME"] = str(logsdir)

    logdir = logsdir / session_name
    workspace_logdir = logdir / "workspace"

    os.environ["SESSION_NAME"] = session_name
    os.environ["WORKSPACE"] = "@log"

    with patch("gptme.config.config_path", str(config_file)):
        config = get_config(True)

    assert config.env
    assert workspace_logdir.exists()
    assert not config.has_project_config()
