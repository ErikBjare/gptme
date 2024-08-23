Evals
=====

gptme provides LLMs with a wide variety of tools, but how well do models make use of them? Which tasks can they complete, and which ones do they struggle with? How far can they get on their own, without any human intervention?

To answer these questions, we have created a evaluation suite that tests the capabilities of LLMs on a wide variety of tasks.

.. note::
    The evaluation suite is still under development, but the eval harness is mostly complete.

You can run the simple ``hello`` eval with gpt-4o like this:

.. code-block:: bash

    gptme-eval hello --model openai/gpt-4o

However, we recommend running it in Docker to improve isolation and reproducibility:

.. code-block:: bash

    make build-docker
    docker run \
        -e "OPENAI_API_KEY=<your api key>" \
        -v $(pwd)/eval_results:/app/gptme/eval_results \
        gptme --timeout 60 $@


Example run
-----------

Here's the output from a run of the eval suite: TODO


Other evals
-----------

We have considered running gptme on other evals, such as SWE-Bench, but have not yet done so.

If you are interested in running gptme on other evals, drop a comment in the issues!
