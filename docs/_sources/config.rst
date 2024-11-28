Configuration
=============

gptme has two configuration files:

- global configuration
- project configuration

It also supports environment variables for configuration, which take precedence over the configuration files.

The CLI also supports a variety of options that can be used to override both configuration values and environment variables.


Global config
-------------

The file is located at ``~/.config/gptme/config.toml``.

Here is an example:

.. code-block:: toml

    [prompt]
    about_user = "I am a curious human programmer."
    response_preference = "Don't explain basic concepts"

    [env]
    # Uncomment to use Claude 3.5 Sonnet by default
    #MODEL = "anthropic/claude-3-5-sonnet-20240620"

    # One of these need to be set
    # If none of them are, they will be prompted for on first start
    OPENAI_API_KEY = ""
    ANTHROPIC_API_KEY = ""
    OPENROUTER_API_KEY = ""
    AZURE_OPENAI_API_KEY = ""

    # Uncomment to use with Ollama
    #MODEL = "local/<model-name>"
    #OPENAI_BASE_URL = "http://localhost:11434/v1"

The ``prompt`` section contains options for the prompt.

The ``env`` section contains environment variables that gptme will fall back to if they are not set in the shell environment. This is useful for setting defaults for API keys and models.


Project config
--------------

The project configuration file is intended to let the user configure how gptme works within a particular project/workspace.

.. note::

    The project configuration file is a very early feature and is likely to change/break in the future.

gptme will look for a ``gptme.toml`` file in the workspace root (this is the working directory if not overridden by the ``--workspace`` option). This file contains project-specific configuration options.

This file currently supports a single option, ``files``, which is a list of paths that gptme will always include in the context:

.. code-block:: toml

    files = ["README.md", "Makefile"]
