Examples
========

A list of things you can do with gptme.

To see example output without running the commands yourself, check out the :doc:`demos`.

.. code-block:: bash

    gptme 'write a web app to particles.html which shows off an impressive and colorful particle effect using three.js'
    gptme 'render mandelbrot set to mandelbrot.png'

    # chaining prompts
    gptme 'show me something cool in the python repl' - 'something cooler' - 'something even cooler'

    # stdin
    git diff | gptme 'complete the TODOs in this diff'
    make test | gptme 'fix the failing tests'

    # from a file
    gptme 'summarize this' README.md
    gptme 'refactor this' main.py

    # it can read files using tools, if contents not provided in prompt
    gptme 'suggest improvements to my vimrc'

Do you have a cool example? Share it with us in the `Discussions <https://github.com/ErikBjare/gptme/discussions>`_!


.. rubric:: Skip confirmation and run in non-interactive mode

You can skip confirmation prompts and run in non-interactive mode to terminate when all prompts have been completed.

This should make it first write snake.py, then make the change in a following prompt:

.. code-block:: bash

    gptme --non-interactive --no-confirm 'create a snake game using curses in snake.py, dont run it' '-' 'make the snake green and the apple red'

The '-' is special "multiprompt" syntax that tells the assistant to wait for the assistant to finish work on the next prompt (run until no more tool calls) before continuing. For more such non-interactive examples, see :doc:`automation`.


.. rubric:: Generate Commit Messages

Generate meaningful commit messages based on your git diff:

.. code-block:: bash

   msg_file=$(mktemp)
   git diff --cached | gptme --non-interactive "Write a concise, meaningful commit message for this diff to `$msg_file`.

   Format: <type>: <subject>
   Where type is one of: feat, fix, docs, style, refactor, test, chore, build";

   git commit -F "$msg_file"


.. rubric:: Generate Documentation

Generate docstrings for all functions in a file:

.. code-block:: bash

   gptme --non-interactive "Patch these files to include concise docstrings for all functions, skip functions that already have docstrings. Include: brief description, parameters." $@

These examples demonstrate how gptme can be used to create simple yet powerful automation tools. Each script can be easily customized and expanded to fit specific project needs.

