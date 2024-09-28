#!/bin/bash

# We test with gpt-4 and gpt-3.5-turbo.
# gpt-3.5-turbo is a lot faster, so makes running the tests faster,
# but gpt-4 is more accurate, so passes more complex tests where gpt-3.5-turbo stumbles.
# there is also gpt-3.5-turbo-16k, which handles contexts up to 16k tokens (vs gpt-4's 8k and gpt-3.5-turbo's 4k).
MODEL="openai/gpt-4-1106-preview"
ARGS="--model $MODEL"


# if one of the args to this script was --ask, ask if test passed/failed/idk after each test
if [ "$1" = "--ask" ]; then
    ASK="1"
fi

# overwrite gptme using a function that adds the arguments and calls the original, supporting several arguments
function gptme() {
    echo "$ gptme $ARGS $@"
    /usr/bin/env gptme $ARGS "$@" --non-interactive </dev/null
    if [ "$ASK" = "1" ]; then
        echo -n "Did the test pass? (y/n/I) "
        read -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Test passed"
        elif [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Test failed"
            exit 1
        else
            echo "I don't know"
        fi
    fi
}

# set pwd to the output directory under this script
cd "$(dirname "$0")"
mkdir -p output
cd output

# run interactive tests if not in CI (GITHUB_ACTIONS is set by github actions)
interactive=${GITHUB_ACTIONS:-1}

set -e

# test stdin and cli-provided prompt
# NOTE: we do not do this as part of the suite, because our gptme function wrapper above does not support stdin
#       if you want to run it, copy the line into your terminal
# echo "The project mascot is a flying pig" | gptme "What is the project mascot?"

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

# 3 complex plots
gptme 'make a figure with 3 plots: one timeseries plot with multiple series (upper), one 3d plot of a sphere (left-bottom), and one 2d plot of a circle (right-bottom). Make it colorful and fancy!'

if [ "$interactive" = "1" ]; then
    # interactive matplotlib
    gptme 'plot an x^2 graph'
fi

# generate a mandelbrot set
gptme 'render mandelbrot set to mandelbrot.png'

# particle effect
gptme 'write a web app to particles.html which shows off an impressive and colorful particle effect using three.js'

# very heavy! run by hand
# gptme 'render a zooming mandelbrot video to mandelbrot.mp4, use a colorful gradient, write scripts to file'

# make sure it can build basic web apps from scratch
# NOTE: hard! often messes up tools use
gptme 'create a new vue project with typescript and pinia named "habit tracker", iterate on it for a few times to create a daily habit-tracker with 3-state buttons (completed, missed, unset) and a comment field for each entry. The UI should be table-looking, with one row per day and one column per habit. Make sure the UI is clean and modern.' --model anthropic
