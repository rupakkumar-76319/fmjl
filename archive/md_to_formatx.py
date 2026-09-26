"""Reference converter: Markdown -> Format X v0.1.

Usage: python md_to_formatx.py input.md --doc my_doc --source original.pdf > my_doc.jsonl
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from markdown_it import MarkdownIt

VERSION = "0.1"
CONVERTER = "formatx-md 0.1"

BLOCK_TYPES = {
    "heading_open": "heading",
    "paragraph_open": "paragraph",
    "bullet_list_open": "list",
    "ordered_list_open": "list",
    "table_open": "table",
    "blockquote_open": "quote",
    "fence": "code",
    "code_block": "code",
    "html_block": "paragraph",
}

# Element key order: metadata first, md last (easier for humans to scan)
KEY_ORDER = ["id", "hash", "type", "subtype", "level", "parent", "page", "pages", "bbox",
             "characters", "reference", "confidence", "lang", "access", "html", "latex",
             "file", "md"]


def element_hash(el_type: str, md: str) -> str:
    """First 16 hex chars of SHA-256 of type + newline + md (rulebook section 6.1)."""
    return hashlib.sha256(f"{el_type}\n{md}".encode("utf-8")).hexdigest()[:16]


def make_element(**fields) -> dict:
    """Build an element with computed hash and characters, in canonical key order."""
    fields["hash"] = element_hash(fields["type"], fields["md"])
    fields["characters"] = len(fields["md"])
    return {k: fields[k] for k in KEY_ORDER if k in fields}


def make_header(doc, source, source_bytes, elements, structure, lang="en", access=None,
                protection="none", signed=False, converter=CONVERTER) -> dict:
    return {
        "type": "document",
        "version": VERSION,
        "doc": doc,
        "source": source,
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
        "protection": protection,
        "signed": signed,
        "converter": converter,
        "structure": structure,
        "elements": elements,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lang": lang,
        "access": access or ["all"],
    }


def md_to_elements(md_text: str, doc: str) -> list[dict]:
    parser = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    tokens = parser.parse(md_text)
    lines = md_text.splitlines()
    elements, stack = [], []  # stack: [(level, id)] of open headings

    for i, tok in enumerate(tokens):
        if tok.level != 0 or tok.type not in BLOCK_TYPES or tok.map is None:
            continue
        el_type = BLOCK_TYPES[tok.type]
        start, end = tok.map
        md = "\n".join(lines[start:end]).strip()
        el_id = f"{doc}#e{len(elements) + 1}"
        fields = {"id": el_id, "type": el_type, "md": md}

        if el_type == "heading":
            level = int(tok.tag[1])
            while stack and stack[-1][0] >= level:
                stack.pop()
            fields["level"] = level
            fields["parent"] = stack[-1][1] if stack else None
            stack.append((level, el_id))
        else:
            fields["parent"] = stack[-1][1] if stack else None

        elements.append(make_element(**fields))
    return elements


def convert(md_text: str, doc: str, source: str, source_bytes: bytes) -> list[dict]:
    elements = md_to_elements(md_text, doc)
    structure = any(e["type"] == "heading" for e in elements)
    return [make_header(doc, source, source_bytes, len(elements), structure), *elements]


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--doc", required=True, help="short name: lowercase letters, digits, _ or -")
    ap.add_argument("--source", default=None, help="original file name")
    args = ap.parse_args()
    raw = args.input.read_bytes()
    for line in convert(raw.decode("utf-8"), args.doc, args.source or args.input.name, raw):
        print(dumps(line))


if __name__ == "__main__":
    main()
