GPT playground
==============

[![Build](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/gpt-playground/actions/workflows/build.yml)

Just me playing with large language models, langchain, etc.


## gptme

An interactive CLI to let you chat with ChatGPT, with extra tools like:

 - Execute shell/Python code on the local machine.
   - Command output (stdout & stderr + error code) will be feeded back to the agent, making it able to self-correct errors etc.
 - Handle long context sizes through summarization.
   - (not very well developed)


## TODO

Ideas for things to try:

 - An agent that looks up the latest CI job, and if it failed, tries to figure out how to fix it.
 - An agent that looks up recent GitHub issues, tries to generate an answer.
 - An agent that looks up recent GitHub PRs, tries to generate an action (comment, ask for human review, merge, close).
