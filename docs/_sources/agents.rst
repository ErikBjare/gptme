Agents
======

gptme supports "agents", which we think of as having:

- Identity
- Personality & preferences
- Memory

  - Journal
  - Tasks
  - Knowledgebase

- Extra tools

  - Email
  - Chat
  - Social Media

gptme agents are git-based and all their data is stored in a git repository. This makes it easy to share and collaborate on agents, and to keep a history of all interactions with the agent.

They leverage the ``gptme.toml`` :doc:`project configuration file <config>` using a particular set of prompts and directory structure which makes it capable to keep a journal, track tasks, remember things, and more.

You can create your own agent with the `gptme-agent-template <https://github.com/gptme/gptme-agent-template/>`_.

Bob
---

Bob, aka `@TimeToBuildBob <https://github.com/TimeToBuildBob>`_, is the first experimental agent built on top of gptme. He is a friendly and helpful bot that helps with working on gptme and related projects.

Why personify agents?
^^^^^^^^^^^^^^^^^^^^^

While personifying agents might seem like a silly idea for professional use, it can actually be quite helpful when working with them. It can help get into the right mindset for interacting with the agent, help you remember what the agent is for, what you've told them, and make the agent more memorable and relatable.
