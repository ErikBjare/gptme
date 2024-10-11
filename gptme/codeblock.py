from collections.abc import Generator
from dataclasses import dataclass, field
from xml.etree import ElementTree


@dataclass(frozen=True)
class Codeblock:
    lang: str
    content: str
    path: str | None = None
    start: int | None = field(default=None, compare=False)

    def __post_init__(self):
        # init path if path is None and lang is pathy
        if self.path is None and self.is_filename:
            object.__setattr__(self, "path", self.lang)  # frozen dataclass workaround

    def to_markdown(self) -> str:
        return f"```{self.lang}\n{self.content}\n```"

    def to_xml(self) -> str:
        return f'<codeblock lang="{self.lang}" path="{self.path}">\n{self.content}\n</codeblock>'

    @classmethod
    def from_markdown(cls, content: str) -> "Codeblock":
        if content.strip().startswith("```"):
            content = content[3:]
        if content.strip().endswith("```"):
            content = content[:-3]
        lang = content.splitlines()[0].strip()
        return cls(lang, content[len(lang) :])

    @classmethod
    def from_xml(cls, content: str) -> "Codeblock":
        """
        Example:
          <codeblock lang="python" path="example.py">
          print("Hello, world!")
          </codeblock>
        """
        root = ElementTree.fromstring(content)
        return cls(root.attrib["lang"], root.text or "", root.attrib.get("path"))

    @property
    def is_filename(self) -> bool:
        return "." in self.lang or "/" in self.lang

    @classmethod
    def iter_from_markdown(cls, markdown: str) -> list["Codeblock"]:
        return list(_extract_codeblocks(markdown))


def _extract_codeblocks(markdown: str) -> Generator[Codeblock, None, None]:
    # speed check (early exit): check if message contains a code block
    backtick_count = markdown.count("```")
    if backtick_count < 2:
        return

    lines = markdown.split("\n")
    stack: list[str] = []
    current_block = []
    current_lang = ""

    for idx, line in enumerate(lines):
        # not actually the starting index, but close enough
        # TODO: fix to actually be correct
        start_idx = sum(len(line) + 1 for line in lines[:idx])
        stripped_line = line.strip()
        if stripped_line.startswith("```"):
            if not stack:  # Start of a new block
                stack.append(stripped_line[3:])
                current_lang = stripped_line[3:]
            elif stripped_line[3:] and stack[-1] != stripped_line[3:]:  # Nested start
                current_block.append(line)
                stack.append(stripped_line[3:])
            else:  # End of a block
                if len(stack) == 1:  # Outermost block
                    yield Codeblock(
                        current_lang, "\n".join(current_block), start=start_idx
                    )
                    current_block = []
                    current_lang = ""
                else:  # Nested end
                    current_block.append(line)
                stack.pop()
        elif stack:
            current_block.append(line)
