from pathlib import Path

import click
import openai

from langchain.agents import initialize_agent
from langchain.tools.base import BaseTool
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import ChatOpenAI
from langchain.indexes import VectorstoreIndexCreator
from langchain.agents import load_tools

from .prompts import context_ai_orchestrator

@click.group()
def main():
    pass


class ReflectTool(BaseTool):
    """Tool that adds the capability to reflect on an answer."""

    name = "Reflect"
    description = (
        "You can use this when you want to present and reflect on the answer you just got."
    )

    def _run(self, query: str) -> str:
        """Use the Reflect tool."""
        print(query)
        return query

    async def _arun(self, query: str) -> str:
        raise NotImplementedError("Tool does not support async")

@main.command()
@click.argument("query")
@click.option("--context")
@click.option("--keep-asking", is_flag=True)
def agent(query: str, context: str, keep_asking=False):
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
    tools = load_tools(["terminal"], llm=llm)
    # tools += [StdInInquireTool()]
    # tools += [ReflectTool()]
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

    if not context:
        context = context_ai_orchestrator

    history = ""
    if context:
        history += context + "\n---\n"
    history += "Human: If a command fails, try to figure out the cause and a solution.\n"
    history += "Assistant: Understood.\n"
    if not query:
        query = input(">>> ")
    while True:
        print(history)
        with open("history.txt", "w") as f:
            f.write(history)
        if query:
            history += f"Human: {query}\n"
        try:
            res = agent.run(input=history.strip(), verbose=True)
            print(res)
            history += f"Human: {query}\n\n"
            history += f"AI: {res}\n\n"
            if keep_asking:
                query = input(">>> ")
            else:
                break
        except openai.error.InvalidRequestError as e:
            res = f"Got an error '{e}', try something different"
            print(res)
            history += f"Human: {query}\n\n"
            history += f"{res}\n\n"



@main.command()
def qa():
    llm = ChatOpenAI(temperature=0)
    chain = load_qa_chain(llm, chain_type="stuff")

    while True:
        query = input("Query: ")
        if query == "exit":
            break

        answer_chain = chain.run(question=query)
        print("Answer: ", answer_chain)


@main.command()
@click.argument("file")
def file(query: str, file: str):
    loader = load_notes()
    index = VectorstoreIndexCreator().from_loaders([loader])

    while True:
        query = input("Query: ")
        if query == "exit":
            break

        res = index.query_with_sources(query)
        print("Answer: ", res['answer'])


def load_notes():
    filepath = Path("~/annex/Backup/Standard Notes/erb-m2/Items/Note/").expanduser()
    assert filepath.exists()
    loader = DirectoryLoader(filepath, glob="**/202*.txt", loader_cls=TextLoader)
    docs = loader.load()
    assert docs
    return loader


if __name__ == '__main__':
    main()
