#!/usr/bin/env python3
"""fmjl.pdf - PDF importer for FMJL, rulebook version 1.1.

  fmjl report.pdf                    writes report.fmjl and images/ (add --md for report.md too)
  fmjl pdf report.pdf [-o report.fmjl] [--doc name]

What it does with a page:
  text blocks   headings (by font size), paragraphs, lists; blocks that the text layer cut
                out of one paragraph are joined again
  tables        found by PyMuPDF; merged cells become an HTML table with rowspan and colspan
  images        saved as PNG into images/, captions linked with reference=
  charts        drawn with lines and shapes are rendered to PNG as well
  noise         headers, footers and page numbers repeated across pages, also when the
                page number in them changes
  books         "Chapter I" lines become headings and the header meta gets fmjl.body
  scans         missing spaces in an OCR text layer are restored; blank pages are skipped
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
import unicodedata
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
HEADING_END = tuple('.:;,"”’')
SOFT = ""
MARKER_RE = re.compile(r"^\[?(\d{1,3}|[ivxlc]{1,7}|[*†‡§])\]?$")
QUOTES = "\"'’”"
NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                "sixteen|seventeen|eighteen|nineteen|twenty|first|second|third|fourth|fifth|sixth|seventh|"
                "eighth|ninth|tenth|last")
CHAPTER_RE = re.compile(r"^(?i:chapter|part|book|volume|canto)\s+([IVXLCDM]+|\d{1,3}|(?i:" + NUMBER_WORDS + r"))"
                        r"\s*[.:]?(\s*[.:—–-]?\s+\S.{0,70})?$")
PART_RE = re.compile(r"^(part|book|volume)\b", re.I)
FRONT_RE = re.compile(r"^(preface|introduction|prologue|foreword)\.?$", re.I)
MIN_CHAPTERS = 3
MAX_SCAN_TILES = 8
COLUMN_TOLERANCE = 20


def _norm(text):
    """The key of a running header: its letters only, without a page number in Roman numerals
    at either end, so "PERSUASION. 11", "102 PERSUASION." and "xii • Contents" and
    "Contents • xiii" are one header each."""
    text = re.sub(r"^\W*[ivxlcdm]+\b|\b[ivxlcdm]+\W*$", "", text.strip(), flags=re.I) or text
    return re.sub(r"[^a-z]+", "", text.lower()) or re.sub(r"\d+", "#", re.sub(r"\s+", " ", text)).strip().lower()


def _area(rect):
    return max(0.0, rect.x1 - rect.x0) * max(0.0, rect.y1 - rect.y0)


def _bbox(rect, page_rect):
    w, h = page_rect.width or 1, page_rect.height or 1
    vals = [rect[0] / w, rect[1] / h, rect[2] / w, rect[3] / h]
    return [min(1000, max(0, int(round(v * 1000)))) for v in vals]


def _cell(text):
    return re.sub(r"\s+", " ", text or "").strip().replace("|", "\\|")


def _scanned(blocks, page_rect):
    """True when the text lies over a picture of the whole page: a scan with a text layer
    from OCR. Such layers store each word as a span and sometimes leave out the space between
    two words, so a space belongs between two spans (rulebook 10.1)."""
    page_area = _area(page_rect) or 1
    return any(b["type"] == 1 and _area(pymupdf.Rect(b["bbox"])) > 0.8 * page_area for b in blocks) \
        and any(b["type"] == 0 for b in blocks)


def _script(ch):
    name = unicodedata.name(ch, "")
    return name.split(" ")[0] if name else ""


def _scan_cleanup(items):
    """On a scanned page: an image with text lying on it is part of the scan (a sharper copy of
    the text area), not a picture; text without any letter or digit ("*", "—"), or a piece of at
    most three characters in another script than the page, is what OCR read from an ornament
    (rulebook 10.1, rule 15)."""
    texts = [it for it in items if it["kind"] == "text"]
    letters = Counter(_script(c) for it in texts for ln in it["lines"] for c in ln if c.isalpha())
    main = letters.most_common(1)[0][0] if letters else ""
    out = []
    for it in items:
        if it["kind"] == "image":
            covered = sum(_area(t["rect"] & it["rect"]) for t in texts)
            if covered >= 0.3 * (_area(it["rect"]) or 1):
                continue
        if it["kind"] == "text":
            text = "".join(it["lines"]).strip()
            if not any(c.isalnum() for c in text):
                continue
            if len(text) <= 3 and main and all(_script(c) != main for c in text if c.isalpha()) \
                    and any(c.isalpha() for c in text):
                continue
        out.append(it)
    return out


def _gap_spaces(raw):
    """Text of a scanned page from its characters: inside one span the letters of a word touch,
    so a gap of at least 5% of the font size between two letters is a space the OCR layer left
    out ("partof" is drawn as "part of") (rulebook 10.1, rule 15)."""
    for b in raw["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                chars = s.get("chars", [])
                gaps = sorted(b["bbox"][0] - a["bbox"][2] for a, b in zip(chars, chars[1:])
                              if a["c"].isalnum() and b["c"].isalnum())
                usual = gaps[len(gaps) // 2] if gaps else 0
                need = max(0.05 * (s["size"] or 10), usual + 0.05 * (s["size"] or 10), 3 * usual)
                out, prev = [], None
                for c in chars:
                    if prev is not None and prev["c"].isalnum() and c["c"].isalnum() \
                            and c["bbox"][0] - prev["bbox"][2] >= need:
                        out.append(" ")
                    out.append(c["c"])
                    prev = c
                s["text"] = "".join(out)
    return raw


def _join_spans(spans, spaced):
    out = ""
    for s in spans:
        t = s["text"]
        if spaced and out and t[:1].isalnum():
            end = out.rstrip(QUOTES)
            closed = 0 < len(end) < len(out) and end[-1] in ",.;:!?"
            if out[-1].isalnum() or out[-1] in ",.;:!?" or closed:
                out += " "
        out += t
    return out


def _block_text(block, spaced=False):
    lines, rects = [], []
    for line in block["lines"]:
        text = ZERO_WIDTH_RE.sub("", _join_spans(line["spans"], spaced))
        if not text.strip():
            continue
        if lines and BULLET_ONLY_RE.match(lines[-1]):
            lines[-1] = lines[-1].strip() + " " + text.strip()
            rects[-1] |= line["bbox"]
        else:
            lines.append(text.rstrip())
            rects.append(pymupdf.Rect(line["bbox"]))
    return lines, rects


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


def _resolve_hyphens(els):
    """A hyphen at the end of a line was left as SOFT by _join_lines. It stays a hyphen when the
    document writes the word with a hyphen elsewhere and never without ("self-esteem");
    otherwise it was only a line break and the halves join ("some-thing" becomes "something")
    (rulebook 10.1)."""
    texts = [e.get("md", "") for e in els] + [e.get("_text", "") for e in els]
    plain = Counter(w.lower() for t in texts for w in re.findall(r"\w+", t.replace(SOFT, " ")))
    hyphened = Counter(m.group(0).lower() for t in texts for m in re.finditer(r"\w+-\w+", t))

    def pick(m):
        a, b = m.group(1), m.group(2)
        joined, kept = (a + b).lower(), (a + "-" + b).lower()
        return a + "-" + b if hyphened[kept] and not plain[joined] else a + b

    for e in els:
        for k in ("md", "_text"):
            if SOFT in e.get(k, ""):
                e[k] = re.sub(r"(\w*)" + SOFT + r"(\w*)", pick, e[k])


def _join_lines(lines):
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
        elif out.endswith("\u00ad"):
            out = out[:-1] + ln
        elif out.endswith("-") and ln[:1].islower():
            out = out[:-1] + SOFT + ln
        else:
            out += " " + ln
    return re.sub(r"[ \t]+", " ", out).replace("\u00ad", "")


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
        if any(_area((t & rect)) > 0.3 * min(_area(t), _area(rect)) for t, _ in tables):
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
        self.number, self.rect, self.items, self.no_text, self.blank = number, rect, [], False, False


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
        if pg.no_text and _blank(page):
            pg.no_text, pg.blank = False, True
            continue
        spaced = _scanned(d["blocks"], page.rect)
        if spaced:
            d = _gap_spaces(page.get_text("rawdict", textpage=textpage) if textpage else page.get_text("rawdict"))
        image_blocks = sum(1 for b in d["blocks"] if b["type"] == 1)
        scan_tiles = image_blocks > MAX_SCAN_TILES and not pg.no_text
        for b in d["blocks"]:
            rect = pymupdf.Rect(b["bbox"])
            if b["type"] == 1:
                area = _area(rect) / (_area(page.rect) or 1)
                if scan_tiles or area < 0.004 or (area > 0.8 and not pg.no_text) or rect.width < 12 or rect.height < 12:
                    continue
                digest = hashlib.sha1(b["image"]).hexdigest()
                image_seen.setdefault(digest, []).append(pno)
                pg.items.append({"kind": "image", "rect": rect, "bytes": b["image"], "digest": digest})
                continue
            if any(t.contains(rect) or _area((t & rect)) > 0.5 * _area(rect) for t, _ in tables):
                continue
            if any(c.contains(rect) for c in charts):
                continue
            lines, rects = _block_text(b, spaced)
            if not lines:
                continue
            size, bold, chars = _span_stats(b)
            pg.items.append({"kind": "text", "rect": rect, "lines": lines, "line_rects": rects, "size": size,
                             "bold": bold, "chars": chars, "ocr": textpage is not None, "cells": _cells(b)})
        if spaced:
            pg.items = _scan_cleanup(pg.items)
        pg.items = _colon_lists(_attach_fragments(_drop_caps(_merge_text_tables(pg.items)), spaced))
    return pages, image_seen


def _blank(page):
    """A page with no text whose picture is almost all white, such as a scanned endpaper."""
    pix = page.get_pixmap(dpi=24, colorspace=pymupdf.csGRAY)
    dark = sum(1 for v in pix.samples if v < 160)
    return dark <= 0.003 * len(pix.samples)


def _colon_lists(items):
    """A block whose line ends with a colon and is followed by two or more short lines that do
    not reach the right margin holds a list without bullets: the short lines become list items
    instead of being run together with the sentence above (rulebook 10.1, rule 18)."""
    out = []
    for it in items:
        lines = it.get("lines") or []
        cut = next((i for i, ln in enumerate(lines[:-2]) if ln.rstrip().endswith(":")), None) \
            if it["kind"] == "text" and not it.get("cells") else None
        if cut is None:
            out.append(it)
            continue
        rest, rects = lines[cut + 1:], it["line_rects"][cut + 1:]
        right = max(r.x1 for r in it["line_rects"])
        size = it["size"] or 10
        if not all(r.x1 < right - 3 * size for r in rects[:-1]) or any(ln.rstrip().endswith((".", "!", "?")) for ln in rest[:-1]) \
                or any(BULLET_RE.match(ln) for ln in rest):
            out.append(it)
            continue
        head = dict(it, lines=lines[:cut + 1], line_rects=it["line_rects"][:cut + 1], cells=None)
        head["rect"] = pymupdf.Rect(head["line_rects"][0])
        for r in head["line_rects"][1:]:
            head["rect"] |= r
        tail = dict(it, lines=["- " + ln.strip() for ln in rest], line_rects=list(rects), cells=None)
        tail["rect"] = pymupdf.Rect(rects[0])
        for r in rects[1:]:
            tail["rect"] |= r
        out += [head, tail]
    return out


def _drop_caps(items):
    """A drop cap, the large first letter of a paragraph, goes back to the start of the
    paragraph beside it ("I" + "n the early 1880s"), wherever the text layer put it (rulebook 10.1)."""
    texts = [it for it in items if it["kind"] == "text" and not it.get("cells")]
    if not texts:
        return items
    sizes = sorted(it["size"] for it in texts)
    usual = sizes[len(sizes) // 2] or 10
    for it in texts:
        for i in range(len(it["lines"]) - 1, -1, -1):
            letter, r = it["lines"][i].strip(), it["line_rects"][i]
            if len(letter) != 1 or not letter.isalpha() or not letter.isupper() or r.height < 2.2 * usual:
                continue
            for t in texts:
                if t is it or not t["lines"]:
                    continue
                first = t["line_rects"][0]
                if -2 <= first.x0 - r.x1 <= 2 * usual and r.y0 - usual <= first.y0 <= r.y0 + 0.5 * r.height \
                        and t["lines"][0][:1].isalpha():
                    t["lines"][0] = letter + t["lines"][0].lstrip()
                    t["line_rects"][0] = first | r
                    t["rect"] = t["rect"] | r
                    del it["lines"][i], it["line_rects"][i]
                    break
    return [it for it in items if it["kind"] != "text" or it["lines"]]


def _attach_fragments(items, scanned=False):
    """Some text layers put the last word of a line in a block of its own. Such a word goes
    back into the line it stands beside instead of becoming a paragraph after the block."""
    texts = [it for it in items if it["kind"] == "text" and not it.get("cells")]
    out = []
    for it in items:
        if it["kind"] == "text" and not it.get("cells") and len(it["lines"]) == 1 \
                and len(it["lines"][0].split()) <= 3 and _place_fragment(it, texts, scanned):
            texts.remove(it)
            continue
        out.append(it)
    return out


def _is_list(lines):
    """Lines that are list items. A letter or Roman marker ("A.", "iv)") counts only when at
    least two lines carry such markers in order, so a name such as "R. B. Sparkman" is not a list."""
    marks = [m.group(1) for m in (BULLET_RE.match(ln) for ln in lines) if m]
    if not BULLET_RE.match(lines[0]) or len(marks) < max(1, (len(lines) + 1) // 2):
        return False
    if len(marks) < 2 and marks[0] in "–—-*":
        return False
    letters = [re.sub(r"[().]", "", k) for k in marks if re.fullmatch(r"\(?[a-zA-Z]{1,4}[.)]", k)]
    if letters and len(letters) == len(marks):
        if len(letters) < 2:
            return False
        order = [ord(k[0].lower()) for k in letters]
        roman = all(re.fullmatch(r"[ivxlc]+", k, re.I) for k in letters)
        return roman or order == sorted(order)
    return True


def _same_size(a, b):
    """Font sizes that are equal for layout purposes; OCR layers measure each block a little
    differently."""
    return abs(a - b) <= max(0.5, 0.2 * max(a, b))


def _place_fragment(frag, texts, scanned=False):
    """Puts a one-to-three-word block back into the line it stands beside: the line it overlaps
    most, never after a line that already ends with a hyphen."""
    r, best = frag["rect"], None
    for host in texts:
        size = (max(frag["size"], host["size"]) if scanned else frag["size"]) or 10
        marker = MARKER_RE.match(frag["lines"][0].strip()) and frag["size"] < host["size"]
        close = abs(host["size"] - frag["size"]) <= 0.3 * size if scanned else _same_size(host["size"], frag["size"])
        if host is frag or len(host["lines"]) < 2 or not (close or marker):
            continue
        for i, lr in enumerate(host["line_rects"]):
            overlap = min(lr.y1, r.y1) - max(lr.y0, r.y0)
            if overlap < 0.5 * min(r.height, lr.height):
                continue
            if (-r.width if scanned else 0) <= r.x0 - lr.x1 <= 1.5 * size and r.x1 >= lr.x1 - 2                     and not host["lines"][i].rstrip().endswith("-"):
                side = "end"
            elif 0 <= lr.x0 - r.x1 <= 1.5 * size:
                side = "start"
            else:
                continue
            if best is None or overlap > best[0]:
                best = (overlap, host, i, side)
    if best is None:
        return False
    _, host, i, side = best
    word, lr = frag["lines"][0].strip(), host["line_rects"][i]
    host["lines"][i] = host["lines"][i].rstrip() + " " + word if side == "end" else word + " " + host["lines"][i].lstrip()
    host["line_rects"][i] = lr | r
    host["rect"] = host["rect"] | r
    host["chars"] += frag["chars"]
    return True


def _full_last(it):
    """The last line of a block runs to the right edge, so the paragraph goes on."""
    if len(it["line_rects"]) < 2:
        return None
    return it["line_rects"][-1].x1 >= it["rect"].x1 - 1.5 * (it["size"] or 10)


def _indented(it):
    """The first line of a block starts further right than the others: a new paragraph."""
    rects = it["line_rects"]
    if len(rects) < 2:
        return None
    return rects[0].x0 > min(r.x0 for r in rects[1:]) + 0.6 * (it["size"] or 10)


def _line_gap(*its):
    gaps = [b.y0 - a.y1 for it in its for a, b in zip(it["line_rects"], it["line_rects"][1:])]
    gaps.sort()
    return gaps[len(gaps) // 2] if gaps else None


def _indent_style(pages, body):
    """True when the document starts its paragraphs with an indented first line, as books do.
    Only then does a block whose first line is not indented say "the paragraph goes on";
    in block-style documents a full last line proves nothing."""
    flags = [_indented(it) for pg in pages for it in pg.items
             if it["kind"] == "text" and not it.get("noise") and len(it["line_rects"]) >= 3
             and _same_size(it["size"], body)]
    return len(flags) >= 10 and sum(1 for f in flags if f) >= 0.3 * len(flags)


def _merge_paragraphs(pg, body, indent_style):
    """Join text blocks that are one paragraph split by the text layer: same body size, the
    same column, the usual line spacing between them, the line above running to the margin,
    and the line below not indented. In documents without indented paragraphs the text above
    must also stop mid-sentence (rulebook 10.1)."""
    def plain(it):
        return it["kind"] == "text" and not it.get("noise") and not it.get("cells") and not it["bold"] \
            and (_same_size(it["size"], body) or it.get("side")) and not _is_list(it["lines"]) \
            and not CHAPTER_RE.match(_join_lines(it["lines"]))

    others = [it for it in pg.items if not plain(it)]
    out = []
    for it in sorted(pg.items, key=lambda i: (i["rect"].y0, i["rect"].x0)):
        if not plain(it):
            out.append(it)
            continue
        b = it["rect"]
        above = [p for p in out if plain(p) and p["rect"].y1 <= b.y0 + 0.5 * (body or 10)
                 and bool(p.get("side")) == bool(it.get("side")) and _same_size(p["size"], it["size"])
                 and min(p["rect"].x1, b.x1) - max(p["rect"].x0, b.x0) >= 0.6 * min(p["rect"].width, b.width)]
        target = max(above, key=lambda p: p["rect"].y1) if above else None
        if target is not None:
            a, size = target["rect"], (it["size"] if it.get("side") else body) or 10
            usual = _line_gap(target, it)
            limit = max(usual if usual is not None else 0.2 * size, 0) + 0.3 * size
            if re.search(r"\w-$", target["lines"][-1].rstrip()) or len(it["lines"]) == 1:
                limit = max(limit, 0.8 * size)
            between = any(o is not it and o is not target and o["rect"].y0 < b.y0 and o["rect"].y1 > a.y1
                          and min(o["rect"].x1, b.x1) > max(o["rect"].x0, b.x0) for o in others)
            col_right = max(a.x1, b.x1)
            last_full = target["line_rects"][-1].x1 >= col_right - 1.5 * size
            col_left = min([r.x0 for r in target["line_rects"][1:] + it["line_rects"][1:]] or [a.x0, b.x0])
            not_indented = it["line_rects"][0].x0 <= col_left + 0.6 * size
            goes_on = indent_style or not target["lines"][-1].rstrip().endswith(SENTENCE_END)
            if it.get("side"):
                last_full = goes_on = not_indented = not target["lines"][-1].rstrip().endswith(SENTENCE_END) \
                    or it["lines"][0].lstrip()[:1].islower()
            if -0.5 * size <= b.y0 - a.y1 <= limit and not between and last_full and not_indented and goes_on:
                target["lines"] += it["lines"]
                target["line_rects"] += it["line_rects"]
                target["rect"] = a | b
                target["chars"] += it["chars"]
                continue
        out.append(it)
    pg.items = out


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
            if not zone and PAGE_NUMBER_RE.match(" ".join(it["lines"])) and (bottom < 0.15 or top > 0.8):
                zone = "header" if bottom < 0.15 else "footer"
            if not zone:
                continue
            key = (zone, _norm(" ".join(it["lines"])))
            it["_zone"], it["_key"] = zone, key
            seen[key] += 1
    threshold = max(2, min(3, int(len(pages) * 0.3)))
    for pg in pages:
        for it in pg.items:
            zone = it.get("_zone")
            if not zone:
                continue
            text = " ".join(it["lines"])
            if PAGE_NUMBER_RE.match(text):
                it["noise"] = "page_number"
            elif seen[it["_key"]] >= threshold and len(text) < 200 \
                    and not CHAPTER_RE.match(_join_lines(it["lines"])) and not FRONT_RE.match(_join_lines(it["lines"])):
                it["noise"] = zone


def _mark_sidebars(pages, body):
    """A sidebar is text in a smaller size in a narrow column beside the body text, such as
    quotations in the margin. It is read after the body text of its page, as its own stream,
    so that it never cuts a body paragraph in two (rulebook 10.1)."""
    for pg in pages:
        w = pg.rect.width or 1
        main = [it for it in pg.items if it["kind"] == "text" and not it.get("noise") and _same_size(it["size"], body)]
        side = [it for it in pg.items if it["kind"] == "text" and not it.get("noise") and it["size"] < body
                and not _same_size(it["size"], body) and it["rect"].width < 0.4 * w
                and not CAPTION_RE.match(" ".join(it["lines"]))
                and all(it["rect"].x0 >= m["rect"].x1 - 2 or it["rect"].x1 <= m["rect"].x0 + 2 for m in main)]
        if main and len(side) >= 2:
            for it in side:
                it["side"] = True


def _order(items, rect):
    side = sorted((it for it in items if it.get("side")), key=lambda i: (i["rect"].y0, i["rect"].x0))
    if side:
        return _order([it for it in items if not it.get("side")], rect) + side
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
    e = _plain_element(it, text, body, levels)
    if len(lines) <= 2 and (CHAPTER_RE.match(text) or FRONT_RE.match(text)):
        e["_chapter"] = "part" if PART_RE.match(text) else "chapter" if CHAPTER_RE.match(text) else "front"
        e["_text"] = re.sub(r"\s+([.,:;])", r"\1", text)
    return e


def _plain_element(it, text, body, levels):
    lines = it["lines"]
    size = it["size"]
    short = len(text) <= 160 and len(lines) <= 3 and not text.endswith(HEADING_END)
    if short and (size in levels or (it["bold"] and size >= body)):
        level = levels.get(size, min(6, len(levels) + 1))
        return {"type": "heading", "level": level, "md": "#" * level + " " + text}
    if _is_list(lines):
        items = []
        for ln in lines:
            m = BULLET_RE.match(ln)
            if m:
                n = NUMBER_RE.match(ln)
                if n:
                    items.append("%s. " % n.group(1) + m.group(2).strip())
                elif m.group(1)[:1].isalnum() or m.group(1)[:1] == "(":
                    items.append("- " + m.group(1) + " " + m.group(2).strip())
                else:
                    items.append("- " + m.group(2).strip())
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


def _lost_initials(els):
    """A drop cap that is only a picture leaves the first word of a chapter without its first
    letter ("IR WALTER" for "SIR WALTER"). When that word never occurs elsewhere in the document
    and one capital letter in front of it makes a word the document uses often, clearly more
    often than with any other letter, the letter is put back (rulebook 10.1, rule 12)."""
    vocab = Counter(w.lower() for e in els for w in re.findall(r"[^\W\d_]+", e.get("md", "")))
    for i, e in enumerate(els[:-1]):
        nxt = els[i + 1]
        if e["type"] != "heading" or nxt["type"] != "paragraph":
            continue
        m = re.match(r"([^\W\d_]+)", nxt["md"])
        if not m or not m.group(1).isupper() or vocab[m.group(1).lower()] > 1:
            continue
        word = m.group(1)
        counts = sorted(((vocab[(c + word).lower()], c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), reverse=True)
        (best, letter), (second, _) = counts[0], counts[1]
        if best >= 5 and best >= 3 * max(second, 1):
            nxt["md"] = letter + nxt["md"]


def _number_headings(els):
    """A chapter number printed on its own line above the title ("6", then "Anxiety") is one
    heading with the title: "6 Anxiety" (rulebook 10.1)."""
    for i in range(len(els) - 2, -1, -1):
        e, nxt = els[i], els[i + 1]
        num = re.sub(r"^#{1,6}\s*", "", e["md"]) if e["type"] == "heading" else ""
        if re.fullmatch(r"\d{1,3}|[IVXLC]{1,7}", num) and nxt["type"] == "heading" and nxt.get("page") == e.get("page"):
            level = min(e["level"], nxt["level"])
            nxt["level"], nxt["md"] = level, "#" * level + " " + num + " " + re.sub(r"^#{1,6}\s*", "", nxt["md"])
            nxt["bbox"] = [min(e["bbox"][0], nxt["bbox"][0]), min(e["bbox"][1], nxt["bbox"][1]),
                           max(e["bbox"][2], nxt["bbox"][2]), max(e["bbox"][3], nxt["bbox"][3])]
            del els[i]


def _chapters(els):
    """Books: when at least MIN_CHAPTERS lines read "Chapter I", "Part Two" and the like, those
    lines are the headings (parts level 1, chapters below them), headings before the first one
    are front matter and become paragraphs, and the first one is where the body starts
    (rulebook 10.1). Returns that element, or None."""
    marked = [e for e in els if e.get("_chapter") and e["type"] != "noise"]
    if sum(1 for e in marked if e["_chapter"] != "front") < MIN_CHAPTERS:
        return None
    parts = any(e["_chapter"] == "part" for e in marked)
    for e in marked:
        level = 2 if parts and e["_chapter"] != "part" else 1
        e["type"], e["level"], e["md"] = "heading", level, "#" * level + " " + e["_text"]
    first = marked[0]
    for e in els[:els.index(first)]:
        if e["type"] == "heading":
            e["type"], e["md"] = "paragraph", re.sub(r"^#{1,6}\s+", "", e["md"])
            del e["level"]
    return first


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


def _rejoin_tails(page_els, body):
    """A paragraph that starts in lower case, in the same column directly below or inside a
    paragraph that stops mid-sentence, is the rest of that paragraph: the text layer cut it
    off, often with a wrong font size ("was .", "room.") (rulebook 10.1, rule 12)."""
    line = 1.6 * (body or 10)
    paras = [p for p in page_els if p["type"] == "paragraph" and p.get("_rect") is not None]

    def runs_to_margin(p):
        if p.get("_full") is not None:
            return p["_full"]
        right = max((q["_rect"].x1 for q in paras if q.get("_side") == p.get("_side")
                     and min(q["_rect"].x1, p["_rect"].x1) > max(q["_rect"].x0, p["_rect"].x0)), default=p["_rect"].x1)
        return p["_rect"].x1 >= right - 1.5 * (body or 10)

    def column_left(p):
        return min((q["_rect"].x0 for q in paras if q.get("_side") == p.get("_side")
                    and min(q["_rect"].x1, p["_rect"].x1) > max(q["_rect"].x0, p["_rect"].x0)), default=p["_rect"].x0)

    out = []
    for e in page_els:
        r = e.get("_rect")
        host = None
        if e["type"] == "paragraph" and r is not None and e["md"][:1].islower():
            near = [p for p in out if p["type"] == "paragraph" and p.get("_side") == e.get("_side")
                    and not p["md"].rstrip().endswith(SENTENCE_END) and p["_rect"].y0 <= r.y0 <= p["_rect"].y1 + line
                    and r.x0 < p["_rect"].x1 and r.x0 >= column_left(p) - 2 * (body or 10)]
            host = max(near, key=lambda p: p["_rect"].y1) if near else None
            if host is not None and not (runs_to_margin(host) or e.get("_side")):
                host = None
        if host is None:
            out.append(e)
            continue
        joiner = SOFT if re.search(r"\w-$", host["md"]) else " "
        host["md"] = (host["md"][:-1] if joiner == SOFT else host["md"]) + joiner + e["md"]
        host["_rect"] = host["_rect"] | r
        host["bbox"] = _bbox(host["_rect"], host["_page_rect"])
        host["_full"] = e.get("_full")
    return out


def _trailing_numbers(page_els):
    """A number standing alone below all the text of its page, such as a printer's sheet mark
    at the end of a chapter, is a page mark: noise, not a paragraph (rulebook 10.1, rule 11)."""
    for e in page_els:
        if e["type"] != "paragraph" or not re.fullmatch(r"\d{1,3}", e["md"].strip()) or e.get("_rect") is None:
            continue
        others = [o for o in page_els if o is not e and o["type"] != "noise" and o.get("_rect") is not None]
        if others and all(o["_rect"].y1 <= e["_rect"].y0 + 2 for o in others):
            e["type"], e["subtype"] = "noise", "page_number"
    return page_els


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
    _mark_sidebars(pages, body)
    indent_style = _indent_style(pages, body)
    for pg in pages:
        _merge_paragraphs(pg, body, indent_style)
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
                e["_indented"], e["_full"], e["_side"] = _indented(it), _full_last(it), bool(it.get("side"))
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
        page_els = _trailing_numbers(_rejoin_tails(_merge_lists(page_els), body))
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

    _resolve_hyphens(els)
    _number_headings(els)
    start = _chapters(els)
    _lost_initials(els)
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

    last = {}
    for e in els:
        if e["type"] in ("noise", "caption", "image"):
            continue
        prev = last.get(e.get("_side", False))
        last[e.get("_side", False)] = e
        if prev is not None and e["type"] == "paragraph" and prev["type"] == "paragraph" \
                and e["page"] == prev["page"] + 1 and e.get("_indented") is not True \
                and (not prev["md"].endswith(SENTENCE_END) and (e["md"][:1].islower() or prev.get("_full"))
                     or indent_style and prev.get("_full") and e.get("_indented") is False):
            e["continues"] = prev["id"]

    meta = pdf.metadata or {}
    h = {"type": "document", "doc": doc, "source": path.name, "converter": "fmjl pdf 1.1"}
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
    if start is not None and start is not els[0]:
        h["meta"]["fmjl.body"] = start["id"]
    rows = fmjl.fill([h] + els, base=path.parent)
    return rows, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fmjl pdf", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--output", help="output .fmjl (default: same name next to the PDF)")
    ap.add_argument("--doc", help="document name (default: from the file name)")
    ap.add_argument("--md", action="store_true", help="also write the .md authoring form next to the .fmjl")
    ap.add_argument("--no-md", action="store_true", help=argparse.SUPPRESS)
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
    if a.md and not a.no_md:
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
