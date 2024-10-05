Contributing
============

We welcome contributions to the project. Here is some information to get you started.

.. note::
    This document is a work in progress. PRs are welcome.

.. contents::
   :local:

Tests
-----

Run tests with `make test`.

Some tests make LLM calls, which might take a while and so are not run by default. You can run them with `make test SLOW=true`.

Tests are currently covering:

 - tools like shell and Python
 - integration tests that make LLM calls, run the generated code, and checks the output
   - this could be used as a LLM eval harness

There are also some integration tests in `./tests/test-integration.sh` which are used to manually test more complex tasks.

Release
-------

To make a release, simply run `make release` and follow the instructions.
