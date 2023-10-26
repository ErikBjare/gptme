#!/bin/bash

set -e
set -x

# set pwd to the output directory under this script
cd "$(dirname "$0")"
mkdir -p output
cd output

# set this to indicate tests are run (non-interactive)
export PYTEST_CURRENT_TEST=1

# test stdin and cli-provided prompt
echo "The project mascot is a flying pig" | gptme "What is the project mascot?"

# test python command
gptme "/python print('hello world')"

# test shell command
gptme "/shell echo 'hello world'"

# interactive matplotlib
gptme 'plot an x^2 graph'

# matplotlib to file
gptme 'plot up to the 3rd degree taylor expansion of sin(x), save to sin.png'

# interactive curses
gptme 'write a snake game with curses'
