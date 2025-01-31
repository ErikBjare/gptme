Providers
=========

We support several LLM providers, including OpenAI, Anthropic, OpenRouter, Deepseek, Azure, and any OpenAI-compatible server (e.g. ``ollama``, ``llama-cpp-python``).

To select a provider and model, run ``gptme`` with the ``-m``/``--model`` flag set to ``<provider>/<model>``, for example:

.. code-block:: sh

    gptme --model openai/gpt-4o "hello"
    gptme --model anthropic "hello"  # if model part unspecified, will fall back to the provider default
    gptme --model openrouter/meta-llama/llama-3.1-70b-instruct "hello"
    gptme --model deepseek/deepseek-reasoner "hello"
    gptme --model gemini/gemini-1.5-flash-latest "hello"
    gptme --model groq/llama-3.3-70b-versatile "hello"
    gptme --model xai/grok-beta "hello"
    gptme --model local/llama3.2:1b "hello"

On first startup, if ``--model`` is not set, and no API keys are set in the config or environment it will be prompted for. It will then auto-detect the provider, and save the key in the configuration file.

You can list the models known to gptme using ``gptme '/models' - '/exit'``

Use the ``[env]`` section in the ``gptme.toml`` :doc:`config` file to store API keys using the same format as the environment variables:

- ``OPENAI_API_KEY="your-api-key"``
- ``ANTHROPIC_API_KEY="your-api-key"``
- ``OPENROUTER_API_KEY="your-api-key"``
- ``GEMINI_API_KEY="your-api-key"``
- ``XAI_API_KEY="your-api-key"``
- ``GROQ_API_KEY="your-api-key"``
- ``DEEPSEEK_API_KEY="your-api-key"``

.. rubric:: Local

You can use local LLM models using any OpenAI API-compatible server.

To achieve that with ``ollama``, install it then run:

.. code-block:: sh

    ollama pull llama3.2:1b
    ollama serve
    OPENAI_BASE_URL="http://127.0.0.1:11434/v1" gptme 'hello' -m local/llama3.2:1b

.. note::

    Small models won't work well with tools, severely limiting the usefulness of gptme. You can find an overview of how different models perform on the :doc:`evals` page.
