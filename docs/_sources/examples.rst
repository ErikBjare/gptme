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


Commit Message Generator
------------------------

Generate meaningful commit messages based on your git diff:

.. code-block:: bash

   #!/bin/bash
   # Usage: git-commit-auto
   msg_file=$(mktemp)
   git diff --cached | gptme --non-interactive "Write a concise, meaningful commit message for this diff to `$msg_file`.

   Format: <type>: <subject>
   Where type is one of: feat, fix, docs, style, refactor, test, chore, build";

   git commit -F "$msg_file"

Generate Documentation
----------------------

Generate docstrings for all functions in a file:

.. TODO: not automation, move to examples.

.. code-block:: bash

   #!/bin/bash
   gptme --non-interactive "Patch these files to include concise docstrings for all functions, skip functions that already have docstrings. Include: brief description, parameters." $@


These examples demonstrate how gptme can be used to create simple yet powerful automation tools. Each script can be easily customized and expanded to fit specific project needs.

