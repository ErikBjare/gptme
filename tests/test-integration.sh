#!/bin/bash

set -e
set -x

# set this to indicate tests are run (non-interactive)
export PYTEST_CURRENT_TEST=1

# test stdin and cli-provided prompt
echo "The project mascot is a flying pig" | gptme "What is the project mascot?"

# test python command
gptme ".python print('hello world')"

# test shell command
gptme ".shell echo 'hello world'"
