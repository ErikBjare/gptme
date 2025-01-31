Contributing
============

We welcome contributions to the project. Here is some information to get you started.

.. note::
    This document is a work in progress. PRs are welcome.

Install
-------

.. code-block:: bash

   # checkout the code and navigate to the root of the project
   git clone https://github.com/ErikBjare/gptme.git
   cd gptme

   # install poetry (if not installed)
   pipx install poetry

   # activate the virtualenv
   poetry shell

   # build the project
   make build

You can now start ``gptme`` from your development environment using the regular commands.

You can also install it in editable mode with ``pipx`` using ``pipx install -e .`` which will let you use your development version of gptme regardless of venv.

Tests
-----

Run tests with ``make test``.

Some tests make LLM calls, which might take a while and so are not run by default. You can run them with ``make test SLOW=true``.

There are also some integration tests in ``./tests/test-integration.sh`` which are used to manually test more complex tasks.

There is also the :doc:`evals`.

Release
-------

To make a release, simply run ``make release`` and follow the instructions.
