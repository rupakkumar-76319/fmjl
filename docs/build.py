"""Builds docs/rulebook.html from the rulebook's Markdown form, with the same style as index.html.

Run: python docs/build.py        (needs: pip install markdown-it-py)
"""
import html
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<a href="index.html" class="brand">FMJL</a>
<nav>
<a href="index.html">Introduction</a>
<a href="rulebook.html">Rulebook</a>
<a href="https://pypi.org/project/fmjl/">PyPI</a>
<a href="https://marketplace.visualstudio.com/items?itemName=rupakkumar.fmjl">VS Code</a>
<a href="https://github.com/rupakkumar-76319/fmjl">GitHub</a>
</nav>
</header>
<main>
{body}
</main>
<footer>
<p>FMJL is released under the MIT License. Copyright Rupak Kumar. The rulebook is the authority; if a tool and the rulebook disagree, the tool has a bug.</p>
</footer>
</body>
</html>
"""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render(md_text):
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    tokens = md.parse(md_text)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and i + 1 < len(tokens):
            tok.attrSet("id", slug(tokens[i + 1].content))
    return md.renderer.render(tokens, md.options, {})


def main():
    src = sorted(ROOT.glob("rulebook/fmjl_rulebook_v*.md"))
    if not src:
        print("no rulebook found")
        return 1
    text = src[-1].read_text(encoding="utf-8")
    if text.startswith("---\n"):
        text = text[text.index("\n---\n", 4) + 5:]
    m = re.search(r"^# (.+)$", text, re.M)
    title = m.group(1) if m else "FMJL Rulebook"
    body = render(text)
    out = HERE / "rulebook.html"
    page = PAGE.format(title=html.escape(title), body=body,
                       description="The rules of FMJL: one document, two forms, twenty element types, and the JSON Schema.")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"wrote {out} from {src[-1].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
