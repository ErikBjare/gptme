CLI Reference
=============

gptme provides the following commands:

.. contents:: Commands
   :depth: 1
   :local:
   :backlinks: none

This is the full CLI reference. For a more concise version, run ``gptme --help``.

.. rubric:: gptme

You can skip confirmation prompts and run in non-interactive mode to terminate when all prompts have been completed:

.. code-block:: bash

    gptme --non-interactive --no-confirm 'create a snake game using curses in snake.py, dont run it' '-' 'make the snake green and the apple red'

This should make it first write snake.py, then make the change in a following prompt.

The '-' is special "multiprompt" syntax that tells the assistant to wait for the assistant to finish work on the next prompt (run until no more tool calls) before continuing.

.. click:: gptme.cli:main
   :prog: gptme
   :nested: full

.. rubric:: gptme-server

.. click:: gptme.server:main
   :prog: gptme-server
   :nested: full

.. rubric:: gptme-eval

.. click:: gptme.eval:main
   :prog: gptme-eval
   :nested: full
