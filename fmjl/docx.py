#!/usr/bin/env python3
"""fmjl.docx - Word importer for FMJL, rulebook version 1.1.

  fmjl report.docx                   writes report.fmjl and images/ (add --md for report.md too)
  fmjl docx report.docx [-o report.fmjl] [--doc name]

A .docx file already knows its structure, so the importer reads it directly:
  headings      from the Heading 1..6 and Title styles (or the outline level)
  lists         from Word numbering; bullets and numbers are kept apart
  tables        merged cells become an HTML table with rowspan and colspan
  images        saved into images/, captions linked with reference=
  formulas      Word math (OMML) becomes LaTeX: display math as a formula element, inline as $...$
  footnotes     one footnote element after the paragraph that cites it
  noise         the section header and footer
  page          from the page breaks Word recorded when it last saved the file
Needs nothing beyond Python. Images in EMF or WMF are converted when PyMuPDF
is installed, otherwise reported.

Copyright (c) 2026 Rupak Kumar. MIT License, see LICENSE.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fmjl

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
}
IMAGE_EXT = {".png": "png", ".jpg": "jpg", ".jpeg": "jpeg", ".webp": "webp", ".svg": "svg"}
CONVERTIBLE = {".gif", ".bmp", ".tif", ".tiff", ".pnm", ".jp2"}


def _w(tag):
    return "{%s}%s" % (NS["w"], tag)


def _q(prefix, tag):
    return "{%s}%s" % (NS[prefix], tag)


def _val(el, name, default=None):
    if el is None:
        return default
    return el.get(_w("val"), default)


def _on(rpr, tag):
    el = rpr.find("w:" + tag, NS) if rpr is not None else None
    if el is None:
        return False
    return el.get(_w("val"), "true") not in ("0", "false", "off")


SYMBOLS = {
    "\u2211": "\\sum", "\u220f": "\\prod", "\u222b": "\\int", "\u222c": "\\iint", "\u222e": "\\oint",
    "\u00b1": "\\pm", "\u2213": "\\mp", "\u2264": "\\le", "\u2265": "\\ge", "\u2260": "\\ne",
    "\u00d7": "\\times", "\u00f7": "\\div", "\u22c5": "\\cdot", "\u00b7": "\\cdot", "\u221e": "\\infty",
    "\u2192": "\\to", "\u2190": "\\leftarrow", "\u21d2": "\\Rightarrow", "\u21d4": "\\Leftrightarrow",
    "\u2212": "-", "\u2202": "\\partial", "\u2207": "\\nabla", "\u2208": "\\in", "\u2209": "\\notin",
    "\u2282": "\\subset", "\u2286": "\\subseteq", "\u222a": "\\cup", "\u2229": "\\cap",
    "\u2200": "\\forall", "\u2203": "\\exists", "\u2248": "\\approx", "\u2261": "\\equiv",
    "\u223c": "\\sim", "\u221d": "\\propto", "\u2026": "\\ldots", "\u22ef": "\\cdots", "\u00b0": "^\\circ",
    "\u2032": "'", "\u221a": "\\sqrt", "\u2205": "\\emptyset", "\u00ac": "\\neg", "\u2227": "\\wedge",
    "\u2228": "\\vee", "\u2225": "\\parallel", "\u22a5": "\\perp", "\u2220": "\\angle", "\u210f": "\\hbar",
    "{": "\\{", "}": "\\}", "%": "\\%", "&": "\\&", "#": "\\#", "_": "\\_",
}
GREEK = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho "
         "sigma tau upsilon phi chi psi omega").split()
for _i, _name in enumerate(GREEK):
    SYMBOLS[chr(0x3b1 + _i + (1 if _i >= 17 else 0))] = "\\" + _name
    up = _name.capitalize()
    if up in ("Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega"):
        SYMBOLS[chr(0x391 + _i + (1 if _i >= 17 else 0))] = "\\" + up
SYMBOLS["\u03c2"] = "\\varsigma"


def _latex_text(text):
    out = []
    for ch in text:
        rep = SYMBOLS.get(ch)
        if rep is None:
            out.append(ch)
        elif rep.startswith("\\") and rep[1:].isalpha():
            out.append(rep + " ")
        else:
            out.append(rep)
    return re.sub(r" +([^A-Za-z])", r"\1", "".join(out)).strip()


def _m(tag):
    return "{%s}%s" % (NS["m"], tag)


def _omml(el):
    """OMML (Word math) to LaTeX. Unknown parts fall back to the text of their runs."""
    tag = el.tag
    if tag == _m("t"):
        return _latex_text(el.text or "")
    if tag == _m("r"):
        return "".join(_omml(c) for c in el if c.tag == _m("t"))
    if tag == _m("f"):
        return "\\frac{%s}{%s}" % (_omml_child(el, "num"), _omml_child(el, "den"))
    if tag == _m("sSup"):
        return "%s^{%s}" % (_omml_base(el), _omml_child(el, "sup"))
    if tag == _m("sSub"):
        return "%s_{%s}" % (_omml_base(el), _omml_child(el, "sub"))
    if tag == _m("sSubSup"):
        return "%s_{%s}^{%s}" % (_omml_base(el), _omml_child(el, "sub"), _omml_child(el, "sup"))
    if tag == _m("sPre"):
        return "{}_{%s}^{%s}%s" % (_omml_child(el, "sub"), _omml_child(el, "sup"), _omml_base(el))
    if tag == _m("rad"):
        deg = _omml_child(el, "deg")
        return ("\\sqrt[%s]{%s}" % (deg, _omml_child(el, "e"))) if deg else "\\sqrt{%s}" % _omml_child(el, "e")
    if tag == _m("d"):
        pr = el.find("m:dPr", NS)
        beg = _val_m(pr, "begChr", "(")
        end = _val_m(pr, "endChr", ")")
        sep = _val_m(pr, "sepChr", ",")
        inner = sep.join(_omml(e) for e in el.findall("m:e", NS))
        left = "\\left" + (_latex_text(beg) if beg else ".")
        right = "\\right" + (_latex_text(end) if end else ".")
        return "%s%s%s" % (left, inner, right)
    if tag == _m("nary"):
        pr = el.find("m:naryPr", NS)
        op = _latex_text(_val_m(pr, "chr", "\u222b"))
        sub, sup = _omml_child(el, "sub"), _omml_child(el, "sup")
        return op + ("_{%s}" % sub if sub else "") + ("^{%s}" % sup if sup else "") + " " + _omml_child(el, "e")
    if tag == _m("func"):
        name = _omml_child(el, "fName")
        return ("\\%s " % name if name.isalpha() else name) + _omml_child(el, "e")
    if tag == _m("bar"):
        return "\\overline{%s}" % _omml_child(el, "e")
    if tag == _m("acc"):
        ch = _val_m(el.find("m:accPr", NS), "chr", "\u0302")
        names = {"\u0302": "hat", "\u0303": "tilde", "\u0307": "dot", "\u0308": "ddot", "\u0304": "bar",
                 "\u20d7": "vec", "\u0306": "breve", "\u030c": "check"}
        return "\\%s{%s}" % (names.get(ch, "hat"), _omml_child(el, "e"))
    if tag == _m("limLow"):
        return "%s_{%s}" % (_omml_child(el, "e"), _omml_child(el, "lim"))
    if tag == _m("limUpp"):
        return "%s^{%s}" % (_omml_child(el, "e"), _omml_child(el, "lim"))
    if tag == _m("groupChr"):
        return "\\underbrace{%s}" % _omml_child(el, "e")
    if tag == _m("m"):
        rows = [" & ".join(_omml(e) for e in mr.findall("m:e", NS)) for mr in el.findall("m:mr", NS)]
        return "\\begin{matrix}%s\\end{matrix}" % " \\\\ ".join(rows)
    if tag == _m("eqArr"):
        return "\\begin{aligned}%s\\end{aligned}" % " \\\\ ".join(_omml(e) for e in el.findall("m:e", NS))
    if tag in (_m("box"), _m("borderBox"), _m("phant"), _m("e"), _m("oMath"), _m("oMathPara"), _m("num"),
               _m("den"), _m("sub"), _m("sup"), _m("deg"), _m("lim"), _m("fName")):
        return "".join(_omml(c) for c in el if not c.tag.endswith("Pr"))
    if tag.endswith("Pr") or tag == _m("ctrlPr"):
        return ""
    return "".join(_omml(c) for c in el)


def _omml_child(el, name):
    c = el.find("m:" + name, NS)
    return _omml(c) if c is not None else ""


def _omml_base(el):
    base = _omml_child(el, "e")
    return base if len(base) == 1 or base.startswith("\\") and base[1:].isalpha() else "{%s}" % base


def _val_m(pr, name, default):
    if pr is None:
        return default
    c = pr.find("m:" + name, NS)
    if c is None:
        return default
    return c.get(_m("val"), default)


class _Docx:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        self.names = set(self.zip.namelist())
        self.rels = self._rels("word/_rels/document.xml.rels")
        self.styles = self._styles()
        self.numbering = self._numbering()
        self.footnotes = {}
        self.footnotes = self._notes("word/footnotes.xml", "footnote")
        self.warnings = []

    def xml(self, name):
        return ET.fromstring(self.zip.read(name)) if name in self.names else None

    def _rels(self, name):
        root = self.xml(name)
        out = {}
        if root is not None:
            for rel in root.findall("rel:Relationship", NS):
                out[rel.get("Id")] = (rel.get("Target"), rel.get("TargetMode"))
        return out

    def _styles(self):
        root = self.xml("word/styles.xml")
        out = {}
        if root is None:
            return out
        for st in root.findall("w:style", NS):
            sid = st.get(_w("styleId"))
            name = _val(st.find("w:name", NS), "val", sid) or sid
            based = _val(st.find("w:basedOn", NS), "val")
            numpr = st.find("w:pPr/w:numPr", NS)
            out[sid] = (name.lower(), based, numpr)
        return out

    def style_ids(self, sid):
        seen = []
        while sid and sid in self.styles and sid not in seen:
            seen.append(sid)
            sid = self.styles[sid][1]
        return seen

    def style_chain(self, sid):
        return [self.styles[s][0] for s in self.style_ids(sid)]

    def style_numpr(self, sid):
        for s in self.style_ids(sid):
            if self.styles[s][2] is not None:
                return self.styles[s][2]
        return None

    def _numbering(self):
        root = self.xml("word/numbering.xml")
        out = {}
        if root is None:
            return out
        abstract = {}
        for an in root.findall("w:abstractNum", NS):
            levels = {}
            for lvl in an.findall("w:lvl", NS):
                levels[int(lvl.get(_w("ilvl"), "0"))] = _val(lvl.find("w:numFmt", NS), "val", "bullet")
            abstract[an.get(_w("abstractNumId"))] = levels
        for num in root.findall("w:num", NS):
            aid = _val(num.find("w:abstractNumId", NS), "val")
            out[num.get(_w("numId"))] = abstract.get(aid, {})
        return out

    def _notes(self, name, tag):
        root = self.xml(name)
        out = {}
        if root is None:
            return out
        for note in root.findall("w:" + tag, NS):
            nid = note.get(_w("id"))
            if note.get(_w("type")) in ("separator", "continuationSeparator"):
                continue
            paras = [self.para_md(p)[0] for p in note.findall(".//w:p", NS)]
            out[nid] = " ".join(t for t in paras if t).strip()
        return out

    def image_target(self, rid):
        target = self.rels.get(rid)
        if not target or target[1] == "External":
            return None
        name = "word/" + target[0].lstrip("/") if not target[0].startswith("word/") else target[0]
        return name if name in self.names else None

    def para_md(self, p, plain=False):
        """Returns (markdown text, tokens). Tokens: ('image', name, alt), ('footnote', id), ('pagebreak',)."""
        parts, tokens = [], []
        self._walk(p, parts, tokens, plain)
        text = "".join(parts)
        text = re.sub(r"[ \t]+", " ", text).strip()
        text = re.sub(r"\*\*\s*\*\*", "", text)
        return text, tokens

    def _walk(self, el, parts, tokens, plain):
        for child in el:
            tag = child.tag
            if tag == _w("r"):
                self._run(child, parts, tokens, plain)
            elif tag == _w("hyperlink"):
                inner, inner_tokens = [], []
                self._walk(child, inner, inner_tokens, True)
                tokens.extend(inner_tokens)
                text = "".join(inner).strip()
                target = self.rels.get(child.get(_q("r", "id")))
                if target and target[1] == "External" and text and not plain:
                    parts.append(f"[{text}]({target[0]})")
                else:
                    parts.append(text)
            elif tag in (_w("del"), _w("moveFrom"), _w("proofErr"), _w("bookmarkStart"), _w("bookmarkEnd")):
                continue
            elif tag in (_q("m", "oMath"), _q("m", "oMathPara")):
                latex = re.sub(r"\s+", " ", _omml(child)).strip()
                if latex:
                    parts.append("$" + latex + "$")
                    tokens.append(("math", latex, tag == _q("m", "oMathPara")))
            else:
                self._walk(child, parts, tokens, plain)

    def _run(self, r, parts, tokens, plain):
        rpr = r.find("w:rPr", NS)
        bold, italic = (not plain) and _on(rpr, "b"), (not plain) and _on(rpr, "i")
        buf = []
        for child in r:
            tag = child.tag
            if tag == _w("t"):
                buf.append((child.text or "").replace("\u00ad", ""))
            elif tag == _w("noBreakHyphen"):
                buf.append("-")
            elif tag == _w("tab"):
                buf.append(" ")
            elif tag == _w("br"):
                if child.get(_w("type")) == "page":
                    tokens.append(("pagebreak",))
                else:
                    buf.append(" ")
            elif tag == _w("lastRenderedPageBreak"):
                tokens.append(("pagebreak",))
            elif tag == _w("footnoteReference"):
                nid = child.get(_w("id"))
                if nid in self.footnotes:
                    tokens.append(("footnote", nid))
                    buf.append(f"[^{nid}]")
            elif tag in (_w("drawing"), _w("pict"), _w("object")):
                for blip in child.iter(_q("a", "blip")):
                    tokens.append(("image", blip.get(_q("r", "embed")), self._alt(child)))
                for img in child.iter(_q("v", "imagedata")):
                    tokens.append(("image", img.get(_q("r", "id")), self._alt(child)))
            elif tag == _w("sym"):
                buf.append("")
        text = "".join(buf)
        if not text:
            return
        if bold or italic:
            lead = text[:len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            core = text.strip()
            if core:
                mark = "**" if bold else ""
                mark2 = "*" if italic else ""
                text = lead + mark + mark2 + core + mark2 + mark + trail
        parts.append(text)

    def _alt(self, drawing):
        for pr in drawing.iter(_q("wp", "docPr")):
            return (pr.get("descr") or pr.get("title") or pr.get("name") or "").strip()
        return ""


def _cell_text(docx, tc):
    paras = [docx.para_md(p)[0] for p in tc.findall(".//w:p", NS)]
    return " ".join(t for t in paras if t).strip()


def _table(docx, tbl):
    rows, merged = [], False
    for tr in tbl.findall("w:tr", NS):
        row = []
        for tc in tr.findall("w:tc", NS):
            pr = tc.find("w:tcPr", NS)
            span = int(_val(pr.find("w:gridSpan", NS) if pr is not None else None, "val", "1") or 1)
            vm = pr.find("w:vMerge", NS) if pr is not None else None
            vmerge = None if vm is None else (vm.get(_w("val")) or "continue")
            if span > 1 or vmerge:
                merged = True
            row.append({"text": _cell_text(docx, tc), "span": span, "vmerge": vmerge})
        rows.append(row)
    if not rows:
        return None
    if not merged:
        width = max(len(r) for r in rows)
        grid = [[c["text"].replace("|", "\\|") for c in r] + [""] * (width - len(r)) for r in rows]
        lines = [fmjl._pipe_row(grid[0]), fmjl._pipe_row(["---"] * width)] + [fmjl._pipe_row(r) for r in grid[1:]]
        return {"type": "table", "md": "\n".join(lines)}
    out = ["<table>"]
    for ri, row in enumerate(rows):
        cells, col = [], 0
        for c in row:
            if c["vmerge"] == "continue":
                col += c["span"]
                continue
            rowspan = 1
            if c["vmerge"] == "restart":
                for below in rows[ri + 1:]:
                    cc = 0
                    hit = None
                    for b in below:
                        if cc == col:
                            hit = b
                            break
                        cc += b["span"]
                    if hit is not None and hit["vmerge"] == "continue":
                        rowspan += 1
                    else:
                        break
            attrs = (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (f' colspan="{c["span"]}"' if c["span"] > 1 else "")
            tag = "th" if ri == 0 else "td"
            cells.append(f"<{tag}{attrs}>{html.escape(c['text'], quote=False)}</{tag}>")
            col += c["span"]
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    h = "\n".join(out)
    return {"type": "table", "html": h, "md": fmjl.html_table_to_md(h)}


def _body_children(el):
    for child in el:
        if child.tag in (_w("p"), _w("tbl")):
            yield child
        elif child.tag == _w("sdt"):
            content = child.find("w:sdtContent", NS)
            if content is not None:
                yield from _body_children(content)
        elif child.tag in (_w("ins"), _w("moveTo")):
            yield from _body_children(child)


def _heading_level(docx, p, style_names, shift=0):
    for name in style_names:
        m = re.match(r"^(heading|überschrift|titre)\s*(\d)$", name)
        if m:
            return int(m.group(2)) + shift
        if name == "title":
            return 1
    ppr = p.find("w:pPr", NS)
    lvl = _val(ppr.find("w:outlineLvl", NS) if ppr is not None else None, "val")
    if lvl is not None and lvl.isdigit() and int(lvl) < 9:
        return int(lvl) + 1
    return None


def _list_info(docx, p, sid, style_names):
    ppr = p.find("w:pPr", NS)
    numpr = ppr.find("w:numPr", NS) if ppr is not None else None
    if numpr is None:
        numpr = docx.style_numpr(sid)
    if numpr is None:
        if any(n.startswith("list bullet") for n in style_names):
            return 0, "bullet"
        if any(n.startswith("list number") for n in style_names):
            return 0, "decimal"
        return None
    num_id = _val(numpr.find("w:numId", NS), "val")
    ilvl = int(_val(numpr.find("w:ilvl", NS), "val", "0") or 0)
    if num_id == "0" or num_id is None:
        return None
    fmt = docx.numbering.get(num_id, {}).get(ilvl, "bullet")
    return ilvl, fmt


def _is_code(p, style_names):
    if any("code" in n or "source" in n or "html" in n for n in style_names):
        return True
    runs = p.findall(".//w:r", NS)
    fonts = []
    for r in runs:
        rpr = r.find("w:rPr", NS)
        f = rpr.find("w:rFonts", NS) if rpr is not None else None
        fonts.append((f.get(_w("ascii")) or "") if f is not None else "")
    return bool(runs) and all(re.search(r"consolas|courier|mono", f, re.I) for f in fonts)


def _save_image(docx, name, out_dir, doc, id_, warnings):
    data = docx.zip.read(name)
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXT:
        rel = f"images/{doc}_{id_}.{IMAGE_EXT[ext]}"
        (out_dir / "images").mkdir(parents=True, exist_ok=True)
        (out_dir / rel).write_bytes(data)
        return rel
    if ext in CONVERTIBLE:
        try:
            import pymupdf
            pix = pymupdf.Pixmap(data)
            if pix.n - pix.alpha >= 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            rel = f"images/{doc}_{id_}.png"
            (out_dir / "images").mkdir(parents=True, exist_ok=True)
            pix.save(str(out_dir / rel))
            return rel
        except Exception as e:
            warnings.append(f"{name}: could not convert to PNG ({e})")
            return None
    warnings.append(f"{name}: {ext} images are not supported; export it as PNG in Word")
    return None


def _meta(docx):
    root = docx.xml("docProps/core.xml")
    h = {}
    if root is None:
        return h
    title = root.findtext("dc:title", default="", namespaces=NS).strip()
    creator = root.findtext("dc:creator", default="", namespaces=NS).strip()
    created = root.findtext("dcterms:created", default="", namespaces=NS).strip()
    if title:
        h["title"] = title
    if creator:
        h["authors"] = [a.strip() for a in re.split(r"[;,]", creator) if a.strip()]
    m = re.match(r"(\d{4}-\d{2}-\d{2})", created)
    if m:
        h["date"] = m.group(1)
    return h


def import_docx(path, doc=None, out_dir=None):
    path = Path(path)
    out_dir = Path(out_dir) if out_dir else path.parent
    doc = doc or re.sub(r"[^a-z0-9_-]+", "_", path.stem.lower()).strip("_") or "document"
    docx = _Docx(path)
    body = docx.xml("word/document.xml").find("w:body", NS)
    els, page = [], 0
    pages_seen = any(True for _ in body.iter(_w("lastRenderedPageBreak"))) or \
        any(br.get(_w("type")) == "page" for br in body.iter(_w("br")))
    shift = 0
    for p in body.iter(_w("p")):
        ppr = p.find("w:pPr", NS)
        sid = _val(ppr.find("w:pStyle", NS) if ppr is not None else None, "val")
        if sid and "title" in docx.style_chain(sid):
            shift = 1
            break

    def add(e):
        if pages_seen:
            e["page"] = page
        els.append(e)
        return e

    for name in sorted(n for n in docx.names if re.match(r"word/header\d*\.xml$", n)):
        root = docx.xml(name)
        text = " ".join(t for t in (docx.para_md(p)[0] for p in root.iter(_w("p"))) if t).strip()
        if text:
            add({"type": "noise", "subtype": "header", "md": text})

    list_run = None
    for child in _body_children(body):
        if child.tag == _w("tbl"):
            list_run = None
            t = _table(docx, child)
            if t:
                add(t)
            continue
        ppr = child.find("w:pPr", NS)
        sid = _val(ppr.find("w:pStyle", NS) if ppr is not None else None, "val")
        style_names = docx.style_chain(sid) if sid else []
        level = _heading_level(docx, child, style_names, shift)
        text, tokens = docx.para_md(child, plain=level is not None)
        for tok in tokens:
            if tok[0] == "pagebreak":
                page += 1
        images = [t for t in tokens if t[0] == "image"]
        for _, rid, alt in images:
            target = docx.image_target(rid)
            if target:
                add({"type": "image", "md": alt, "_zip": target})
        maths = [t for t in tokens if t[0] == "math"]
        if len(maths) == 1 and maths[0][2] and text == "$" + maths[0][1] + "$":
            list_run = None
            add({"type": "formula", "latex": maths[0][1], "md": "$$" + maths[0][1] + "$$"})
            continue
        if not text:
            if not images:
                list_run = None
            continue
        li = _list_info(docx, child, sid, style_names)
        if level:
            list_run = None
            add({"type": "heading", "level": min(level, 6), "md": "#" * min(level, 6) + " " + text})
        elif li is not None:
            ilvl, fmt = li
            if not (list_run is not None and els and els[-1] is list_run):
                list_run = add({"type": "list", "md": "", "_counts": {}})
            counts = list_run["_counts"]
            counts[ilvl] = counts.get(ilvl, 0) + 1
            for deeper in [k for k in counts if k > ilvl]:
                del counts[deeper]
            marker = "- " if fmt == "bullet" else f"{counts[ilvl]}. "
            list_run["md"] += ("\n" if list_run["md"] else "") + "  " * ilvl + marker + text
        elif any(n == "caption" for n in style_names):
            list_run = None
            add({"type": "caption", "md": text, "_caption": True})
        elif any("quote" in n for n in style_names):
            list_run = None
            add({"type": "quote", "md": "> " + text})
        elif _is_code(child, style_names):
            list_run = None
            plain = docx.para_md(child, plain=True)[0]
            if els and els[-1].get("_code"):
                els[-1]["md"] = els[-1]["md"][:-4] + "\n" + plain + "\n```"
            else:
                add({"type": "code", "md": "```\n" + plain + "\n```", "_code": True})
        else:
            list_run = None
            add({"type": "paragraph", "md": text})
        for tok in tokens:
            if tok[0] == "footnote":
                add({"type": "footnote", "md": f"[^{tok[1]}]: {docx.footnotes[tok[1]]}", "_cites": els[-1] if els[-1]["type"] != "footnote" else els[-2]})

    for name in sorted(n for n in docx.names if re.match(r"word/footer\d*\.xml$", n)):
        root = docx.xml(name)
        text = " ".join(t for t in (docx.para_md(p)[0] for p in root.iter(_w("p"))) if t).strip()
        if text:
            e = {"type": "noise", "subtype": "footer", "md": text}
            if pages_seen:
                e["page"] = page
            els.append(e)

    for i, e in enumerate(els):
        if not e.pop("_caption", False):
            continue
        wants = "table" if e["md"].lower().startswith("table") else "image"
        order = (i + 1, i - 1) if wants == "table" else (i - 1, i + 1)
        target = None
        for want in (wants, None):
            for j in order:
                if 0 <= j < len(els) and els[j]["type"] in ("image", "table") and (want is None or els[j]["type"] == want):
                    target = els[j]
                    break
            if target is not None:
                break
        if target is None:
            e["type"] = "paragraph"
        else:
            e["_target"] = target
            if target["type"] == "image" and re.match(r"^(picture|image|graphic|figure)?\s*\d*$", target["md"], re.I):
                target["md"] = e["md"]

    prev = 0
    for e in els:
        if e["type"] != "heading":
            continue
        if e["level"] > prev + 1:
            e["level"] = prev + 1
            e["md"] = "#" * e["level"] + " " + re.sub(r"^#+\s*", "", e["md"])
        prev = e["level"]
    for n, e in enumerate(els, 1):
        e["id"] = f"{doc}#e{n}"
    keep = []
    for e in els:
        e.pop("_code", None)
        if "_target" in e:
            e["reference"] = e.pop("_target")["id"]
        if "_cites" in e:
            e["reference"] = e.pop("_cites")["id"]
        if "_zip" in e:
            rel = _save_image(docx, e.pop("_zip"), out_dir, doc, e["id"].rsplit("#", 1)[1], docx.warnings)
            if not rel:
                continue
            e["file"] = rel
            if not e["md"]:
                e["md"] = "Image " + e["id"].rsplit("#e", 1)[1]
        keep.append(e)

    h = {"type": "document", "doc": doc, "source": path.name, "converter": "fmjl docx 1.1"}
    h.update(_meta(docx))
    ins = sum(1 for _ in body.iter(_w("ins"))) + sum(1 for _ in body.iter(_w("moveTo")))
    dels = sum(1 for _ in body.iter(_w("del"))) + sum(1 for _ in body.iter(_w("moveFrom")))
    if ins or dels:
        h["meta"] = {"fmjl.tracked_changes": {"insertions": ins, "deletions": dels}}
        docx.warnings.append(f"tracked changes: {ins} insertion(s) kept and {dels} deletion(s) dropped; "
                             "accept or reject the changes in Word to be sure")
    if "title" not in h:
        for e in keep:
            if e["type"] == "heading" and e["level"] == 1:
                h["title"] = e["md"][2:]
                break
    if pages_seen:
        h.setdefault("meta", {})["pages"] = page + 1
    rows = fmjl.fill([h] + keep, base=path.parent)
    return rows, docx.warnings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fmjl docx", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--output", help="output .fmjl (default: same name next to the .docx)")
    ap.add_argument("--doc", help="document name (default: from the file name)")
    ap.add_argument("--md", action="store_true", help="also write the .md authoring form next to the .fmjl")
    ap.add_argument("--no-md", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    path = Path(a.file)
    out = Path(a.output) if a.output else path.with_suffix(".fmjl")
    try:
        rows, warnings = import_docx(path, doc=a.doc, out_dir=out.parent)
    except (ValueError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile) as e:
        print(f"error: {e}")
        return 2
    fmjl.write_rows(out, rows)
    print(f"wrote {out} ({len(rows) - 1} elements)")
    if a.md and not a.no_md:
        md = out.with_suffix(".md")
        fmjl.write_text(md, fmjl.export_md(rows))
        print(f"wrote {md}")
    for w in dict.fromkeys(warnings):
        print("warning: " + w)
    return fmjl._report(fmjl.check(out))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
