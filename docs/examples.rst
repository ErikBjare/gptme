Examples
========

A list of things you can do with gptme.

To see example output without running the commands yourself, check out the :doc:`demos`.

.. code-block:: bash

    gptme 'write a web app to particles.html which shows off an impressive and colorful particle effect using three.js'
    gptme 'render mandelbrot set to mandelbrot.png'

    # files
    gptme 'summarize this' README.md
    gptme 'refactor this' main.py

    # stdin
    git status -vv | gptme 'fix TODOs'
    git status -vv | gptme 'commit'
    make test | gptme 'fix the failing tests'

    # if path not directly provided in prompt, it can read files using tools
    gptme 'suggest improvements to my vimrc'

    # chaining prompts
    gptme 'show me something cool in the python repl' - 'something cooler' - 'something even cooler'

Do you have a cool example? Share it with us in the `Discussions <https://github.com/ErikBjare/gptme/discussions>`_!


.. rubric:: Skip confirmation and run in non-interactive mode

You can skip confirmation prompts and run in non-interactive mode to terminate when all prompts have been completed.

This should make it first write snake.py, then make the change in a following prompt:

.. code-block:: bash

    gptme --non-interactive --no-confirm 'create a snake game using curses in snake.py, dont run it' '-' 'make the snake green and the apple red'

The '-' is special "multiprompt" syntax that tells the assistant to wait for the assistant to finish work on the next prompt (run until no more tool calls) before continuing. For more such non-interactive examples, see :doc:`automation`.
