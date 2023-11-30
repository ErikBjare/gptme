# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from docutils import nodes
from docutils.parsers.rst import Directive

project = "gptme"
copyright = "2023, Erik Bjäreholt"
author = "Erik Bjäreholt"


class ChatDirective(Directive):
    required_arguments = 0
    optional_arguments = 0
    has_content = True

    def run(self):
        self.assert_has_content()
        # parse "User:", "Assistant:" and "System:" lines as chat messages
        # msgs = [
        #     {"role": line.split(":"), "content": line.split(":", 1)[1].strip()}
        #     for line in self.content
        #     if any(line.startswith(role) for role in ["User", "Assistant", "System"])
        # ]
        msgs = []
        for line in self.content:
            if any(line.startswith(role) for role in ["User", "Assistant", "System"]):
                role, content = line.split(":", 1)
                msgs.append({"role": role, "content": content.strip()})
            else:
                msgs[-1]["content"] += f"\n{line}"

        for msg in msgs:
            if msg["role"] == "User":
                msg["role_style"] = "color: #6666ff;"
            elif msg["role"] == "Assistant":
                msg["role_style"] = "color: #44ff44"
            elif msg["role"] == "System":
                msg["role_style"] = "color: #999999"

        # set up table
        src = f"""
<table style="width: 100%; margin-bottom: 1em">
  {"".join(f'<tr><td style="text-align: right; padding: 0 1em 0 1em; width: 0.1%; font-weight: bold; {msg["role_style"]}">{msg["role"]}</td><td><pre style="margin-right: 1em; padding: 5px; margin-bottom: 0.5em;">{msg["content"]}</pre></td></tr>' for msg in msgs)}
</table>
""".strip()

        return [nodes.raw("", src, format="html")]


def setup(app):
    app.add_directive("chat", ChatDirective)


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.autosectionlabel",
    "sphinx_click",
]


templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

extlinks = {
    "issue": ("https://github.com/ErikBjare/gptme/issues/%s", "issue #"),
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]

html_title = "gptme"
html_logo = "../media/logo.png"
html_favicon = "../media/logo.png"

html_theme_options = {
    "repository_url": "https://github.com/ErikBjare/gptme",
    "path_to_docs": "docs",
    "use_repository_button": True,
    "use_edit_page_button": True,
    "extra_navbar": """
    <p>
        Back to <a href="https://github.com/ErikBjare/gptme">GitHub</a>
    </p>""",
}

show_navbar_depth = 2
