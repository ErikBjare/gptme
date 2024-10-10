Automation
==========

gptme can be used to create powerful yet simple automated workflows. Here we showcase small but powerful examples that demonstrate the capabilities of gptme in various workflows and automation scenarios.

We will be using shell scripts, cron jobs, and other tools to automate the workflows.


.. note::

   This is a work in progress. We intend to make gptme more powerful for automations, see `issue #143 <https://github.com/ErikBjare/gptme/issues/143>`_ for more details on this plan.



.. rubric:: Example: Implement feature

This example demonstrates how to implement a feature in a codebase using gptme, making sure the code is correct before creating a pull request.

Given a GitHub issue it will check out a new branch, look up relevant files, make changes, typecheck/test them, and create a pull request if everything is correct.

.. code-block:: bash

   $ gptme 'read <url>' '-' 'create a branch' '-' 'look up relevant files' '-' 'make changes' '-' 'typecheck it' '-' 'test it' '-' 'create a pull request'


.. include:: automation/example_code_review.rst

.. include:: automation/example_activity_summary.rst
