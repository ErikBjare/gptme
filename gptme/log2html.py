import html
import logging
from pathlib import Path
from typing import List

from .message import Message

logger = logging.getLogger(__name__)

def export_to_html(log: List[Message], output_path: Path) -> None:
    """
    Export the conversation log to a self-contained HTML file.

    This function generates an HTML file that includes the conversation log,
    styled with Tailwind CSS. The HTML file is self-contained and can be
    uploaded to a static site or included in another page.

    The Content Security Policy (CSP) is set to allow necessary resources
    while still maintaining a good level of security.

    Args:
        log (List[Message]): The conversation log to export.
        output_path (Path): The path where the HTML file will be saved.

    Returns:
        None
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Conversation Log</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/2.3.10/purify.min.js"></script>
        <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net/npm/marked/marked.min.js https://cdnjs.cloudflare.com/ajax/libs/dompurify/2.3.10/purify.min.js;">
        <script>
            function toggleMessage(id) {{
                const content = document.getElementById(id);
                const button = document.getElementById(`toggle-${{id}}`);
                if (content.classList.contains('hidden')) {{
                    content.classList.remove('hidden');
                    button.textContent = 'Hide';
                }} else {{
                    content.classList.add('hidden');
                    button.textContent = 'Show';
                }}
            }}

            function processCodeBlocks() {{
                const codeBlocks = document.querySelectorAll('pre code');
                codeBlocks.forEach((block, index) => {{
                    const wrapper = document.createElement('details');
                    wrapper.className = 'mb-4 border border-gray-300 rounded-md overflow-hidden';
                    const summary = document.createElement('summary');
                    const className = block.className;
                    const lang = className.split('-')[1] || 'code';
                    summary.textContent = lang;
                    summary.className = 'cursor-pointer text-blue-500 hover:text-blue-700 p-2 bg-gray-100 font-bold';
                    wrapper.appendChild(summary);
                    block.parentNode.className = 'p-4 bg-gray-50';
                    block.className += ' text-sm';
                    // Unescape HTML entities in code blocks
                    block.innerHTML = block.innerHTML.replace(/&quot;/g, '"').replace(/&amp;/g, '&').trim();
                    block.parentNode.parentNode.insertBefore(wrapper, block.parentNode);
                    wrapper.appendChild(block.parentNode);
                }});
            }}

            document.addEventListener('DOMContentLoaded', processCodeBlocks);
        </script>
    </head>
    <body class="bg-gray-100 p-8 font-mono">
        <div class="max-w-4xl mx-auto bg-white shadow-md rounded-lg overflow-hidden">
            <h1 class="text-2xl font-bold p-4 bg-blue-500 text-white">Conversation Log</h1>
            <div class="p-4 space-y-4">
                {''.join(_message_to_html(msg, idx) for idx, msg in enumerate(log))}
            </div>
        </div>
    </body>
    </html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Exported conversation log to {output_path}")

def _message_to_html(msg: Message, idx: int) -> str:
    """Convert a single message to HTML."""
    role_colors = {
        "user": "bg-green-100",
        "assistant": "bg-blue-100",
        "system": "bg-gray-100",
    }
    color_class = role_colors.get(msg.role, "bg-gray-100")

    # Escape all content to prevent XSS
    text_content = html.escape(msg.content)

    is_system = msg.role == "system"
    hidden_class = "hidden" if is_system else ""
    button_text = "Show" if is_system else "Hide"

    backslash = "\\"
    return f"""
    <div class="p-4 rounded-lg {color_class} relative">
        <div class="flex justify-between items-center mb-2">
            <p class="font-bold">{msg.role.capitalize()}:</p>
            <button id="toggle-msg-{idx}" class="text-sm text-blue-500 hover:text-blue-700" onclick="toggleMessage('msg-{idx}')">{button_text}</button>
        </div>
        <div id="msg-{idx}" class="{hidden_class} overflow-x-auto max-w-full">
            <div class="markdown-content"></div>
        </div>
    </div>
    <script>
        const _el{idx} = document.getElementById('msg-{idx}').querySelector('.markdown-content');
        _el{idx}.textContent = `{text_content.replace('`', backslash + '`')}`;
        _el{idx}.innerHTML = DOMPurify.sanitize(marked.parse(_el{idx}.textContent), {{FORBID_TAGS: ['style', 'script', 'html']}});
    </script>
    """
