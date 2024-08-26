import glob
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.container import Container

logger = logging.getLogger(__name__)


@dataclass
class Config:
    prompt: dict
    env: dict

    def get_env(self, key: str, default: str | None = None) -> str | None:
        """Gets an enviromnent variable, checks the config file if it's not set in the environment."""
        try:
            return self.get_env_required(key)
        except KeyError:
            return default

    def get_env_required(self, key: str) -> str:
        """Gets an enviromnent variable, checks the config file if it's not set in the environment."""
        if key in os.environ:
            return os.environ[key]
        elif key in self.env:
            return self.env[key]
        raise KeyError(
            f"Environment variable {key} not set in env or config, see README."
        )

    def dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "env": self.env,
        }


@dataclass
class ProjectConfig:
    """Project-level configuration, such as which files to include in the context by default."""

    files: list[str] = field(default_factory=list)


ABOUT_ACTIVITYWATCH = """ActivityWatch is a free and open-source automated time-tracker that helps you track how you spend your time on your devices."""
ABOUT_GPTME = "gptme is a CLI to interact with large language models in a Chat-style interface, enabling the assistant to execute commands and code on the local machine, letting them assist in all kinds of development and terminal-based work."


default_config = Config(
    prompt={
        "about_user": "I am a curious human programmer.",
        "response_preference": "Basic concepts don't need to be explained.",
        "project": {
            "activitywatch": ABOUT_ACTIVITYWATCH,
            "gptme": ABOUT_GPTME,
        },
    },
    env={
        # toml doesn't support None
        # "OPENAI_API_KEY": None
    },
)

# Define the path to the config file
config_path = os.path.expanduser("~/.config/gptme/config.toml")

# Global variable to store the config
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config() -> Config:
    # TODO: validate
    config = _load_config()
    return Config(**config)  # type: ignore


def _load_config() -> tomlkit.TOMLDocument:
    # Check if the config file exists
    if not os.path.exists(config_path):
        # If not, create it and write some default settings
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as config_file:
            tomlkit.dump(default_config.dict(), config_file)
        print(f"Created config file at {config_path}")

    # Now you can read the settings from the config file like this:
    with open(config_path) as config_file:
        doc = tomlkit.load(config_file)
    return doc


def set_config_value(key: str, value: str) -> None:
    doc: TOMLDocument | Container = _load_config()

    # Set the value
    keypath = key.split(".")
    d = doc
    for key in keypath[:-1]:
        d = d.get(key, {})
    d[keypath[-1]] = value

    # Write the config
    with open(config_path, "w") as config_file:
        tomlkit.dump(doc, config_file)

    # Reload config
    global _config
    _config = load_config()


def get_workspace_prompt(workspace: str) -> str:
    project_config_paths = [
        p
        for p in (
            Path(workspace) / "gptme.toml",
            Path(workspace) / ".github" / "gptme.toml",
        )
        if p.exists()
    ]
    if project_config_paths:
        project_config_path = project_config_paths[0]
        logger.info(f"Using project configuration at {project_config_path}")
        # load project config
        with open(project_config_path) as f:
            project_config = tomlkit.load(f)
            project = ProjectConfig(**project_config)  # type: ignore
            # expand with glob
            files = [p for file in project.files for p in glob.glob(file)]
            for file in files:
                if not Path(file).exists():
                    logger.error(
                        f"File {file} specified in project config does not exist"
                    )
                    exit(1)
        return "\n\nSelected project files, read more with cat:\n" + "\n\n".join(
            [f"```{Path(file).name}\n{Path(file).read_text()}\n```" for file in files]
        )
    return ""


if __name__ == "__main__":
    config = get_config()
    print(config)
