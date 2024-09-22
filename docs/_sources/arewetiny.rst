Are we tiny?
============

gptme is intended to be small and simple, and focus on doing the right thing in the right way, rather than all the things in all the ways.

Since it is built by a single developer, there are limits imposed to how large things can get before it becomes too much to handle. Being aggressive about keeping things small and simple is a way to keep the project maintainable and fun to work on. The fastest way to kill a project is to make it too big and complex, and suffer burnout as a result.

To that end, in this document we will present some statistics about the current state of the project, trying to be mindful to keep an eye on this page and make sure we are not growing too much.


Lines of code
-------------

LoC Core
*******

.. command-output:: make -C .. cloc-core

LoC Tools
*********

.. command-output:: make -C .. cloc-tools

LoC Server
***********

.. command-output:: make -C .. cloc-server

LoC Tests
**********

.. command-output:: make -C .. cloc-tests

LoC Eval
********

.. command-output:: make -C .. cloc-eval

LoC Total
*********

.. command-output:: make -C .. cloc-total
