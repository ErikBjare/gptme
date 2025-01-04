import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.container import Container

from .dirs import get_logs_dir

from .util import console, get_git_repo_root, path_with_tilde

logger = logging.getLogger(__name__)


@dataclass
class Config:
    prompt: dict
    global_env: dict

    def has_project_config(self):
        return bool(os.environ.get("SESSION_NAME")) and self.get_project_config()

    @property
    def env(self):
        if self.has_project_config():
            project_config = self.get_project_config()
            assert project_config is not None
            return {**self.global_env, **project_config.project_env}
        else:
            return self.global_env

    def __getattribute__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            if self.has_project_config():
                return getattr(self.get_project_config(), name)
            else:
                raise

    def get_env(self, key: str, default: str | None = None) -> str | None:
        """Gets an environment variable, checks the config file if it's not set in the environment."""
        return os.environ.get(key) or self.env.get(key) or default

    def get_env_required(self, key: str) -> str:
        """Gets an environment variable, checks the config file if it's not set in the environment."""
        if val := os.environ.get(key) or self.env.get(key):
            return val
        raise KeyError(  # pragma: no cover
            f"Environment variable {key} not set in env or config, see README."
        )

    def get_log_dir(self, force_name: str | None = None) -> Path:
        name = force_name or os.environ.get("SESSION_NAME")
        assert (
            name
        ), "SESSION_NAME env var must be initialized before calling get_log_dir()"

        logdir = get_logs_dir() / name
        logdir.mkdir(parents=True, exist_ok=True)

        return logdir

    def get_workspace_dir(self) -> Path:
        logdir = self.get_log_dir()

        log_workspace = logdir / "workspace"

        workspace_from_env = os.environ.get("WORKSPACE")

        # If the log workspace exists, we have already created it previously. We can
        # directly use it.
        if log_workspace.exists():
            resolved_workspace = log_workspace.resolve()
            assert (
                not workspace_from_env
                or (workspace_from_env == str(log_workspace))
                or (workspace_from_env == str(resolved_workspace))
                or (workspace_from_env == "@log")
            ), f"Workspace already exists in {log_workspace}, wont override."
            return resolved_workspace

        # Otherwise we have three cases
        if not workspace_from_env:  # We use the default workspace
            if repo_root := get_git_repo_root():
                workspace = Path(repo_root)
            else:
                workspace = Path.cwd()
        elif (
            workspace_from_env == "@log"
        ):  # The user wants the workspace in the log directory
            log_workspace.mkdir(parents=True, exist_ok=True)
            workspace = log_workspace
        else:  # The workspace is forced from env or cli option
            workspace = Path(workspace_from_env)
            assert (
                workspace.exists()
            ), f"Workspace path {workspace_from_env} does not exist"

        if workspace_from_env != "@log":
            log_workspace.symlink_to(workspace, target_is_directory=True)

        return workspace

    def get_project_config(self) -> "ProjectConfig | None":
        return _get_project_config(self.get_workspace_dir())

    def to_dict(self) -> dict:
        if self.has_project_config():
            project_config = self.get_project_config()
            assert project_config is not None
            return {
                "prompt": self.prompt,
                "env": self.env,
                **project_config.to_dict(),
            }
        else:
            return {
                "prompt": self.prompt,
                "env": self.env,
            }


@dataclass
class ProjectConfig:
    """Project-level configuration, such as which files to include in the context by default."""

    project_prompt: str | None = None
    project_env: dict = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    rag: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_prompt": self.project_prompt,
            "files": self.files,
            "rag": self.rag,
        }


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
    global_env={
        # toml doesn't support None
        # "OPENAI_API_KEY": None
    },
)

# Define the path to the config file
config_path = os.path.expanduser("~/.config/gptme/config.toml")

# Global variable to store the config
_config: Config | None = None


def get_config(force_load=False) -> Config:
    global _config
    if _config is None or force_load:
        _config = _load_config()
    return _config


def _load_config() -> Config:
    config = _load_config_doc()
    assert "prompt" in config, "prompt key missing in config"
    assert "env" in config, "env key missing in config"
    prompt = config.pop("prompt")
    env = config.pop("env")
    if config:
        logger.warning(f"Unknown keys in config: {config.keys()}")
    return Config(prompt=prompt, global_env=env)


def _load_config_doc() -> tomlkit.TOMLDocument:
    # Check if the config file exists
    if not os.path.exists(config_path):
        # If not, create it and write some default settings
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        toml = tomlkit.dumps(default_config.to_dict())
        with open(config_path, "w") as config_file:
            config_file.write(toml)
        console.log(f"Created config file at {config_path}")
        doc = tomlkit.loads(toml)
        return doc
    else:
        with open(config_path) as config_file:
            doc = tomlkit.load(config_file)
        return doc


def set_config_value(key: str, value: str) -> None:  # pragma: no cover
    doc: TOMLDocument | Container = _load_config_doc()

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
    _config = _load_config()


@lru_cache
def _get_project_config(workspace: Path) -> ProjectConfig | None:
    project_config_paths = [
        p
        for p in (
            workspace / "gptme.toml",
            workspace / ".github" / "gptme.toml",
        )
        if p.exists()
    ]
    if project_config_paths:
        project_config_path = project_config_paths[0]
        console.log(
            f"Using project configuration at {path_with_tilde(project_config_path)}"
        )
        # load project config
        with open(project_config_path) as f:
            project_config = tomlkit.load(f)

        prompt = project_config.pop("prompt", None)
        env = project_config.pop("env", {})
        return ProjectConfig(project_prompt=prompt, project_env=env, **project_config)  # type: ignore
    return None


if __name__ == "__main__":
    config = get_config()
    print(config)
