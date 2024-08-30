Evals
=====

gptme provides LLMs with a wide variety of tools, but how well do models make use of them? Which tasks can they complete, and which ones do they struggle with? How far can they get on their own, without any human intervention?

To answer these questions, we have created a evaluation suite that tests the capabilities of LLMs on a wide variety of tasks.

.. note::
    The evaluation suite is still under development, but the eval harness is mostly complete.

Usage
-----

You can run the simple ``hello`` eval with gpt-4o like this:

.. code-block:: bash

    gptme-eval hello --model openai/gpt-4o

However, we recommend running it in Docker to improve isolation and reproducibility:

.. code-block:: bash

    make build-docker
    docker run \
        -e "OPENAI_API_KEY=<your api key>" \
        -v $(pwd)/eval_results:/app/eval_results \
        gptme-eval hello --model openai/gpt-4o


Example run
-----------

Here's the output from a run of the eval suite:

.. code-block::

   $ gptme-eval eval_results/eval_results_20240830_203143.csv
   +-----------------------------------------------+-------------+------------+-----------+---------------+------------+
   | Model                                         | hello-ask   | prime100   | hello     | hello-patch   | init-git   |
   +===============================================+=============+============+===========+===============+============+
   | openai/gpt-4o                                 | ✅ 17.89s   | ✅ 18.69s  | ✅ 17.66s | ✅ 13.95s     | ✅ 20.14s  |
   +-----------------------------------------------+-------------+------------+-----------+---------------+------------+
   | anthropic/claude-3-5-sonnet-20240620          | ✅ 21.06s   | ✅ 16.46s  | ❌ 0.00s  | ❌ 0.00s      | ❌ 0.00s   |
   +-----------------------------------------------+-------------+------------+-----------+---------------+------------+
   | openrouter/meta-llama/llama-3.1-405b-instruct | ✅ 8.68s    | ✅ 15.81s  | ✅ 12.70s | ✅ 12.12s     | ✅ 13.36s  |
   +-----------------------------------------------+-------------+------------+-----------+---------------+------------+


Note that in this particular run, something went wrong with Anthropic. We are working on making the evals more robust and informative, and challenging.


Other evals
-----------

We have considered running gptme on other evals, such as SWE-Bench, but have not yet done so.

If you are interested in running gptme on other evals, drop a comment in the issues!
