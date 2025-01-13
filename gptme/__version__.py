import importlib.metadata
import os.path
import subprocess


def get_git_version(package_dir):
    """Get version information from git."""
    try:
        # Run git commands
        def git_cmd(cmd):
            return subprocess.check_output(cmd, cwd=package_dir, text=True).strip()

        # Check if we're in a git repo
        if (
            subprocess.call(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=package_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        ):
            # List all version tags and get the latest one
            tags = git_cmd(["git", "tag", "--list", "v*", "--sort=-v:refname"])
            if tags:
                latest_tag = tags.split("\n")[0]  # Get first tag (latest due to sort)
                version = latest_tag.lstrip("v")  # Remove 'v' prefix

                # Get commit hash
                commit_hash = git_cmd(["git", "rev-parse", "--short", "HEAD"])

                # Check if working tree is dirty
                is_dirty = bool(git_cmd(["git", "status", "--porcelain"]))

                version += f"+{commit_hash}"
                if is_dirty:
                    version += ".dirty"
                return version
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


try:
    __version__ = importlib.metadata.version("gptme")
    is_editable = isinstance(
        importlib.metadata.distribution("gptme"), importlib.metadata.PathDistribution
    )
    if is_editable:
        # Get the directory containing the package
        package_dir = os.path.dirname(os.path.abspath(__file__))
        git_version = get_git_version(package_dir)
        if git_version:
            __version__ = git_version
        else:
            __version__ += "+unknown"
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0 (unknown)"

if __name__ == "__main__":
    print(__version__)
