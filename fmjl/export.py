#!/usr/bin/env python3
"""fmjl.export - writes a .fmjl document in another format, rulebook version 1.1.

  fmjl export report.fmjl --to docx          writes report.docx
  fmjl export report.fmjl --to pdf -o out.pdf

Formats:
  md      clean Markdown without id notes; merged-cell tables as HTML
  html    one page with the images inside it; formulas as LaTeX, shown with MathJax when online
  pdf     that page printed with PyMuPDF (pip install pymupdf)
  docx    Word, made from that page by pandoc (https://pandoc.org); formulas become Word equations
  odt     OpenDocument text, by pandoc
  epub    e-book, by pandoc
Parts of a paragraph linked with continues become one paragraph again, and noise is left out.
What only FMJL holds stays in the .fmjl: ids, hashes, page and bbox, access.

Copyright (c) 2026 Rupak Kumar. MIT License, see LICENSE.
"""
from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import fmjl

FORMATS = ("md", "html", "pdf", "docx", "odt", "epub")
PANDOC = ("docx", "odt", "epub")
DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_RE = re.compile(r"(?<![\\$])\$([^\s$](?:[^$\n]*?[^\s$])?)\$(?![\d$])")
CSS = """body { font-family: Georgia, serif; line-height: 1.55; max-width: 46em; margin: 2em auto; padding: 0 1em; color: #222; }
h1, h2, h3, h4 { font-family: Helvetica, Arial, sans-serif; line-height: 1.25; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 4px 8px; vertical-align: top; }
th { background: #eee; }
img { max-width: 100%; }
figcaption, .caption { color: #555; font-size: 0.9em; }
blockquote { border-left: 3px solid #ccc; margin-left: 0; padding-left: 1em; color: #444; }
pre { background: #f5f5f5; padding: 0.6em; overflow-x: auto; }
"""


def blocks(rows):
    """The elements to show, in order: noise left out, parts linked with continues joined."""
    els = [e for e in rows[1:] if e.get("type") != "noise"]
    units, _ = fmjl._join_parts(els)
    return [{k: v for k, v in u.items() if k != "_parts"} for u in units]


def _image_path(e, base, out_dir):
    f = e.get("file", "")
    if not f or re.match(r"^[a-z]+:", f, re.I) or out_dir is None:
        return f
    try:
        return Path(os.path.relpath(Path(base) / f, out_dir)).as_posix()
    except ValueError:
        return (Path(base) / f).resolve().as_posix()


def to_md(rows, base=".", out_dir=None):
    """Clean Markdown: the text of every element, image paths relative to out_dir."""
    out = []
    for e in blocks(rows):
        if e["type"] == "image":
            out.append(f"![{e.get('md', '')}]({_image_path(e, base, out_dir)})")
        elif e["type"] == "table" and isinstance(e.get("html"), str) and e["html"]:
            out.append(e["html"])
        else:
            out.append(fmjl._render_block(e))
    return "\n\n".join(out) + "\n"


def _math(text, display_only=False):
    """Formulas become the spans pandoc and MathJax read as math; the rest is left as it is."""
    found = []

    def keep(m, display):
        found.append((display, m.group(1).strip()))
        return f"\ue001{len(found) - 1}\ue001"

    text = DISPLAY_RE.sub(lambda m: keep(m, True), text)
    if not display_only:
        text = INLINE_RE.sub(lambda m: keep(m, False), text)
    return text, found


def _math_html(latex, display, dollars):
    tex = html.escape(latex, quote=False)
    if dollars:
        return f"$${tex}$$" if display else f"${tex}$"
    return f'<span class="math display">\\[{tex}\\]</span>' if display else f'<span class="math inline">\\({tex}\\)</span>'


def _put_math(rendered, found, dollars=False):
    def span(m):
        display, latex = found[int(m.group(1))]
        return _math_html(latex, display, dollars)
    return re.sub("\ue001(\\d+)\ue001", span, rendered)


def _data_uri(path):
    kind = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return f"data:{kind};base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def to_html(rows, base=".", embed=True, dollars=False):
    """One HTML page. With embed, images are put inside the page; otherwise they are linked
    relative to base. With dollars, formulas are written as $...$ for pandoc's
    tex_math_dollars; otherwise as the math spans MathJax reads."""
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    h = rows[0]
    title = h.get("title") or h.get("doc") or "Document"
    body, has_math = [], False
    for e in blocks(rows):
        t = e["type"]
        if t == "image":
            src = e.get("file", "")
            path = Path(base) / src
            if embed and src and path.is_file():
                src = _data_uri(path)
            alt = html.escape(e.get("md", ""), quote=True)
            body.append(f'<figure><img src="{html.escape(src, quote=True)}" alt="{alt}"></figure>')
        elif t == "table" and isinstance(e.get("html"), str) and e["html"]:
            body.append(e["html"])
        elif t == "formula":
            latex = e["latex"] if isinstance(e.get("latex"), str) else fmjl._strip_dollars(e.get("md", ""))
            body.append(f"<p>{_math_html(latex, True, dollars)}</p>")
            has_math = True
        elif t in ("code", "html"):
            body.append(md.render(e.get("md", "")) if t == "code" else e.get("md", ""))
        else:
            text, found = _math(fmjl._render_block(e))
            has_math = has_math or bool(found)
            out = _put_math(md.render(text), found, dollars)
            if t == "caption":
                out = out.replace("<p>", '<p class="caption">', 1)
            body.append(out)
    mathjax = ('<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>\n'
               if has_math else "")
    lang = html.escape(h.get("lang") or "en", quote=True)
    return (f'<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)}</title>\n<style>\n{CSS}</style>\n{mathjax}</head>\n<body>\n"
            + "\n".join(body) + "\n</body>\n</html>\n")


def to_pdf(rows, base, out):
    """Prints the HTML page to PDF with PyMuPDF; formulas stay as LaTeX text."""
    import pymupdf
    page = to_html(rows, base, embed=False)
    page = re.sub(r"<script.*?</script>\n?", "", page, flags=re.S)
    story = pymupdf.Story(html=page, user_css="body { font-family: serif; } img { width: 100%; }",
                          archive=str(Path(base).resolve()))
    writer = pymupdf.DocumentWriter(str(out))
    box = pymupdf.paper_rect("a4")
    where = box + (54, 54, -54, -54)
    more = True
    while more:
        device = writer.begin_page(box)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    done = pymupdf.open(str(out))
    done.subset_fonts()
    done.set_metadata({"title": rows[0].get("title") or rows[0].get("doc") or "",
                       "author": ", ".join(rows[0].get("authors") or []), "creator": fmjl.CONVERTER})
    data = done.tobytes(garbage=4, deflate=True)
    done.close()
    Path(out).write_bytes(data)


def to_pandoc(rows, base, out, fmt):
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError(f"--to {fmt} needs pandoc (https://pandoc.org/installing.html)")
    page = to_html(rows, base, embed=False, dollars=True)
    page = re.sub(r"<script.*?</script>\n?", "", page, flags=re.S)
    done = subprocess.run([pandoc, "-f", "html+tex_math_dollars", "-t", fmt, "-o", str(Path(out).resolve()),
                           "--resource-path", str(Path(base).resolve())],
                          input=page.encode("utf-8"), capture_output=True, cwd=str(Path(base).resolve()))
    if done.returncode != 0:
        raise RuntimeError("pandoc: " + done.stderr.decode("utf-8", "replace").strip())


def export(path, fmt, out=None):
    """Writes the .fmjl at path as fmt; returns the output path."""
    path = Path(path)
    rows = fmjl.read_rows(path)
    out = Path(out) if out else path.with_suffix("." + fmt)
    if out.resolve() == path.resolve():
        raise ValueError("the output would replace the .fmjl itself")
    base = path.parent
    if fmt == "md":
        fmjl.write_text(out, to_md(rows, base, out.parent))
    elif fmt == "html":
        fmjl.write_text(out, to_html(rows, base, embed=True))
    elif fmt == "pdf":
        to_pdf(rows, base, out)
    elif fmt in PANDOC:
        to_pandoc(rows, base, out, fmt)
    else:
        raise ValueError(f"unknown format {fmt}; use one of {', '.join(FORMATS)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fmjl export", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--to", required=True, choices=FORMATS)
    ap.add_argument("-o", "--output", help="output file (default: same name, new extension)")
    a = ap.parse_args(argv)
    try:
        out = export(a.file, a.to, a.output)
    except (ValueError, OSError, RuntimeError, ImportError) as e:
        print(f"error: {e}")
        return 2
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
