#!/bin/bash
# A simple script that:
# - mounts your gptme config into the docker container
# - mounts the ./eval_results folder
#    - (which should be a symlink to path ./eval-results/eval_results
#       where ./eval-results is a worktree of the git branch of the same name)
# - runs the gptme-eval command
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GIT_ROOT_DIR=$SCRIPT_DIR/..
docker run \
    -v ~/.config/gptme:/home/appuser/.config/gptme \
    -v $GIT_ROOT_DIR/eval_results:/app/eval_results \
    gptme-eval \
    --timeout 60 \
    $@
