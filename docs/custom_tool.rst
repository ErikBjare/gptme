Creating a Custom Tool for gptme
=================================

Introduction
------------
In gptme, a custom tool allows you to extend the functionality of the assistant by
defining new tools that can be executed.
This guide will walk you through the process of creating and registering a custom tool.

Creating a Custom Tool
-----------------------
To create a custom tool, you need to define a new instance of the ``ToolSpec`` class.
This class requires several parameters:

- **name**: The name of the tool.
- **desc**: A description of what the tool does.
- **instructions**: Instructions on how to use the tool.
- **examples**: Example usage of the tool.
- **execute**: A function that defines the tool's behavior when executed.
- **block_types**: The block types to detects.
- **parameters**: A list of parameters that the tool accepts.

Here is a basic example of defining a custom tool:

.. code-block:: python

    import random
    from gptme.tools import ToolSpec, Parameter, ToolUse
    from gptme.message import Message

    def execute(code, args, kwargs, confirm):

        if code is None and kwargs is not None:
            code = kwargs.get('side_count')

        yield Message('system', f"Result: {random.randint(1,code)}")

    def examples(tool_format):
        return f"""
    > User: Throw a dice and give me the result.
    > Assistant:
    {ToolUse("dice", [], "6").to_output(tool_format)}
    > System: 3
    > assistant: The result is 3
    """.strip()

    tool = ToolSpec(
        name="dice",
        desc="A dice simulator.",
        instructions="This tool generate a random integer value like a dice.",
        examples=examples,
        execute=execute,
        block_types=["dice"],
        parameters=[
            Parameter(
                name="side_count",
                type="integer",
                description="The number of faces of the dice to throw.",
                required=True,
            ),
        ],
    )

Registering the Tool
---------------------
To ensure your tool is available for use, you can specify the module in the ``TOOL_MODULES`` env variable or
setting in your :doc:`project configuration file <config>`, which will automatically load your custom tools.

.. code-block:: toml

    TOOL_MODULES = "gptme.tools,path.to.your.custom_tool_module"

Don't remove the ``gptme.tools`` package unless you know exactly what you are doing.

Ensure your module is in the Python path by either installing it
(e.g. with ``pip install .`` or ``pipx runpip gptme install .``, depending on installation method)
or by temporarily modifying the `PYTHONPATH` environment variable. For example:

.. code-block:: bash

    export PYTHONPATH=$PYTHONPATH:/path/to/your/module


This lets Python locate your module during development and testing without requiring installation.
