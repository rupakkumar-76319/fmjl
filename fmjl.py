#!/usr/bin/env python3
"""fmjl.py - reference tool for FMJL (.fmjl), rulebook version 0.4.

One document, two forms:
  name.fmjl   storage form   one JSON object per line, for machines
  name.md     authoring form normal Markdown with small hidden notes, for people

Commands:
  python fmjl.py new notes.md        authoring form  -> storage form (notes.fmjl)
  python fmjl.py md notes.fmjl       storage form    -> authoring form (notes.md)
  python fmjl.py fill notes.fmjl     fill id, hash, characters, parent; make md canonical
  python fmjl.py check notes.fmjl    check every rule, print errors with line numbers
  python fmjl.py view notes.fmjl     print the document as clean Markdown
  python fmjl.py info notes.fmjl     print title, element counts and an outline
  python fmjl.py upgrade old.fmjl    turn a version 0.1 or 0.2 file into 0.3

Needs Python 3.9+ and: pip install jsonschema
The rulebook (fmjl_rulebook_v0.4.md) is the authority. If this tool and the
rulebook disagree, this tool has a bug.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

VERSION = "0.4"
CONVERTER = "fmjl 0.4"

TYPES = ["heading", "paragraph", "list", "table", "formula", "code", "image", "caption",
         "footnote", "form_field", "annotation", "redaction", "noise", "message", "utterance",
         "record", "citation", "quote", "toc", "group"]
SUBTYPES = {
    "image": ["logo", "stamp", "signature", "chart", "diagram", "photo", "qr_code", "barcode"],
    "noise": ["header", "footer", "watermark", "page_number"],
    "group": ["slide", "sidebar", "figure", "box", "sheet", "thread"],
}
HEADER_ORDER = ["type", "version", "doc", "source", "sha256", "protection", "signed", "converter",
                "structure", "elements", "created", "lang", "access", "title", "authors", "date",
                "summary", "last_id", "meta"]
ELEMENT_ORDER = ["id", "hash", "type", "subtype", "level", "label", "parent", "page", "pages",
                 "bbox", "characters", "reference", "continues", "confidence", "lang", "access",
                 "html", "latex", "file", "meta", "md"]
FRONT_ORDER = ["fmjl", "doc", "title", "authors", "date", "summary", "lang", "access", "source",
               "sha256", "protection", "signed", "converter", "created", "last_id", "meta"]
NOTE_KEYS = ["type", "subtype", "label", "level", "page", "pages", "bbox", "confidence", "lang",
             "access", "reference", "continues", "parent", "file", "meta"]

ID_RE = re.compile(r"^[a-z0-9_-]+#e[1-9][0-9]*$")
SHORT_ID_RE = re.compile(r"^e[1-9][0-9]*$")
LABEL_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)*$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
HEADING_RE = re.compile(r"^(#{1,6})(?:[ \t]|$)")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
IMAGE_RE = re.compile(r"^!\[(.*)\]\((\S+?)\)$", re.S)
NOTE_RE = re.compile(r"^\s*<!--\s*(.*?)\s*-->\s*$", re.S)
SEP_CELL_RE = re.compile(r"^:?-+:?$")
LINK_RE = re.compile(r"\]\(#([a-z0-9_-]+)\)")

SCHEMA = json.loads(r'''{
 "$schema": "https://json-schema.org/draft/2020-12/schema",
 "title": "FMJL line, version 0.4",
 "oneOf": [
  {
   "$ref": "#/$defs/header"
  },
  {
   "$ref": "#/$defs/element"
  }
 ],
 "$defs": {
  "header": {
   "type": "object",
   "required": [
    "type",
    "version",
    "doc",
    "source",
    "sha256",
    "protection",
    "signed",
    "converter",
    "structure",
    "elements",
    "created",
    "lang",
    "access"
   ],
   "properties": {
    "type": {
     "const": "document"
    },
    "version": {
     "type": "string",
     "pattern": "^[0-9]+\\.[0-9]+$"
    },
    "doc": {
     "type": "string",
     "pattern": "^[a-z0-9_-]+$"
    },
    "source": {
     "type": "string",
     "minLength": 1
    },
    "sha256": {
     "type": "string",
     "pattern": "^[0-9a-f]{64}$"
    },
    "protection": {
     "enum": [
      "none",
      "password",
      "certificate",
      "drm"
     ]
    },
    "signed": {
     "type": "boolean"
    },
    "converter": {
     "type": "string",
     "minLength": 1
    },
    "structure": {
     "type": "boolean"
    },
    "elements": {
     "type": [
      "integer",
      "null"
     ],
     "minimum": 0
    },
    "created": {
     "type": "string",
     "format": "date-time"
    },
    "lang": {
     "type": "string",
     "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)*$"
    },
    "access": {
     "type": "array",
     "minItems": 1,
     "items": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]+$"
     }
    },
    "title": {
     "type": "string"
    },
    "authors": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "date": {
     "type": "string",
     "pattern": "^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$"
    },
    "summary": {
     "type": "string"
    },
    "last_id": {
     "type": "integer",
     "minimum": 0
    },
    "meta": {
     "type": "object"
    }
   }
  },
  "element": {
   "type": "object",
   "required": [
    "id",
    "hash",
    "type",
    "parent",
    "characters",
    "md"
   ],
   "properties": {
    "id": {
     "type": "string",
     "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
    },
    "hash": {
     "type": "string",
     "pattern": "^[0-9a-f]{16}$"
    },
    "type": {
     "enum": [
      "heading",
      "paragraph",
      "list",
      "table",
      "formula",
      "code",
      "image",
      "caption",
      "footnote",
      "form_field",
      "annotation",
      "redaction",
      "noise",
      "message",
      "utterance",
      "record",
      "citation",
      "quote",
      "toc",
      "group"
     ]
    },
    "subtype": {
     "type": "string"
    },
    "label": {
     "type": "string",
     "pattern": "^[a-z][a-z0-9_-]*$"
    },
    "level": {
     "type": "integer",
     "minimum": 1,
     "maximum": 6
    },
    "parent": {
     "type": [
      "string",
      "null"
     ],
     "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
    },
    "page": {
     "type": "integer",
     "minimum": 0
    },
    "pages": {
     "type": "array",
     "minItems": 2,
     "items": {
      "type": "integer",
      "minimum": 0
     }
    },
    "bbox": {
     "type": "array",
     "minItems": 4,
     "maxItems": 4,
     "items": {
      "type": "integer",
      "minimum": 0,
      "maximum": 1000
     }
    },
    "characters": {
     "type": "integer",
     "minimum": 0
    },
    "reference": {
     "anyOf": [
      {
       "type": "string",
       "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
      },
      {
       "type": "array",
       "minItems": 2,
       "items": {
        "type": "string",
        "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
       }
      }
     ]
    },
    "continues": {
     "type": "string",
     "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
    },
    "confidence": {
     "type": "number",
     "minimum": 0,
     "maximum": 1
    },
    "lang": {
     "type": "string",
     "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)*$"
    },
    "access": {
     "type": "array",
     "minItems": 1,
     "items": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.:-]+$"
     }
    },
    "html": {
     "type": "string"
    },
    "latex": {
     "type": "string"
    },
    "file": {
     "type": "string",
     "pattern": "^images/[^/]+\\.(png|webp|jpg|jpeg|svg)$"
    },
    "meta": {
     "type": "object"
    },
    "md": {
     "type": "string"
    }
   },
   "dependentRequired": {
    "bbox": [
     "page"
    ]
   },
   "not": {
    "required": [
     "page",
     "pages"
    ]
   },
   "allOf": [
    {
     "if": {
      "required": [
       "type"
      ],
      "properties": {
       "type": {
        "const": "heading"
       }
      }
     },
     "then": {
      "required": [
       "level"
      ]
     }
    },
    {
     "if": {
      "required": [
       "type"
      ],
      "properties": {
       "type": {
        "const": "formula"
       }
      }
     },
     "then": {
      "required": [
       "latex"
      ]
     }
    },
    {
     "if": {
      "required": [
       "type"
      ],
      "properties": {
       "type": {
        "const": "image"
       }
      }
     },
     "then": {
      "required": [
       "file"
      ],
      "properties": {
       "subtype": {
        "enum": [
         "logo",
         "stamp",
         "signature",
         "chart",
         "diagram",
         "photo",
         "qr_code",
         "barcode"
        ]
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "type"
      ],
      "properties": {
       "type": {
        "const": "noise"
       }
      }
     },
     "then": {
      "required": [
       "subtype"
      ],
      "properties": {
       "subtype": {
        "enum": [
         "header",
         "footer",
         "watermark",
         "page_number"
        ]
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "type"
      ],
      "properties": {
       "type": {
        "const": "group"
       }
      }
     },
     "then": {
      "required": [
       "subtype"
      ],
      "properties": {
       "subtype": {
        "enum": [
         "slide",
         "sidebar",
         "figure",
         "box",
         "sheet",
         "thread"
        ]
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "level"
      ]
     },
     "then": {
      "properties": {
       "type": {
        "const": "heading"
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "html"
      ]
     },
     "then": {
      "properties": {
       "type": {
        "const": "table"
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "latex"
      ]
     },
     "then": {
      "properties": {
       "type": {
        "const": "formula"
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "file"
      ]
     },
     "then": {
      "properties": {
       "type": {
        "const": "image"
       }
      }
     }
    },
    {
     "if": {
      "required": [
       "subtype"
      ]
     },
     "then": {
      "properties": {
       "type": {
        "enum": [
         "image",
         "noise",
         "group"
        ]
       }
      }
     }
    }
   ]
  }
 }
}''')


def element_hash(type_, md):
    """First 16 hex characters of SHA-256 over `type`, a newline, then `md` (rulebook 7.2)."""
    return hashlib.sha256((type_ + "\n" + md).encode("utf-8")).hexdigest()[:16]


def id_number(id_):
    return int(id_.rsplit("#e", 1)[1])


def short_id(id_, doc):
    return id_[len(doc) + 1:] if isinstance(id_, str) and id_.startswith(doc + "#") else id_


def dumps(row):
    """One storage-form line, keys in the standard order, no trailing newline."""
    order = HEADER_ORDER if row.get("type") == "document" else ELEMENT_ORDER
    known = [k for k in order if k in row]
    extra = [k for k in row if k not in order and not k.startswith("_")]
    if row.get("type") != "document" and known and known[-1] == "md":
        keys = known[:-1] + extra + ["md"]
    else:
        keys = known + extra
    return json.dumps({k: row[k] for k in keys}, ensure_ascii=False, separators=(",", ":"))


def read_rows(path):
    """Read a storage-form file into a list of dicts. Raises ValueError with the line number."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"line {i}: not valid JSON: {e.msg} at column {e.colno}") from None
            if not isinstance(obj, dict):
                raise ValueError(f"line {i}: must be one JSON object")
            rows.append(obj)
    if not rows:
        raise ValueError("line 1: file has no lines")
    return rows


def write_rows(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


def _split_row(line):
    """Split one Markdown table row into cells. `\\|` stays inside a cell."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, i = [], [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("\\|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _pipe_row(cells):
    return "| " + " | ".join(cells) + " |"


def _sep_cell(cell):
    left, right = cell.startswith(":"), cell.endswith(":")
    return (":" if left else "") + "---" + (":" if right else "")


class _TableParser(HTMLParser):
    """Turns <table> HTML into a grid of cell texts, repeating merged cells (rulebook 8.6)."""

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.span = [], None, None, (1, 1)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
            self.span = (int(a.get("rowspan") or 1), int(a.get("colspan") or 1))
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            self.row.append((text, self.span))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def grid(self):
        grid, pending = [], {}
        for r, row in enumerate(self.rows):
            line, c, cells = [], 0, list(row)
            while cells or (r, c) in pending:
                if (r, c) in pending:
                    line.append(pending.pop((r, c)))
                    c += 1
                    continue
                text, (rs, cs) = cells.pop(0)
                for dc in range(cs):
                    line.append(text)
                    for dr in range(1, rs):
                        pending[(r + dr, c + dc)] = text
                c += cs
            grid.append(line)
        width = max((len(l) for l in grid), default=0)
        return [l + [""] * (width - len(l)) for l in grid]


def html_table_to_md(html):
    p = _TableParser()
    p.feed(html)
    grid = p.grid()
    if not grid:
        return ""
    lines = [_pipe_row(grid[0]), _pipe_row(["---"] * len(grid[0]))]
    lines += [_pipe_row(r) for r in grid[1:]]
    return "\n".join(lines)


def canonical_md(type_, md, latex=None, html=None):
    """Rewrite `md` into canonical form (rulebook section 8). Idempotent."""
    if type_ == "code":
        return md
    if type_ == "formula" and latex is not None:
        return "$$" + latex + "$$"
    if type_ == "table" and html:
        return html_table_to_md(html)
    text = md.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out = []
    for ln in lines:
        if ln.strip() and ln.endswith("  "):
            ln = ln.rstrip() + "\\"
        else:
            ln = ln.rstrip()
        out.append(ln)
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    if out and out[-1].endswith("\\") and len(out) == 1:
        pass
    if type_ == "heading" and out:
        m = re.match(r"^(#{1,6})\s*(.*)$", out[0])
        if m:
            text = re.sub(r"(?:^|\s)#+$", "", m.group(2)).strip()
            out[0] = m.group(1) + (" " + text if text else "")
    if type_ in ("list", "form_field"):
        out = [re.sub(r"^(\s*)[*+](\s)", r"\1-\2", ln) for ln in out]
    if type_ == "table" and out and all(ln.lstrip().startswith("|") for ln in out):
        rows = [_split_row(ln) for ln in out]
        if len(rows) > 1 and all(SEP_CELL_RE.match(c) for c in rows[1]):
            rows[1] = [_sep_cell(c) for c in rows[1]]
        out = [_pipe_row(r) for r in rows]
    return "\n".join(out)


class _Parents:
    """Default parent rule (rulebook 7.4.2): nearest heading above with a lower level;
    inside a group, the group or a heading inside that group. Frames hold row dicts."""

    def __init__(self):
        self.frames = [[None, []]]

    def default(self, row):
        group, heads = self.frames[-1]
        if row.get("type") == "heading":
            level = row.get("level") or 1
            for lvl, h in reversed(heads):
                if lvl < level:
                    return h
            return group
        return heads[-1][1] if heads else group

    def add(self, row):
        if row.get("type") == "heading":
            level = row.get("level") or 1
            heads = self.frames[-1][1]
            while heads and heads[-1][0] >= level:
                heads.pop()
            heads.append((level, row))

    def open_group(self, row):
        self.frames.append([row, []])

    def close_group(self):
        if len(self.frames) > 1:
            self.frames.pop()


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fill(rows, doc=None, base=None):
    """Fill in id, hash, characters and parent, make md canonical, complete the header.
    Returns new rows; the input is not changed."""
    rows = [dict(r) for r in rows]
    if not rows or rows[0].get("type") != "document":
        raise ValueError("line 1 must be the header line with \"type\":\"document\"")
    h = rows[0]
    doc = h.get("doc") or doc
    if not doc:
        raise ValueError("the header needs 'doc' (a short document name)")
    h["doc"] = doc
    els = rows[1:]

    used = {id_number(e["id"]) for e in els if isinstance(e.get("id"), str) and ID_RE.match(e["id"])}
    last = max([h.get("last_id") or 0] + sorted(used))
    for e in els:
        if not (isinstance(e.get("id"), str) and ID_RE.match(e["id"])):
            last += 1
            e["id"] = f"{doc}#e{last}"

    tracker = _Parents()
    for e in els:
        t = e.get("type") if e.get("type") in TYPES else "paragraph"
        e["type"] = t
        md = e.get("md", "") if isinstance(e.get("md"), str) else ""
        if t == "heading":
            m = HEADING_RE.match(md)
            if not isinstance(e.get("level"), int):
                e["level"] = len(m.group(1)) if m else 1
            if not m:
                md = "#" * e["level"] + " " + md.strip()
        if t == "formula" and not isinstance(e.get("latex"), str):
            e["latex"] = _strip_dollars(md)
        e["md"] = canonical_md(t, md, e.get("latex"), e.get("html"))
        if "parent" not in e:
            p = tracker.default(e)
            e["parent"] = p["id"] if p else None
        tracker.add(e)
        e["hash"] = element_hash(t, e["md"])
        e["characters"] = len(e["md"])
        for k in [k for k in e if k.startswith("_")]:
            del e[k]

    h.setdefault("version", VERSION)
    h.setdefault("source", doc + ".md")
    if not h.get("sha256"):
        src = Path(base or ".") / h["source"]
        if src.is_file():
            h["sha256"] = _sha256_file(src)
        else:
            digest = hashlib.sha256()
            for e in els:
                digest.update((e["type"] + "\n" + e["md"] + "\n").encode("utf-8"))
            h["sha256"] = digest.hexdigest()
    h.setdefault("protection", "none")
    h.setdefault("signed", False)
    h.setdefault("converter", CONVERTER)
    has_heading = any(e["type"] == "heading" for e in els)
    h["structure"] = bool(h.get("structure")) or has_heading
    h["elements"] = len(els)
    h.setdefault("created", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    h.setdefault("lang", "en")
    h.setdefault("access", ["all"])
    h["last_id"] = last
    return rows


def _strip_dollars(md):
    s = md.strip()
    if s.startswith("$$"):
        s = s[2:]
    if s.endswith("$$"):
        s = s[:-2]
    return s.strip("\n").strip() if "\n" not in s.strip() else s.strip("\n")


def _parse_note(line):
    """Returns (kind, attrs) for a note line, or None when the line is not a note.
    kind: 'note', 'group', 'endgroup', 'end' (attrs holds the name for 'end')."""
    m = NOTE_RE.match(line)
    if not m or "\n" in line.strip():
        return None
    body = m.group(1)
    if body.startswith("/"):
        name = body[1:].strip()
        if not name or " " in name:
            return None
        return ("endgroup", {}) if name == "group" else ("end", {"name": name})
    meta = None
    k = re.search(r"(^|\s)meta=", body)
    if k:
        try:
            meta = json.loads(body[k.end():])
        except json.JSONDecodeError:
            return None
        if not isinstance(meta, dict):
            return None
        body = body[:k.start()]
    toks = body.split()
    kind, attrs = "note", {}
    if toks and toks[0] == "group":
        kind = "group"
        toks = toks[1:]
    if toks and SHORT_ID_RE.match(toks[0]):
        attrs["_id"] = toks[0]
        toks = toks[1:]
    elif kind == "note" and not toks:
        return None
    for tok in toks:
        if "=" not in tok:
            return None
        key, val = tok.split("=", 1)
        if key not in NOTE_KEYS:
            return None
        attrs[key] = val
    if meta is not None:
        attrs["meta"] = meta
    return kind, attrs


def _detect(block):
    s = block.lstrip()
    if HEADING_RE.match(s):
        return "heading"
    if FENCE_RE.match(block):
        return "code"
    if s.startswith("|") or s.lower().startswith("<table"):
        return "table"
    if s.startswith("$$"):
        return "formula"
    if "\n" not in block.strip() and IMAGE_RE.match(block.strip()):
        return "image"
    if s.startswith(">"):
        return "quote"
    if re.match(r"^([-*+]|\d+[.)])\s", s):
        return "list"
    return "paragraph"


def _read_block(lines, i):
    """Read one Markdown block starting at lines[i]. Returns (text, next_index)."""
    ln = lines[i]
    s = ln.lstrip()
    m = FENCE_RE.match(ln)
    if m:
        fence = m.group(1)
        j = i + 1
        while j < len(lines):
            mm = FENCE_RE.match(lines[j])
            if mm and mm.group(1)[0] == fence[0] and len(mm.group(1)) >= len(fence) \
                    and not lines[j].strip()[len(mm.group(1)):].strip():
                return "\n".join(lines[i:j + 1]), j + 1
            j += 1
        return "\n".join(lines[i:]), len(lines)
    if s.lower().startswith("<table"):
        j = i
        while j < len(lines) and "</table>" not in lines[j].lower():
            j += 1
        return "\n".join(lines[i:j + 1]), j + 1
    if s.startswith("$$"):
        if len(s.strip()) >= 4 and s.strip().endswith("$$"):
            return ln, i + 1
        j = i + 1
        while j < len(lines) and not lines[j].rstrip().endswith("$$"):
            j += 1
        return "\n".join(lines[i:j + 1]), j + 1
    if HEADING_RE.match(s):
        return ln, i + 1
    j = i + 1
    while j < len(lines):
        nxt = lines[j]
        if not nxt.strip() or _parse_note(nxt) or FENCE_RE.match(nxt) or HEADING_RE.match(nxt.lstrip()):
            break
        j += 1
    return "\n".join(lines[i:j]), j


def _find_end(lines, i, name):
    """Index of the matching `<!-- /name -->` line, skipping fenced code, or None."""
    j, fence = i, None
    while j < len(lines):
        ln = lines[j]
        m = FENCE_RE.match(ln)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
        elif m:
            fence = m.group(1)
        else:
            note = _parse_note(ln)
            if note:
                if note[0] == "end" and note[1]["name"] == name:
                    return j
                if note[0] != "end":
                    return None
        j += 1
    return None


def _split_front(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end == -1:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            return {}, text
    front, body = text[4:end], text[end + 5:]
    fields = {}
    for ln in front.split("\n"):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if ":" not in ln:
            raise ValueError(f"front matter line '{ln}' needs the form key: value")
        key, raw = ln.split(":", 1)
        fields[key.strip()] = _front_value(key.strip(), raw.strip())
    return fields, body


def _front_value(key, raw):
    if key == "fmjl":
        return raw.strip('"')
    if raw.startswith('"') or raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    if key == "authors":
        return [a.strip() for a in raw.split(",") if a.strip()]
    if raw in ("true", "false"):
        return raw == "true"
    if raw == "null":
        return None
    if key in ("last_id", "elements") and re.match(r"^-?\d+$", raw):
        return int(raw)
    return raw


def _ref(value, doc):
    return doc + "#" + value if SHORT_ID_RE.match(value) else value


def _apply_note(row, attrs, doc):
    for key, val in attrs.items():
        if key in ("_id", "type"):
            continue
        if key == "page":
            row["page"] = int(val)
        elif key in ("pages", "bbox"):
            row[key] = [int(v) for v in val.split(",") if v != ""]
        elif key == "confidence":
            row["confidence"] = float(val)
        elif key == "access":
            row["access"] = [v for v in val.split(",") if v]
        elif key == "reference":
            refs = [_ref(v, doc) for v in val.split(",") if v]
            row["reference"] = refs[0] if len(refs) == 1 else refs
        elif key in ("continues", "parent"):
            row[key] = None if val == "null" else _ref(val, doc)
        elif key == "level":
            row["level"] = int(val)
        else:
            row[key] = val


def _make_element(block, attrs, doc):
    t = attrs.get("type") or _detect(block)
    row = {"type": t}
    detected = _detect(block)
    if t == "heading":
        m = HEADING_RE.match(block.lstrip())
        row["level"] = len(m.group(1)) if m else 1
        md = block.strip()
    elif t == "image" and detected == "image":
        m = IMAGE_RE.match(block.strip())
        row["file"] = m.group(2)
        md = m.group(1)
    elif t == "formula" and detected == "formula":
        latex = _strip_dollars(block)
        row["latex"] = latex
        md = "$$" + latex + "$$"
    elif t == "table" and block.lstrip().lower().startswith("<table"):
        row["html"] = block.strip()
        md = html_table_to_md(row["html"])
    else:
        md = block
    row["md"] = md
    _apply_note(row, attrs, doc)
    if "_id" in attrs:
        row["id"] = doc + "#" + attrs["_id"]
    return row


def import_md(text, doc=None, source=None, base=None):
    """Authoring form -> filled storage rows (header first)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    front, body = _split_front(text)
    h = {"type": "document"}
    for k, v in front.items():
        h["version" if k == "fmjl" else k] = v
    doc = h.get("doc") or doc
    if not doc:
        raise ValueError("no document name: add 'doc: my_doc' to the front matter")
    h["doc"] = doc
    if source and not h.get("source"):
        h["source"] = source

    lines = body.split("\n")
    els, tracker, groups = [], _Parents(), []
    pending, pending_group = None, None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        note = _parse_note(ln)
        if note:
            kind, attrs = note
            i += 1
            if kind == "group":
                pending_group = attrs
            elif kind == "endgroup":
                if groups:
                    groups.pop()
                    tracker.close_group()
            elif kind == "note":
                name = attrs.get("_id") or attrs.get("label")
                j = _find_end(lines, i, name) if name else None
                if j is not None:
                    row = _make_element("\n".join(lines[i:j]).strip("\n"), attrs, doc)
                    _place(row, tracker, els)
                    i = j + 1
                else:
                    pending = attrs
            continue
        block, i = _read_block(lines, i)
        if pending_group is not None:
            attrs, pending_group = pending_group, None
            row = _make_element(block, dict(attrs, type="group"), doc)
            row["md"] = block.strip()
            for k in ("file", "latex", "html", "level"):
                row.pop(k, None)
            _place(row, tracker, els)
            tracker.open_group(row)
            groups.append(row)
        else:
            row = _make_element(block, pending or {}, doc)
            pending = None
            _place(row, tracker, els)

    used = {id_number(e["id"]) for e in els if "id" in e}
    seen = set()
    for e in els:
        if "id" in e:
            if e["id"] in seen:
                raise ValueError(f"id {e['id']} is used twice in the notes")
            seen.add(e["id"])
    last = max([h.get("last_id") or 0] + sorted(used))
    for e in els:
        if "id" not in e:
            last += 1
            e["id"] = f"{doc}#e{last}"
    h["last_id"] = last
    labels = {e["label"]: e["id"] for e in els if isinstance(e.get("label"), str)}

    def resolve(v):
        if isinstance(v, str) and not ID_RE.match(v) and v in labels:
            return labels[v]
        return v

    for e in els:
        p = e.pop("_parent_row", None)
        if "parent" in e:
            e["parent"] = resolve(e["parent"])
        else:
            e["parent"] = p["id"] if p else None
        if "reference" in e:
            r = e["reference"]
            e["reference"] = resolve(r) if isinstance(r, str) else [resolve(x) for x in r]
        if "continues" in e:
            e["continues"] = resolve(e["continues"])
    return fill([h] + els, base=base)


def _place(row, tracker, els):
    row["_parent_row"] = tracker.default(row)
    tracker.add(row)
    els.append(row)


def _needs_quotes(v):
    return (v == "" or v != v.strip() or "\n" in v or ": " in v or ", " in v or v.endswith(":")
            or v[0] in "\"'[{#&*!|>%@`" or v in ("true", "false", "null")
            or re.match(r"^-?\d+(\.\d+)?$", v) is not None)


def _front_text(key, v):
    if key == "fmjl":
        return json.dumps(v)
    if key == "authors" and isinstance(v, list) and all(isinstance(a, str) and "," not in a for a in v):
        return ", ".join(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False) if _needs_quotes(v) else v


def _render_block(e):
    t = e["type"]
    if t == "image":
        return f"![{e.get('md', '')}]({e.get('file', '')})"
    if t == "formula":
        latex = e["latex"] if isinstance(e.get("latex"), str) else _strip_dollars(e.get("md", ""))
        return "$$" + latex + "$$" if "\n" not in latex else "$$\n" + latex + "\n$$"
    if t == "table" and isinstance(e.get("html"), str) and e["html"]:
        return e["html"]
    return e.get("md", "")


def _inside(e, group_id, by_id):
    p, steps = e.get("parent"), 0
    while isinstance(p, str) and steps < 10000:
        if p == group_id:
            return True
        p = by_id.get(p, {}).get("parent")
        steps += 1
    return False


def _note_attrs(e, doc, default_parent, block):
    parts = []
    if e["type"] != "group" and _detect(block) != e["type"]:
        parts.append("type=" + e["type"])
    for k in ("subtype", "label"):
        if k in e:
            parts.append(f"{k}={e[k]}")
    if "page" in e:
        parts.append(f"page={e['page']}")
    if "pages" in e:
        parts.append("pages=" + ",".join(str(p) for p in e["pages"]))
    if "bbox" in e:
        parts.append("bbox=" + ",".join(str(p) for p in e["bbox"]))
    if "confidence" in e:
        parts.append("confidence=" + json.dumps(e["confidence"]))
    if "lang" in e:
        parts.append("lang=" + e["lang"])
    if "access" in e:
        parts.append("access=" + ",".join(e["access"]))
    if "reference" in e:
        refs = e["reference"] if isinstance(e["reference"], list) else [e["reference"]]
        parts.append("reference=" + ",".join(short_id(r, doc) for r in refs))
    if "continues" in e:
        parts.append("continues=" + short_id(e["continues"], doc))
    if e.get("parent") != (default_parent["id"] if default_parent else None):
        parts.append("parent=" + (short_id(e["parent"], doc) if e.get("parent") else "null"))
    if "meta" in e:
        parts.append("meta=" + json.dumps(e["meta"], ensure_ascii=False, separators=(",", ":")))
    return parts


def export_md(rows):
    """Storage rows -> authoring form text."""
    h, els = rows[0], rows[1:]
    doc = h["doc"]
    out = ["---"]
    front = dict(h)
    front["fmjl"] = front.pop("version", VERSION)
    for k in FRONT_ORDER:
        if k in front:
            out.append(f"{k}: {_front_text(k, front[k])}")
    for k in front:
        if k not in FRONT_ORDER and k not in ("type", "structure", "elements"):
            out.append(f"{k}: {_front_text(k, front[k])}")
    out += ["---", ""]

    by_id = {e["id"]: e for e in els if isinstance(e.get("id"), str)}
    tracker, open_groups = _Parents(), []
    for e in els:
        while open_groups and not _inside(e, open_groups[-1]["id"], by_id):
            out += ["<!-- /group -->", ""]
            open_groups.pop()
            tracker.close_group()
        block = _render_block(e)
        attrs = [short_id(e["id"], doc)] + _note_attrs(e, doc, tracker.default(e), block)
        if e["type"] == "group":
            out += ["<!-- group " + " ".join(attrs) + " -->", block, ""]
            tracker.add(e)
            tracker.open_group(e)
            open_groups.append(e)
        else:
            out += ["<!-- " + " ".join(attrs) + " -->", block]
            if "\n\n" in block and e["type"] != "code":
                out.append(f"<!-- /{short_id(e['id'], doc)} -->")
            out.append("")
            tracker.add(e)
    while open_groups:
        out += ["<!-- /group -->", ""]
        open_groups.pop()
    return "\n".join(out)


_ALLOF_MSG = {
    0: "a heading needs \"level\":1..6",
    1: "a formula needs \"latex\"",
    2: "an image needs \"file\":\"images/...\" and a subtype from: " + ", ".join(SUBTYPES["image"]),
    3: "noise needs a subtype from: " + ", ".join(SUBTYPES["noise"]),
    4: "a group needs a subtype from: " + ", ".join(SUBTYPES["group"]),
    5: "level (1..6) is only for headings",
    6: "html is only for tables",
    7: "latex is only for formulas",
    8: "file is only for images",
    9: "subtype is only for image, noise and group",
}


def _schema_errors(obj, kind):
    from jsonschema import Draft202012Validator
    schema = {"$defs": SCHEMA["$defs"], "$ref": "#/$defs/" + kind}
    for err in Draft202012Validator(schema).iter_errors(obj):
        path = list(err.absolute_schema_path)
        field = "/".join(str(p) for p in err.absolute_path)
        if err.validator == "required":
            missing = re.match(r"'(.+?)' is a required property", err.message)
            name = missing.group(1) if missing else "a field"
            if path and path[0] == "allOf" and path[1] in _ALLOF_MSG:
                yield _ALLOF_MSG[path[1]]
            else:
                yield f"missing '{name}' (run: python fmjl.py fill)"
        elif err.validator == "not":
            yield "use page or pages, never both"
        elif err.validator == "dependentRequired":
            yield "bbox is allowed only together with page"
        elif path and path[0] == "allOf" and path[1] in _ALLOF_MSG:
            yield _ALLOF_MSG[path[1]]
        else:
            yield f"{field}: {err.message}" if field else err.message


def check_rows(numbered, base=None):
    """Whole-document checks. `numbered` is a list of (line_number, row)."""
    errors = []
    add = lambda line, msg: errors.append(f"line {line}: {msg}")
    first_line, h = numbered[0]
    if h.get("type") != "document":
        add(first_line, 'line 1 must be the header line with "type":"document"')
        h = {}
    else:
        for msg in _schema_errors(h, "header"):
            add(first_line, msg)
        if isinstance(h.get("created"), str) and not DATETIME_RE.match(h["created"]):
            add(first_line, "created must be an ISO 8601 date-time in UTC, like 2026-09-26T10:30:00Z")
    doc = h.get("doc") if isinstance(h.get("doc"), str) else None
    els = [(n, r) for n, r in numbered[1:]]

    by_id, pos, lineof, labels = {}, {}, {}, {}
    for index, (n, e) in enumerate(els):
        if e.get("type") == "document":
            add(n, "only line 1 may be a header")
            continue
        for msg in _schema_errors(e, "element"):
            add(n, msg)
        i = e.get("id")
        if isinstance(i, str) and ID_RE.match(i):
            if doc and not i.startswith(doc + "#"):
                add(n, f"id must start with {doc}#")
            if i in by_id:
                add(n, f"id {i} is used twice")
            by_id[i], pos[i], lineof[i] = e, index, n
            if isinstance(h.get("last_id"), int) and id_number(i) > h["last_id"]:
                add(n, "id number is higher than last_id in the header")
        lab = e.get("label")
        if isinstance(lab, str) and LABEL_RE.match(lab):
            if lab in labels:
                add(n, f"label {lab} is used twice")
            labels[lab] = i
        if isinstance(e.get("reference"), list) and len(e["reference"]) == 1:
            add(n, "a single reference must be a string, not a list")
        md, t = e.get("md"), e.get("type")
        if isinstance(md, str) and isinstance(t, str) and t in TYPES:
            canon = canonical_md(t, md, e.get("latex") if isinstance(e.get("latex"), str) else None,
                                 e.get("html") if isinstance(e.get("html"), str) else None)
            if canon != md:
                add(n, "md is not canonical Markdown (run: python fmjl.py fill)")
            if isinstance(e.get("hash"), str) and e["hash"] != element_hash(t, md):
                add(n, "hash is wrong (run: python fmjl.py fill)")
            if isinstance(e.get("characters"), int) and e["characters"] != len(md):
                add(n, f"characters should be {len(md)}")
            if t == "heading" and isinstance(e.get("level"), int):
                m = HEADING_RE.match(md)
                if not m or len(m.group(1)) != e["level"]:
                    add(n, f"level {e['level']} does not match the #'s in md")
        if isinstance(e.get("file"), str) and base is not None and t == "image":
            if not (Path(base) / e["file"]).is_file():
                add(n, f"file {e['file']} does not exist next to the .fmjl file")

    for index, (n, e) in enumerate(els):
        if e.get("type") == "document":
            continue
        p = e.get("parent")
        if isinstance(p, str):
            if p not in by_id:
                add(n, f"parent {p} does not exist")
            elif pos[p] >= index:
                add(n, "parent must come before the element")
            else:
                par = by_id[p]
                if par.get("type") not in ("heading", "group"):
                    add(n, "parent must be a heading or a group")
                elif e.get("type") == "heading" and par.get("type") == "heading" \
                        and (par.get("level") or 0) >= (e.get("level") or 0):
                    add(n, "a heading's parent must be a heading with a smaller level")
        refs = e.get("reference")
        for r in ([refs] if isinstance(refs, str) else refs if isinstance(refs, list) else []):
            if r not in by_id:
                add(n, f"reference {r} does not exist")
        c = e.get("continues")
        if isinstance(c, str):
            if c not in by_id or pos[c] >= index:
                add(n, "continues must point to an earlier element")
            elif by_id[c].get("type") != e.get("type"):
                add(n, "continues must point to an element of the same type")
        md = e.get("md")
        if isinstance(md, str) and e.get("type") != "code":
            no_code = re.sub(r"^ {0,3}(`{3,}|~{3,})[\s\S]*?^ {0,3}\1", "", md, flags=re.M)
            no_code = re.sub(r"(`+)[\s\S]*?\1", "", no_code)
            for m in LINK_RE.finditer(no_code):
                target = m.group(1)
                if (doc or "") + "#" + target not in by_id and target not in labels:
                    add(n, f"link to #{target} points to no element or label")
    count = sum(1 for _, e in els if e.get("type") != "document")
    if isinstance(h.get("elements"), int) and h["elements"] != count:
        add(first_line, f"elements says {h['elements']} but the file has {count}")
    elif h and h.get("elements") is None and "elements" in h:
        add(first_line, "elements is null: the file is not finished (run: python fmjl.py fill)")
    errors.sort(key=lambda s: int(s.split(":")[0][5:]))
    return errors


def check(path):
    """Check a storage-form file. Returns a list of 'line N: message' strings (empty = passed)."""
    path = Path(path)
    errors = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return [f"line 1: the file is not UTF-8 ({e.reason} at byte {e.start})"]
    if text.startswith("﻿"):
        errors.append("line 1: remove the byte-order mark at the start of the file")
        text = text[1:]
    if "\r" in text:
        line = text[:text.index("\r")].count("\n") + 1
        errors.append(f"line {line}: lines must end with \\n only, not \\r\\n")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        errors.append(f"line {text.count(chr(10)) + 1}: the last line must end with a newline")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    numbered = []
    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            errors.append(f"line {i}: empty line (not allowed; delete it)")
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: not valid JSON: {e.msg} at column {e.colno}")
            continue
        if not isinstance(obj, dict):
            errors.append(f"line {i}: must be one JSON object {{...}}")
            continue
        numbered.append((i, obj))
    if not numbered:
        errors.append("line 1: file has no valid lines")
        return errors
    errors += check_rows(numbered, base=path.parent)
    errors.sort(key=lambda s: int(s.split(":")[0][5:]))
    return errors


def view_text(rows):
    return "\n\n".join(_render_block(e) for e in rows[1:] if e.get("type") != "noise") + "\n"


def info_text(rows):
    h, els = rows[0], rows[1:]
    out = [f"{h.get('title') or h.get('doc')}  (doc: {h.get('doc')}, version {h.get('version')})"]
    if h.get("authors"):
        out.append("authors: " + ", ".join(h["authors"]))
    for k in ("date", "source", "lang", "created"):
        if h.get(k):
            out.append(f"{k}: {h[k]}")
    counts = {}
    for e in els:
        counts[e.get("type")] = counts.get(e.get("type"), 0) + 1
    chars = sum(e.get("characters", 0) for e in els if isinstance(e.get("characters"), int))
    out.append(f"elements: {len(els)}  ({chars} characters)")
    for t in TYPES:
        if t in counts:
            out.append(f"  {t:<11}{counts[t]}")
    out.append("outline:")
    for e in els:
        if e.get("type") == "heading":
            text = re.sub(r"^#{1,6}\s*", "", e.get("md", ""))
            out.append("  " * (e.get("level", 1) - 1) + f"- {text}  [{short_id(e['id'], h['doc'])}]")
        elif e.get("type") == "group":
            out.append(f"  - ({e.get('subtype')} group) {e.get('md', '')}  [{short_id(e['id'], h['doc'])}]")
    return "\n".join(out) + "\n"


def upgrade_rows(rows, base=None):
    h = rows[0]
    old = h.get("version")
    if old not in (None, "0.1", "0.2", "0.3", "0.4"):
        raise ValueError(f"cannot upgrade version {old}; this tool knows 0.1 to 0.4")
    h["version"] = VERSION
    if old != VERSION:
        h["converter"] = f"{h.get('converter', 'unknown')}; upgraded by {CONVERTER}"
    before = {e.get("id"): e.get("hash") for e in rows[1:]}
    rows = fill(rows, base=base)
    changed = sum(1 for e in rows[1:] if before.get(e["id"]) != e["hash"])
    return rows, changed


def _out(path, suffix, override):
    return Path(override) if override else Path(path).with_suffix(suffix)


def _report(errors):
    for e in errors:
        print(e)
    if errors:
        print(f"FAILED: {len(errors)} error{'s' if len(errors) != 1 else ''}")
        return 1
    print("PASSED")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fmjl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_ in [("new", "authoring form (.md) -> storage form (.fmjl)"),
                        ("md", "storage form (.fmjl) -> authoring form (.md)"),
                        ("fill", "fill id, hash, characters, parent; canonical md (in place)"),
                        ("check", "check every rule; print errors with line numbers"),
                        ("view", "print the document as clean Markdown"),
                        ("info", "print title, element counts and an outline"),
                        ("upgrade", "turn a version 0.1, 0.2 or 0.3 file into version 0.4")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("file")
        if name in ("new", "md", "upgrade"):
            p.add_argument("-o", "--output", help="output file (default: same name, other extension)")
        if name == "new":
            p.add_argument("--doc", help="document name when the front matter has none")
    a = ap.parse_args(argv)
    path = Path(a.file)
    try:
        if a.cmd == "new":
            text = path.read_text(encoding="utf-8")
            doc = a.doc or re.sub(r"[^a-z0-9_-]+", "_", path.stem.lower()).strip("_")
            rows = import_md(text, doc=doc, source=path.name, base=path.parent)
            out = _out(path, ".fmjl", a.output)
            write_rows(out, rows)
            print(f"wrote {out} ({len(rows) - 1} elements)")
            return _report(check(out))
        if a.cmd == "md":
            rows = read_rows(path)
            out = _out(path, ".md", a.output)
            out.write_text(export_md(rows), encoding="utf-8", newline="\n")
            print(f"wrote {out}")
            return 0
        if a.cmd == "fill":
            rows = fill(read_rows(path), doc=re.sub(r"[^a-z0-9_-]+", "_", path.stem.lower()),
                        base=path.parent)
            write_rows(path, rows)
            print(f"filled {path} ({len(rows) - 1} elements)")
            return _report(check(path))
        if a.cmd == "check":
            return _report(check(path))
        if a.cmd == "view":
            sys.stdout.write(view_text(read_rows(path)))
            return 0
        if a.cmd == "info":
            sys.stdout.write(info_text(read_rows(path)))
            return 0
        if a.cmd == "upgrade":
            rows, changed = upgrade_rows(read_rows(path), base=path.parent)
            out = _out(path, ".fmjl", a.output)
            write_rows(out, rows)
            print(f"wrote {out} as version {VERSION}; {changed} element hash(es) changed")
            return _report(check(out))
    except (ValueError, OSError) as e:
        print(f"error: {e}")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
