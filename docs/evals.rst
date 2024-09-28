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

   $ gptme-eval eval_results/20240917_172916/eval_results.csv
   === Model Comparison ===
   Model                                 init-git    init-rust    hello      hello-patch    hello-ask    init-react    prime100
   ------------------------------------  ----------  -----------  ---------  -------------  -----------  ------------  ----------
   openai/gpt-4o                         ✅ 7.74s    ✅ 9.62s     ✅ 5.02s   ✅ 5.06s       ✅ 4.69s     ❌ timeout    ✅ 7.48s
   openai/o1-mini                        ✅ 18.44s   ✅ 21.63s    ✅ 21.20s  ✅ 27.39s      ❌ timeout   ❌ 42.65s     ✅ 17.99s
   anthropic/claude-3-5-sonnet-20240620  ❌ timeout  ❌ timeout   ✅ 8.77s   ✅ 7.09s       ✅ 8.08s     ❌ timeout    ✅ 11.26s


We are working on making the evals more robust, informative, and challenging.


Other evals
-----------

We have considered running gptme on other evals, such as SWE-Bench, but have not yet done so.

If you are interested in running gptme on other evals, drop a comment in the issues!
