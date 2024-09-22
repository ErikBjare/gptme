Examples
========

A list of things you can do with gptme.

To see example output without running the commands yourself, check out the :ref:`demos`.


.. code-block:: bash

    gptme 'write a web app to particles.html which shows off an impressive and colorful particle effect using three.js'
    gptme 'render mandelbrot set to mandelbrot.png'

    # stdin
    make test | gptme 'fix the failing tests'

    # from a file
    gptme 'summarize this' README.md
    gptme 'refactor this' main.py

    # it can read files using tools, if contents not provided in prompt
    gptme 'suggest improvements to my vimrc'


Do you have a cool example? Share it with us in the `Discussions <https://github.com/ErikBjare/gptme/discussions>`_!
