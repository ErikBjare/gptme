GPT playground
==============

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)

Just me playing with large language models, langchain, etc.


## gptme

An interactive CLI to let you interact with LLMs in a Chat-style interface.

With **features** like:

 - Supports OpenAI and **any model that runs in llama**
   - Thanks to llama-cpp-server!
 - Tools
   - Access to the local machine
   - Execute shell/Python code on the local machine.
     - Command output (stdout & stderr + error code) will be feeded back to the agent, making it able to self-correct errors etc.
 - Can handle long context sizes through summarization.
   - (not very well developed)


### Usage

Install deps:

```sh
poetry install
```

To use locally, you need to start llama-cpp-server:

```sh
poetry run python -m llama_cpp.server --model ~/ML/Manticore-13B.ggmlv3.q4_1.bin
```

Then you can interact with it using:
```sh
gptme --llm llama

```


## TODO

Ideas for things to try:

 - An agent that looks up the latest CI job, and if it failed, tries to figure out how to fix it.
 - An agent that looks up recent GitHub issues, tries to generate an answer.
 - An agent that looks up recent GitHub PRs, tries to generate an action (comment, ask for human review, merge, close).
