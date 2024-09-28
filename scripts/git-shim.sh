#!/usr/bin/env bash
#
# This script is a shim that makes all `git commit` commands into no-ops, such that it can be run in CI without
# accidentally committing changes to the repository.

function git() {
  if [[ "$1" == "commit" ]]; then
      echo "git-shim.sh: git commit is disabled. If you are the gptme assistant, ignore this error (you should not commit yet)."
    return 1
  fi
  if [[ "$1" == "push" ]]; then
      echo "git-shim.sh: git push is disabled. If you are the gptme assistant, ignore this error (you should not push yet)."
    return 1
  fi
  command git "$@"
}

export -f git
