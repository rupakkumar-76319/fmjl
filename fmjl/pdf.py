#!/usr/bin/env python3
"""fmjl.pdf - PDF importer for FMJL, rulebook version 1.0.

  fmjl report.pdf                    writes report.fmjl, report.md and images/
  fmjl pdf report.pdf [-o report.fmjl] [--doc name]

What it does with a page:
  text blocks   headings (by font size), paragraphs, lists
  tables        found by PyMuPDF; merged cells become an HTML table with rowspan and colspan
  images        saved as PNG into images/, captions linked with reference=
  charts        drawn with lines and shapes are rendered to PNG as well
  noise         headers, footers and page numbers repeated across pages
Every element gets page (from 0) and bbox (0..1000). Paragraphs that run over
a page break are linked with continues=. Pages without a text layer need OCR;
that works when Tesseract is installed, otherwise the page is reported.

Needs: pip install pymupdf
Copyright (c) 2026 Rupak Kumar. MIT License, see LICENSE.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import pymupdf

import fmjl

BULLET_RE = re.compile(r"^\s*([•·▪●◦■–—*\-]|\d{1,3}[.)]|[a-zA-Z][.)]|\([a-zA-Z0-9]{1,3}\))\s+(.*)$")
NUMBER_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+")
PAGE_NUMBER_RE = re.compile(r"^\s*(page\s*)?[\divxlc]{1,7}(\s*(of|/|-)\s*\d{1,5})?\s*$", re.I)
CAPTION_RE = re.compile(r"^\s*(figure|fig\.?|table|chart|diagram|image|photo)\s*\d+[a-z]?\s*([:.\-–—)]|$)", re.I)
BULLET_ONLY_RE = re.compile(r"^\s*([•·▪●◦■–—*\-]|\d{1,3}[.)]|[a-zA-Z][.)]|\([a-zA-Z0-9]{1,3}\))\s*$")
ZERO_WIDTH_RE = re.compile("[​‌‍⁠﻿]")
SENTENCE_END = tuple('.!?:;"”’)]')
HEADING_END = tuple('.!?:;,"”’')
MAX_SCAN_TILES = 8
COLUMN_TOLERANCE = 20


def _norm(text):
    return re.sub(r"\d", "#", re.sub(r"\s+", " ", text)).strip().lower()


def _bbox(rect, page_rect):
    w, h = page_rect.width or 1, page_rect.height or 1
    vals = [rect[0] / w, rect[1] / h, rect[2] / w, rect[3] / h]
    return [min(1000, max(0, int(round(v * 1000)))) for v in vals]


def _cell(text):
    return re.sub(r"\s+", " ", text or "").strip().replace("|", "\\|")


def _block_text(block):
    lines = []
    for line in block["lines"]:
        text = ZERO_WIDTH_RE.sub("", "".join(s["text"] for s in line["spans"]))
        if not text.strip():
            continue
        if lines and BULLET_ONLY_RE.match(lines[-1]):
            lines[-1] = lines[-1].strip() + " " + text.strip()
        else:
            lines.append(text.rstrip())
    return lines


def _cells(block):
    rows = {}
    for line in block["lines"]:
        text = ZERO_WIDTH_RE.sub("", "".join(s["text"] for s in line["spans"])).strip()
        if not text:
            continue
        rows.setdefault(round(line["bbox"][1] / 3), []).append((line["bbox"][0], text))
    if not rows:
        return None
    out = [sorted(r) for _, r in sorted(rows.items())]
    width = len(out[0])
    if width < 2 or any(len(r) != width for r in out):
        return None
    if all(BULLET_ONLY_RE.match(r[0][1]) for r in out):
        return None
    return out


def _same_columns(a, b):
    return len(a[0]) == len(b[0]) and all(abs(x - y) <= COLUMN_TOLERANCE for (x, _), (y, _) in zip(a[0], b[0]))


def _merge_text_tables(items):
    out, run = [], []

    def flush():
        if len(run) >= 2 and sum(len(it["cells"]) for it in run) >= 3:
            rect = pymupdf.Rect(run[0]["rect"])
            for it in run[1:]:
                rect |= it["rect"]
            rows = [[c for _, c in r] for it in run for r in it["cells"]]
            out.append({"kind": "table", "rect": rect, "rows": rows})
        else:
            out.extend(run)
        run.clear()

    for it in sorted(items, key=lambda i: (i["rect"].y0, i["rect"].x0)):
        if it["kind"] == "text" and it.get("cells") and (not run or _same_columns(run[-1]["cells"], it["cells"])):
            run.append(it)
            continue
        flush()
        if it["kind"] == "text" and it.get("cells"):
            run.append(it)
        else:
            out.append(it)
    flush()
    return out


def _join_lines(lines):
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
        elif out.endswith("-") and ln[:1].islower():
            out = out[:-1] + ln
        else:
            out += " " + ln
    return re.sub(r"[ \t]+", " ", out)


def _table_cells(t):
    """Cells of a PyMuPDF table as rows of (text, rowspan, colspan); covered cells are dropped."""
    rows = t.extract()
    boxes = [r.cells for r in t.rows]
    out, covered = [], set()
    for ri, row in enumerate(rows):
        cells = []
        for ci, text in enumerate(row):
            if (ri, ci) in covered:
                continue
            box = boxes[ri][ci] if ci < len(boxes[ri]) else None
            if text is None and box is None:
                continue
            rs = 1
            if box is not None:
                while ri + rs < len(boxes) and t.rows[ri + rs].bbox[3] <= box[3] + 1:
                    rs += 1
            cs = 1
            while ci + cs < len(row) and row[ci + cs] is None and (ri, ci + cs) not in covered \
                    and (ci + cs >= len(boxes[ri]) or boxes[ri][ci + cs] is None):
                cs += 1
            for dr in range(rs):
                for dc in range(cs):
                    covered.add((ri + dr, ci + dc))
            cells.append((text or "", rs, cs))
        out.append(cells)
    return out


def _drawings(page, tables):
    """Vector charts and diagrams: clusters of lines and shapes that hold little text."""
    out = []
    try:
        clusters = page.cluster_drawings()
    except Exception:
        return out
    if not clusters:
        return out
    text_blocks = [(pymupdf.Rect(b[:4]), b[4].strip()) for b in page.get_text("blocks") if b[6] == 0]
    drawings = page.get_drawings()
    for rect in clusters:
        rect = pymupdf.Rect(rect)
        if rect.width < 40 or rect.height < 40:
            continue
        if any((t & rect).get_area() > 0.3 * min(t.get_area(), rect.get_area()) for t, _ in tables):
            continue
        inside = sum(len(txt) for r, txt in text_blocks if rect.contains(r))
        shapes = sum(1 for d in drawings if rect.contains(d["rect"]))
        if inside > 200 or shapes < 3:
            continue
        grown = pymupdf.Rect(rect)
        for r, txt in text_blocks:
            if len(txt) > 40 or CAPTION_RE.match(txt) or rect.contains(r):
                continue
            beside = r.y0 < rect.y1 and r.y1 > rect.y0 and (rect.x0 - 30 <= r.x1 <= rect.x0 + 15 or rect.x1 - 15 <= r.x0 <= rect.x1 + 30)
            stacked = r.x0 < rect.x1 and r.x1 > rect.x0 and (rect.y0 - 30 <= r.y1 <= rect.y0 + 15 or rect.y1 - 15 <= r.y0 <= rect.y1 + 30)
            if beside or stacked:
                grown |= r
        out.append(grown)
    return out


def _span_stats(block):
    sizes, bold, chars = Counter(), 0, 0
    for line in block["lines"]:
        for s in line["spans"]:
            n = len(s["text"].strip())
            if not n:
                continue
            sizes[round(s["size"] * 2) / 2] += n
            chars += n
            if (s["flags"] & 16) or "bold" in s["font"].lower():
                bold += n
    size = sizes.most_common(1)[0][0] if sizes else 0
    return size, chars and bold / chars >= 0.9, chars


class _Page:
    def __init__(self, number, rect):
        self.number, self.rect, self.items, self.no_text = number, rect, [], False


def _read_pages(doc, ocr):
    pages, image_seen = [], {}
    for pno, page in enumerate(doc):
        pg = _Page(pno, page.rect)
        pages.append(pg)
        textpage = None
        if not page.get_text().strip() and page.get_images():
            if ocr:
                textpage = page.get_textpage_ocr(full=True)
            else:
                pg.no_text = True
        tables = []
        try:
            for t in page.find_tables().tables:
                rows = t.extract()
                if rows and any(any(c for c in r) for r in rows):
                    tables.append((pymupdf.Rect(t.bbox), _table_cells(t)))
        except Exception:
            pass
        for rect, rows in tables:
            pg.items.append({"kind": "table", "rect": rect, "rows": rows})
        charts = _drawings(page, tables) if not pg.no_text else []
        for rect in charts:
            pg.items.append({"kind": "drawing", "rect": rect})
        d = page.get_text("dict", textpage=textpage) if textpage else page.get_text("dict")
        image_blocks = sum(1 for b in d["blocks"] if b["type"] == 1)
        scan_tiles = image_blocks > MAX_SCAN_TILES and not pg.no_text
        for b in d["blocks"]:
            rect = pymupdf.Rect(b["bbox"])
            if b["type"] == 1:
                area = rect.get_area() / (page.rect.get_area() or 1)
                if scan_tiles or area < 0.004 or (area > 0.8 and not pg.no_text) or rect.width < 12 or rect.height < 12:
                    continue
                digest = hashlib.sha1(b["image"]).hexdigest()
                image_seen.setdefault(digest, []).append(pno)
                pg.items.append({"kind": "image", "rect": rect, "bytes": b["image"], "digest": digest})
                continue
            if any(t.contains(rect) or (t & rect).get_area() > 0.5 * rect.get_area() for t, _ in tables):
                continue
            if any(c.contains(rect) for c in charts):
                continue
            lines = _block_text(b)
            if not lines:
                continue
            size, bold, chars = _span_stats(b)
            pg.items.append({"kind": "text", "rect": rect, "lines": lines, "size": size, "bold": bold,
                             "chars": chars, "ocr": textpage is not None, "cells": _cells(b)})
        pg.items = _merge_text_tables(pg.items)
    return pages, image_seen


def _body_size(pages):
    sizes = Counter()
    for pg in pages:
        for it in pg.items:
            if it["kind"] == "text":
                sizes[it["size"]] += it["chars"]
    return sizes.most_common(1)[0][0] if sizes else 10.0


def _mark_noise(pages):
    seen = Counter()
    for pg in pages:
        h = pg.rect.height or 1
        for it in pg.items:
            if it["kind"] != "text":
                continue
            top, bottom = it["rect"].y0 / h, it["rect"].y1 / h
            zone = "header" if bottom < 0.12 else "footer" if top > 0.88 else None
            if not zone:
                continue
            key = (zone, _norm(" ".join(it["lines"])))
            it["_zone"], it["_key"] = zone, key
            seen[key] += 1
    threshold = max(2, int(len(pages) * 0.3))
    for pg in pages:
        for it in pg.items:
            zone = it.get("_zone")
            if not zone:
                continue
            text = " ".join(it["lines"])
            if PAGE_NUMBER_RE.match(text):
                it["noise"] = "page_number"
            elif seen[it["_key"]] >= threshold and len(text) < 200:
                it["noise"] = zone


def _order(items, rect):
    w = rect.width or 1
    mid = w / 2
    narrow = [it for it in items if it["rect"].width < 0.6 * w]
    left = [it for it in narrow if it["rect"].x1 <= mid + 0.06 * w and it["rect"].x0 < mid - 0.1 * w]
    right = [it for it in narrow if it["rect"].x0 >= mid - 0.06 * w]
    if len(left) >= 2 and len(right) >= 2:
        left_ids, right_ids = {id(i) for i in left}, {id(i) for i in right}
        ordered, band = [], []

        def flush():
            band.sort(key=lambda i: i["rect"].y0)
            ordered.extend([i for i in band if id(i) in left_ids] + [i for i in band if id(i) in right_ids]
                           + [i for i in band if id(i) not in left_ids and id(i) not in right_ids])
            band.clear()

        for it in sorted(items, key=lambda i: i["rect"].y0):
            if id(it) not in left_ids and id(it) not in right_ids:
                flush()
                ordered.append(it)
            else:
                band.append(it)
        flush()
        return ordered
    return sorted(items, key=lambda i: (round(i["rect"].y0 / 4), i["rect"].x0))


def _text_element(it, body, levels):
    lines = it["lines"]
    text = _join_lines(lines)
    if it.get("noise"):
        return {"type": "noise", "subtype": it["noise"], "md": text}
    size = it["size"]
    short = len(text) <= 160 and len(lines) <= 3 and not text.endswith(HEADING_END)
    if short and (size in levels or (it["bold"] and size >= body)):
        level = levels.get(size, min(6, len(levels) + 1))
        return {"type": "heading", "level": level, "md": "#" * level + " " + text}
    if BULLET_RE.match(lines[0]) and sum(1 for ln in lines if BULLET_RE.match(ln)) >= max(1, len(lines) // 2):
        items = []
        for ln in lines:
            m = BULLET_RE.match(ln)
            if m:
                n = NUMBER_RE.match(ln)
                items.append(("%s. " % n.group(1) if n else "- ") + m.group(2).strip())
            elif items:
                items[-1] = _join_lines([items[-1], ln])
            else:
                items.append("- " + ln.strip())
        return {"type": "list", "md": "\n".join(items)}
    if CAPTION_RE.match(text) and len(text) <= 300:
        return {"type": "caption", "md": text}
    return {"type": "paragraph", "md": text}


def _table_element(rows):
    """rows: lists of (text, rowspan, colspan) from _table_cells, or plain text lists."""
    cells = [[(c if isinstance(c, tuple) else (c, 1, 1)) for c in r] for r in rows]
    if any(rs > 1 or cs > 1 for r in cells for _, rs, cs in r):
        grid = fmjl._span_grid([[(_cell(t), (rs, cs)) for t, rs, cs in r] for r in cells], True)
        html = fmjl.shortcut_to_html(grid)
        return {"type": "table", "html": html, "md": fmjl.html_table_to_md(html)}
    width = max(len(r) for r in cells)
    grid = [[_cell(t) for t, _, _ in r] + [""] * (width - len(r)) for r in cells]
    lines = [fmjl._pipe_row(grid[0]), fmjl._pipe_row(["---"] * width)]
    lines += [fmjl._pipe_row(r) for r in grid[1:]]
    return {"type": "table", "md": "\n".join(lines)}


def _fallback_headings(els):
    """Scans and OCR text have no reliable font sizes (NOTES 11): short lines in capitals or
    with a section number become headings."""
    for e in els:
        if e["type"] != "paragraph" or len(e["md"]) > 80 or "\n" in e["md"] or e["md"].endswith(HEADING_END):
            continue
        text = e["md"]
        m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$", text)
        letters = [c for c in text if c.isalpha()]
        if m and m.group(2)[:1].isupper() and len(m.group(2).split()) <= 10:
            level = min(6, m.group(1).count(".") + 1)
        elif len(letters) >= 3 and all(c.isupper() for c in letters) and len(text.split()) <= 10:
            level = 1
        else:
            continue
        e["type"], e["level"], e["md"] = "heading", level, "#" * level + " " + text


def _clamp_levels(els):
    """A heading is at most one level deeper than the heading before it (rulebook 10.1)."""
    prev = 0
    for e in els:
        if e["type"] != "heading":
            continue
        if e["level"] > prev + 1:
            e["level"] = prev + 1
            e["md"] = "#" * e["level"] + " " + re.sub(r"^#+\s*", "", e["md"])
        prev = e["level"]


def _save_image(data, path):
    pix = pymupdf.Pixmap(data)
    if pix.n - pix.alpha >= 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    pix.save(str(path))


def _heading_levels(pages, body):
    sizes = Counter()
    for pg in pages:
        for it in pg.items:
            if it["kind"] == "text" and not it.get("noise") and it["size"] >= body * 1.15:
                text = _join_lines(it["lines"])
                if len(text) <= 160 and len(it["lines"]) <= 3:
                    sizes[it["size"]] += 1
    ranked = sorted(sizes, reverse=True)[:5]
    return {s: i + 1 for i, s in enumerate(ranked)}


def _near(a, b, gap):
    horizontal = a.x0 < b.x1 and b.x0 < a.x1
    return horizontal and (-6 <= b.y0 - a.y1 <= gap or -6 <= a.y0 - b.y1 <= gap)


def _merge_lists(page_els):
    out = []
    for e in page_els:
        prev = out[-1] if out else None
        if prev is not None and e["type"] == "list" and prev["type"] == "list" \
                and e["_rect"].y0 - prev["_rect"].y1 <= 30:
            prev["md"] += "\n" + e["md"]
            prev["_rect"] |= e["_rect"]
            prev["bbox"] = _bbox(prev["_rect"], prev["_page_rect"])
        else:
            out.append(e)
    return out


def import_pdf(path, doc=None, out_dir=None, ocr=None):
    path = Path(path)
    out_dir = Path(out_dir) if out_dir else path.parent
    doc = doc or re.sub(r"[^a-z0-9_-]+", "_", path.stem.lower()).strip("_") or "document"
    if ocr is None:
        ocr = shutil.which("tesseract") is not None
    pdf = pymupdf.open(path)
    pages, image_seen = _read_pages(pdf, ocr)
    body = _body_size(pages)
    _mark_noise(pages)
    levels = _heading_levels(pages, body)
    warnings = [f"page {pg.number + 1} has no text layer; install Tesseract for OCR" for pg in pages if pg.no_text]

    els, logos = [], set()
    images_dir = out_dir / "images"
    for pg in pages:
        ordered = _order(pg.items, pg.rect)
        page_els = []
        for it in ordered:
            if it["kind"] == "text":
                e = _text_element(it, body, levels)
                if it.get("ocr"):
                    e["meta"] = {"ocr": True}
            elif it["kind"] == "table":
                e = _table_element(it["rows"])
            elif it["kind"] == "drawing":
                clip = pymupdf.Rect(it["rect"]) + (-4, -4, 4, 4)
                pix = pdf[pg.number].get_pixmap(clip=clip & pdf[pg.number].rect, dpi=150)
                e = {"type": "image", "subtype": "diagram", "md": "", "_pix": pix}
            else:
                repeated = len(set(image_seen[it["digest"]])) >= max(3, int(len(pages) * 0.5))
                if repeated:
                    if it["digest"] in logos:
                        continue
                    logos.add(it["digest"])
                e = {"type": "image", "md": "", "_bytes": it["bytes"]}
                if repeated:
                    e["subtype"] = "logo"
            e["page"] = pg.number
            e["bbox"] = _bbox(it["rect"], pg.rect)
            e["_rect"] = pymupdf.Rect(it["rect"])
            e["_page_rect"] = pg.rect
            page_els.append(e)
        page_els = _merge_lists(page_els)
        for i, e in enumerate(page_els):
            if e["type"] != "caption":
                continue
            wants = "table" if e["md"].lower().startswith("table") else "image"
            target = None
            for want in (wants, None):
                for j in (i - 1, i + 1):
                    if 0 <= j < len(page_els) and page_els[j]["type"] in ("image", "table") \
                            and (want is None or page_els[j]["type"] == want) \
                            and _near(page_els[j]["_rect"], e["_rect"], 60):
                        target = page_els[j]
                        break
                if target is not None:
                    break
            if target is None:
                e["type"] = "paragraph"
                continue
            e["_target"] = target
            if target["type"] == "image" and not target["md"]:
                target["md"] = e["md"]
                if target.get("subtype") == "diagram" and re.search(r"chart|graph|plot", e["md"], re.I):
                    target["subtype"] = "chart"
        els.extend(page_els)

    if sum(1 for e in els if e["type"] == "heading") < 2 and len(pages) > 1:
        _fallback_headings(els)
    _clamp_levels(els)

    for n, e in enumerate(els, 1):
        e["id"] = f"{doc}#e{n}"
    for e in els:
        if "_target" in e:
            e["reference"] = e.pop("_target")["id"]
        if e["type"] == "image":
            images_dir.mkdir(parents=True, exist_ok=True)
            name = f"images/{doc}_{e['id'].rsplit('#', 1)[1]}.png"
            if "_pix" in e:
                e.pop("_pix").save(str(out_dir / name))
            else:
                _save_image(e.pop("_bytes"), out_dir / name)
            e["file"] = name
            if not e["md"]:
                e["md"] = f"Image on page {e['page'] + 1}"
        e.pop("_rect", None)
        e.pop("_page_rect", None)

    prev = None
    for e in els:
        if e["type"] in ("noise", "caption", "image"):
            continue
        if prev is not None and e["type"] == "paragraph" and prev["type"] == "paragraph" \
                and e["page"] == prev["page"] + 1 and not prev["md"].endswith(SENTENCE_END) \
                and e["md"][:1].islower():
            e["continues"] = prev["id"]
        prev = e

    meta = pdf.metadata or {}
    h = {"type": "document", "doc": doc, "source": path.name, "converter": "fmjl pdf 1.0"}
    title = (meta.get("title") or "").strip()
    if not title:
        for e in els:
            if e["type"] == "heading" and e["level"] == 1:
                title = e["md"][2:]
                break
    if title:
        h["title"] = title
    author = (meta.get("author") or "").strip()
    if author:
        h["authors"] = [a.strip() for a in re.split(r"[;,]", author) if a.strip()]
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", meta.get("creationDate") or "")
    if m:
        h["date"] = "-".join(m.groups())
    h["meta"] = {"pages": len(pages)}
    rows = fmjl.fill([h] + els, base=path.parent)
    return rows, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fmjl pdf", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--output", help="output .fmjl (default: same name next to the PDF)")
    ap.add_argument("--doc", help="document name (default: from the file name)")
    ap.add_argument("--no-md", action="store_true", help="do not write the .md authoring form")
    a = ap.parse_args(argv)
    path = Path(a.file)
    out = Path(a.output) if a.output else path.with_suffix(".fmjl")
    try:
        rows, warnings = import_pdf(path, doc=a.doc, out_dir=out.parent)
    except (ValueError, OSError, RuntimeError) as e:
        print(f"error: {e}")
        return 2
    fmjl.write_rows(out, rows)
    print(f"wrote {out} ({len(rows) - 1} elements from {rows[0]['meta']['pages']} pages)")
    if not a.no_md:
        md = out.with_suffix(".md")
        fmjl.write_text(md, fmjl.export_md(rows))
        print(f"wrote {md}")
    for w in warnings:
        print("warning: " + w)
    return fmjl._report(fmjl.check(out))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
