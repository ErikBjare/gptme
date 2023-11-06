# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "gptme"
copyright = "2023, Erik Bjäreholt"
author = "Erik Bjäreholt"

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
