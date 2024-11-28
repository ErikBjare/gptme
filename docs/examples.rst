Examples
========

Here are some examples of how to use gptme and what its capabilities are.

To see example output without running the commands yourself, check out the :doc:`demos`.

.. code-block:: bash

    gptme 'write a web app to particles.html which shows off an impressive and colorful particle effect using three.js'
    gptme 'render mandelbrot set to mandelbrot.png'

    # files
    gptme 'summarize this' README.md
    gptme 'refactor this' main.py
    gptme 'what do you see?' image.png  # vision

    # stdin
    git status -vv | gptme 'fix TODOs'
    git status -vv | gptme 'commit'
    make test | gptme 'fix the failing tests'

    # if path not directly provided in prompt, it can read files using tools
    gptme 'explore'
    gptme 'take a screenshot and tell me what you see'
    gptme 'suggest improvements to my vimrc'

    # can read URLs (if browser tool is available)
    gptme 'implement this' https://github.com/ErikBjare/gptme/issues/286

    # can use `gh` shell tool to read issues, PRs, etc.
    gptme 'implement ErikBjare/gptme/issues/286'

    # create new projects
    gptme 'create a performant n-body simulation in rust'

    # chaining prompts
    gptme 'make a change' - 'test it' - 'commit it'
    gptme 'show me something cool in the python repl' - 'something cooler' - 'something even cooler'

Do you have a cool example? Share it with us in the `Discussions <https://github.com/ErikBjare/gptme/discussions>`_!

.. toctree::
   :maxdepth: 2
   :caption: More Examples

   demos
   automation
   projects


.. rubric:: Skip confirmation prompts

You can skip confirmation prompts using the ``--no-confirm`` flag. This is useful when you are confident the LLM will do what you want, so you don't want to have to confirm actions:

.. code-block:: bash

    gptme --no-confirm 'create a snake game using curses in snake.py, dont run it'

.. rubric:: Multiprompt syntax

The ``-`` separator allows you to chain multiple prompts together, letting the assistant finish running tools for one prompt before moving to the next:

.. code-block:: bash

    gptme 'create a project' '-' 'add tests' '-' 'commit changes'

This is particularly useful for breaking down complex tasks into steps and creating :doc:`automation` workflows.

.. rubric:: Non-interactive mode

The ``--non-interactive`` flag runs gptme in a mode that terminates after completing all prompts. This is useful for scripting and automation:

.. code-block:: bash

    gptme --non-interactive 'create a snake game using curses in snake.py, dont run it' '-' 'make the snake green and the apple red'

Note: ``--non-interactive`` implies ``--no-confirm``, so you don't need to specify both.
