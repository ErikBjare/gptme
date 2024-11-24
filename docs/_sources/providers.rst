Providers
=========

We support several LLM providers, including OpenAI, Anthropic, Azure, and any OpenAI-compatible server (e.g. ``ollama``, ``llama-cpp-python``).

To select a provider and model, run ``gptme`` with the ``--model`` flag set to ``<provider>/<model>``, for example:

.. code-block:: sh

    gptme --model openai/gpt-4o "hello"
    gptme --model anthropic "hello"  # if model part unspecified, will fall back to the provider default
    gptme --model openrouter/meta-llama/llama-3.1-70b-instruct "hello"
    gptme --model gemini/gemini-1.5-flash-latest "hello"
    gptme --model local/llama3.2:1b "hello"

On first startup, if ``--model`` is not set, and no API keys are set in the config or environment it will be prompted for. It will then auto-detect the provider, and save the key in the configuration file.

You can persist the below environment variables in the :doc:`config` file.

OpenAI
------

To use OpenAI, set your API key:

.. code-block:: sh

    export OPENAI_API_KEY="your-api-key"

Anthropic
---------

To use Anthropic, set your API key:

.. code-block:: sh

    export ANTHROPIC_API_KEY="your-api-key"

OpenRouter
----------

To use OpenRouter, set your API key:

.. code-block:: sh

    export OPENROUTER_API_KEY="your-api-key"

Gemini
----------

To use Gemini, set your API key:

.. code-block:: sh

    export GEMINI_API_KEY="your-api-key"

Groq
----

To use Groq, set your API key:

.. code-block:: sh

    export GROQ_API_KEY="your-api-key"

xAI
---

To use xAI, set your API key:

.. code-block:: sh

    export XAI_API_KEY="your-api-key"

Local
-----

There are several ways to run local LLM models in a way that exposes a OpenAI API-compatible server.

Here's we will cover how to achieve that with ``ollama``.

You first need to install ``ollama``, then you can run it with:

.. code-block:: sh

    ollama pull llama3.2:1b
    ollama serve
    OPENAI_BASE_URL="http://127.0.0.1:11434/v1" gptme 'hello' -m local/llama3.2:1b

.. note::

    Small models will not reliably follow the system prompt, and will thus fail to use tools, severely limiting the usefulness of gptme.

    The smallest model which performs somewhat adequately is Llama 3.1 70B. You can find an overview of how different models perform on the :doc:`evals` page.
