#!/bin/bash

set -e
set -x

# set pwd to the output directory under this script
cd "$(dirname "$0")"
mkdir -p output
cd output

# run interactive tests if not in CI (GITHUB_ACTIONS is set by github actions)
interactive=${GITHUB_ACTIONS:-1}

# set this to indicate tests are run (non-interactive)
export PYTEST_CURRENT_TEST=1

# test stdin and cli-provided prompt
echo "The project mascot is a flying pig" | gptme "What is the project mascot?"

# test load context from file
echo "The project mascot is a flying pig" > mascot.txt
gptme "What is the project mascot?" mascot.txt

# test python command
gptme "/python print('hello world')"

# test shell command
gptme "/shell echo 'hello world'"

# test write small game
gptme 'write a snake game with curses to snake.py'
# works!

# test implement game of life
gptme 'write an implementation of the game of life with curses to life.py'
# works? almost, needed to try-catch-pass an exception

# test implement wireworld
gptme 'write a implementation of wireworld with curses to wireworld.py'
# works? almost, needed to try-catch-pass an exception, fix color setup, and build a proper circuit

# test plot to file
gptme 'plot up to the 5rd degree taylor expansion of sin(x), save to sin.png'
# works!

# ask it to manipulate sin.png with imagemagick
gptme 'rotate sin.png 90 degrees clockwise with imagemagick'
# works!

# ask it to manipulate sin.png with PIL
gptme 'rotate sin.png 90 degrees clockwise with PIL'
# needs PIL to be installed

# write C code and apply patch
gptme 'write a hello world program in c to hello.c, then patch it to ask for your name and print it'
# works!

# write outline for a class that implements a linked list, then fill in the implementation
gptme 'write class that implements a linked list, then fill in the implementation with patch, then test it'
# works!

if [ "$interactive" = "1" ]; then
    # interactive matplotlib
    gptme 'plot an x^2 graph'
fi
