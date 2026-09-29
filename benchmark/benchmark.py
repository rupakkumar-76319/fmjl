"""Format benchmark: the same document in FMJL, Markdown, JSON and LaTeX.

The document (75 sentences, 2 formulas, 1 table, 1 image with a caption) is defined once
below as the ground truth. Each format has a writer (truth -> file) and a reader
(file -> elements). Every reader's output is scored against the truth.

Run: python benchmark.py        (needs fmjl.py next to it, markdown-it-py, jsonschema, pylatexenc)
"""

import copy
import io
import difflib
import gzip
import json
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

import fmjl
from markdown_it import MarkdownIt
from pylatexenc.latex2text import LatexNodes2Text

TITLE, AUTHOR = "Solar Power for Village Schools", "Format X Test Team"
IMAGE = "images/solar_panels.png"

P = [
    ["Many village schools lose electricity for several hours every day.",
     "Without power, fans stop, lights go out, and computers cannot be used.",
     "Teachers often move classes outside when the rooms become too dark.",
     "Students lose valuable learning time during these power cuts.",
     "Diesel generators can help, but fuel is expensive and noisy.",
     "Solar panels offer a cleaner and cheaper way to keep schools running.",
     "A small rooftop system can power lights, fans, and a few computers.",
     "This report studies one such system over five months."],
    ["The school in this study has 240 students and 9 teachers.",
     "Before the project, the school had power for only 14 hours a day on average.",
     "The local R&D team designed the system with help from two engineers.",
     "The project budget was ₹1,20,000, including panels, batteries, and wiring.",
     "A similar imported kit was quoted at about $450 per panel.",
     "All readings were saved in a file called solar_data_2026.csv for later study.",
     "The results are summarised in the sections below."],
    ["The energy a solar panel produces depends on four main things.",
     "The first is the area of the panel, measured in square metres.",
     "The second is the panel's efficiency, which is the share of sunlight it turns into electricity.",
     "The third is the number of peak sun hours in a day.",
     "The fourth is the performance ratio, which accounts for losses in wires, heat, and dust.",
     "Engineers combine these four values in a simple formula.",
     "The formula below gives the energy produced in one day.",
     "Each symbol is explained right after the formula."],
    ["In this formula, E is the daily energy in kilowatt-hours.",
     "A is the total panel area, and r is the panel efficiency.",
     "H is the number of peak sun hours, and PR is the performance ratio.",
     "The school's panels cover 20 square metres with an efficiency of 18%.",
     "The region gets about 5 peak sun hours on a typical day.",
     "With a performance ratio of 0.75, the system should make about 13.5 kWh per day.",
     "This is enough to run the school's lights, fans, and computer lab."],
    ["The system was switched on in January and measured every day.",
     "A small meter recorded the energy produced each hour.",
     "Sunny days were counted using a simple light sensor.",
     "The table below shows the results for the first five months.",
     "Energy is given in kilowatt-hours, and savings are given in rupees.",
     "Savings were calculated at a rate of ₹8 per unit of electricity.",
     "January and March gave the best results because of clear skies.",
     "May was lower because of early rain and more cloudy days."],
    ["In total, the system produced 1,906 kWh in five months.",
     "This saved the school ₹15,248 on its electricity bill.",
     "The best single day produced 15.2 kWh, which is more than the formula predicted.",
     "The worst day produced only 3.1 kWh during a heavy storm.",
     "On average, the system made 12.6 kWh per day.",
     "This is about 93% of the value predicted by the formula.",
     "The small gap is mostly explained by dust on the panels."],
    ["The panels were mounted on the flat roof of the main building.",
     "They face south and are tilted at 25 degrees to catch the most sunlight.",
     "A battery bank in the store room keeps power available after sunset.",
     "The wiring runs through a safety switch and a small control box.",
     "Local workers finished the installation in four days.",
     "Two teachers were trained to read the meter and clean the panels.",
     "The photo below shows the finished system on the roof."],
    ["The panels are placed in four rows with space for cleaning between them.",
     "The roof was checked by an engineer before the work began.",
     "No leaks or cracks were found during the first five months.",
     "Birds sometimes sit on the frames, so a simple net was added.",
     "The panels are cleaned with water every two weeks.",
     "Cleaning takes less than one hour for two people."],
    ["The most important question for the school was when the system would pay for itself.",
     "This is called the payback period.",
     "It is found by dividing the total cost by the yearly savings.",
     "The yearly energy was estimated from the five-month results.",
     "The formula below shows the calculation.",
     "Here, C is the total cost, E_year is the yearly energy, and p is the price of one unit."],
    ["The system is expected to make about 4,600 kWh in a full year.",
     "At ₹8 per unit, this saves about ₹36,800 every year.",
     "With a total cost of ₹1,20,000, the payback period is about 3.3 years.",
     "After that, the electricity is almost free for the rest of the panels' 25-year life."],
    ["The solar system gave the school reliable power during school hours.",
     "Students no longer lose class time because of power cuts.",
     "The measured energy matched the formula within 7%.",
     "The money saved can now be spent on books and science kits.",
     "Other schools can use the same formula to plan their own systems.",
     "The main lessons are to choose a strong roof and to keep the panels clean.",
     "With simple care, a small solar system can serve a school for many years."],
]
SENTENCES = [s for para in P for s in para]
assert len(SENTENCES) == 75
TABLE = [["Month", "Sunny days", "Energy (kWh)", "Savings (₹)"],
         ["January", "24", "405", "3,240"], ["February", "23", "372", "2,976"],
         ["March", "26", "418", "3,344"], ["April", "22", "381", "3,048"], ["May", "18", "330", "2,640"]]
F1, F2 = r"E = A \times r \times H \times PR", r"T = \frac{C}{E_{year} \times p}"
ALT = "Rows of solar panels on the flat roof of a school building"
CAPTION = "Figure 1: Solar panels on the roof of the main school building"


def para(i, page):
    return {"type": "paragraph", "text": "\n".join(P[i]), "page": page}


def h(text, page):
    return {"type": "heading", "level": 2, "text": text, "page": page}


def truth_elements():
    return [
        {"type": "heading", "level": 1, "text": TITLE, "page": 0},
        h("1. Why Schools Need Solar Power", 0), para(0, 0), para(1, 0),
        h("2. How Much Energy a Panel Makes", 0), para(2, 0), {"type": "formula", "latex": F1, "page": 0}, para(3, 0),
        h("3. Measured Results", 1), para(4, 1), {"type": "table", "cells": TABLE, "page": 1}, para(5, 1),
        h("4. The Installation", 1), para(6, 1),
        {"type": "image", "src": IMAGE, "alt": ALT, "page": 1},
        {"type": "caption", "text": CAPTION, "ref": 14, "page": 1}, para(7, 1),
        h("5. Costs and Savings", 2), para(8, 2), {"type": "formula", "latex": F2, "page": 2}, para(9, 2),
        h("6. Conclusion", 2), para(10, 2),
    ]


def with_paths(els):
    """Add each element's section path (the headings above it)."""
    stack = []
    for e in els:
        if e["type"] == "heading":
            stack = [x for x in stack if x[0] < e["level"]] + [(e["level"], e["text"])]
            e["path"] = [t for _, t in stack[:-1]]
        else:
            e["path"] = [t for _, t in stack]
    return els


TRUTH = with_paths(truth_elements())


def md_table(cells):
    return "\n".join([fmjl._pipe_row(cells[0]), fmjl._pipe_row(["---"] * len(cells[0]))] +
                     [fmjl._pipe_row(r) for r in cells[1:]])


def write_fmjl(els, doc="solar_schools"):
    rows, img_label = [{"type": "document", "doc": doc, "source": "solar_schools.pdf", "title": TITLE,
                        "authors": [AUTHOR], "lang": "en", "access": ["all"],
                        "created": "2026-09-26T09:00:00Z"}], None
    for e in els:
        t = e["type"]
        if t == "heading":
            r = {"type": "heading", "level": e["level"], "md": "#" * e["level"] + " " + e["text"]}
        elif t == "paragraph":
            r = {"type": "paragraph", "md": e["text"]}
        elif t == "formula":
            r = {"type": "formula", "latex": e["latex"], "md": "$$" + e["latex"] + "$$"}
        elif t == "table":
            r = {"type": "table", "md": md_table(e["cells"])}
        elif t == "image":
            r = {"type": "image", "subtype": "photo", "file": e["src"], "md": e["alt"], "label": "roof-photo"}
        else:
            r = {"type": "caption", "md": e["text"], "reference": "LABEL"}
        r["page"] = e["page"]
        rows.append(r)
    for r in rows[1:]:
        r.pop("label", None)
    rows = fmjl.fill(rows)
    last_image = None
    for r in rows[1:]:
        if r["type"] == "image":
            last_image = r["id"]
        if r.get("reference") == "LABEL":
            r["reference"] = last_image
    return "\n".join(fmjl.dumps(r) for r in rows) + "\n"


def write_md(els):
    out = ["---", f"title: {TITLE}", f"author: {AUTHOR}", "---", ""]
    for e in els:
        t = e["type"]
        if t == "heading":
            out.append("#" * e["level"] + " " + e["text"])
        elif t in ("paragraph", "caption"):
            out.append(e["text"])
        elif t == "formula":
            out.append("$$" + e["latex"] + "$$")
        elif t == "table":
            out.append(md_table(e["cells"]))
        elif t == "image":
            out.append(f"![{e['alt']}]({e['src']})")
        out.append("")
    return "\n".join(out)


def write_json(els):
    doc = {"title": {"text": TITLE, "page": 0}, "author": AUTHOR, "sections": []}
    for e in els[1:]:
        t = e["type"]
        if t == "heading":
            doc["sections"].append({"heading": e["text"], "page": e["page"], "blocks": []})
            continue
        blocks = doc["sections"][-1]["blocks"]
        if t == "paragraph":
            blocks.append({"type": "paragraph", "text": e["text"], "page": e["page"]})
        elif t == "formula":
            blocks.append({"type": "formula", "latex": e["latex"], "page": e["page"]})
        elif t == "table":
            blocks.append({"type": "table", "columns": e["cells"][0], "rows": e["cells"][1:], "page": e["page"]})
        elif t == "image":
            blocks.append({"type": "figure", "src": e["src"], "alt": e["alt"], "caption": None, "page": e["page"]})
        elif t == "caption":
            blocks[-1]["caption"] = e["text"]
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


_TEX_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex_escape(s):
    return "".join(_TEX_ESC.get(c, c) for c in s)


def write_latex(els):
    out = [r"\documentclass{article}", r"\usepackage{amsmath}", r"\usepackage{graphicx}",
           r"\usepackage{fontspec}  % compile with XeLaTeX (for the rupee sign)",
           f"\\title{{{tex_escape(TITLE)}}}", f"\\author{{{tex_escape(AUTHOR)}}}",
           r"\begin{document}", r"\maketitle", ""]
    n_eq = 0
    for i, e in enumerate(els[1:], start=1):
        t = e["type"]
        if t == "heading":
            out += [f"\\section*{{{tex_escape(e['text'])}}}", ""]
        elif t == "paragraph":
            out += [tex_escape(line) for line in e["text"].split("\n")] + [""]
        elif t == "formula":
            n_eq += 1
            out += [r"\begin{equation}", e["latex"], f"\\label{{eq:{n_eq}}}", r"\end{equation}", ""]
        elif t == "table":
            c = e["cells"]
            out += [r"\begin{table}[h]", r"\centering", r"\label{tab:results}", r"\begin{tabular}{l" + "r" * (len(c[0]) - 1) + "}",
                    " & ".join(tex_escape(x) for x in c[0]) + r" \\", r"\hline"]
            out += [" & ".join(tex_escape(x) for x in r) + r" \\" for r in c[1:]]
            out += [r"\end{tabular}", r"\end{table}", ""]
        elif t == "image":
            cap = els[i + 1]["text"].split(": ", 1)[1]
            out += [r"\begin{figure}[h]", r"\centering", f"\\includegraphics[width=0.8\\textwidth]{{{e['src']}}}",
                    f"\\caption{{{tex_escape(cap)}}}", r"\label{fig:roof}", r"\end{figure}", ""]
    out.append(r"\end{document}")
    return "\n".join(out) + "\n"


def read_fmjl(text):
    rows = []
    for line in text.split("\n"):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows or rows[0].get("type") != "document":
        return [], {}
    header, els = rows[0], rows[1:]
    by_id = {e.get("id"): e for e in els}
    index = {e.get("id"): i for i, e in enumerate(els)}
    out = []
    for e in els:
        t, r = e.get("type"), {"page": e.get("page")}
        if t == "heading":
            r.update(type="heading", level=e["level"], text=e["md"].lstrip("#").strip())
        elif t == "paragraph":
            r.update(type="paragraph", text=e["md"])
        elif t == "formula":
            r.update(type="formula", latex=e["latex"])
        elif t == "table":
            r.update(type="table", cells=[fmjl._split_row(l) for i, l in enumerate(e["md"].split("\n")) if i != 1])
        elif t == "image":
            r.update(type="image", src=e["file"], alt=e["md"])
        elif t == "caption":
            r.update(type="caption", text=e["md"], ref=index.get(e.get("reference")))
        path, p = [], e.get("parent")
        while p in by_id:
            path.insert(0, by_id[p]["md"].lstrip("#").strip())
            p = by_id[p].get("parent")
        r["path"] = path
        out.append(r)
    return out, {"title": header.get("title"), "author": (header.get("authors") or [None])[0]}


_MD = MarkdownIt("commonmark").enable(["table"])


def read_md(text):
    meta = {}
    if text.startswith("---\n"):
        end = text.index("\n---", 4)
        for line in text[4:end].split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[end + 4:]
    toks, out, stack = _MD.parse(text), [], []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok.type == "heading_open":
            level, txt = int(tok.tag[1]), toks[i + 1].content
            stack = [x for x in stack if x[0] < level] + [(level, txt)]
            out.append({"type": "heading", "level": level, "text": txt, "page": None, "path": [t for _, t in stack[:-1]]})
        elif tok.type == "paragraph_open" and tok.level == 0:
            inline = toks[i + 1]
            kids = [c for c in inline.children if c.type != "softbreak"]
            m = re.fullmatch(r"\$\$(.+)\$\$", inline.content.strip(), re.S)
            if m:
                e = {"type": "formula", "latex": m.group(1).strip()}
            elif len(kids) == 1 and kids[0].type == "image":
                e = {"type": "image", "src": kids[0].attrs["src"], "alt": kids[0].content}
            else:
                e = {"type": "paragraph", "text": inline.content}
            e.update(page=None, path=[t for _, t in stack])
            out.append(e)
        elif tok.type == "table_open":
            cells, row = [], None
            j = i + 1
            while toks[j].type != "table_close":
                if toks[j].type == "tr_open":
                    row = []
                elif toks[j].type == "inline":
                    row.append(toks[j].content)
                elif toks[j].type == "tr_close":
                    cells.append(row)
                j += 1
            out.append({"type": "table", "cells": cells, "page": None, "path": [t for _, t in stack]})
        i += 1
    return out, {"title": meta.get("title"), "author": meta.get("author")}


def read_json(text):
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return [], {}
    out = [{"type": "heading", "level": 1, "text": doc["title"]["text"], "page": doc["title"]["page"], "path": []}]
    for s in doc["sections"]:
        path = [doc["title"]["text"], s["heading"]]
        out.append({"type": "heading", "level": 2, "text": s["heading"], "page": s["page"], "path": path[:1]})
        for b in s["blocks"]:
            base = {"page": b.get("page"), "path": path}
            if b["type"] == "paragraph":
                out.append({"type": "paragraph", "text": b["text"], **base})
            elif b["type"] == "formula":
                out.append({"type": "formula", "latex": b["latex"], **base})
            elif b["type"] == "table":
                out.append({"type": "table", "cells": [b["columns"]] + b["rows"], **base})
            elif b["type"] == "figure":
                out.append({"type": "image", "src": b["src"], "alt": b.get("alt"), **base})
                if b.get("caption"):
                    out.append({"type": "caption", "text": b["caption"], "ref": len(out) - 1, **base})
    return out, {"title": doc["title"]["text"], "author": doc.get("author")}


_L2T = LatexNodes2Text()


def tex_text(s):
    return _L2T.latex_to_text(s).strip()


def read_latex(text):
    meta = {}
    for k in ("title", "author"):
        m = re.search(r"\\%s\{(.*?)\}" % k, text)
        meta[k] = tex_text(m.group(1)) if m else None
    m = re.search(r"\\maketitle(.*?)(\\end\{document\}|$)", text, re.S)
    body = m.group(1) if m else ""
    pattern = re.compile(r"\\section\*?\{(.*?)\}|\\begin\{(equation|table|figure)\}(.*?)\\end\{\2\}", re.S)
    out = [{"type": "heading", "level": 1, "text": meta["title"], "page": None, "path": []}]
    section, pos, n_fig = None, 0, 0

    def add_paragraphs(chunk):
        for block in re.split(r"\n\s*\n", chunk):
            if block.strip():
                lines = [tex_text(l) for l in block.strip().split("\n")]
                out.append({"type": "paragraph", "text": "\n".join(lines), "page": None,
                            "path": [meta["title"]] + ([section] if section else [])})

    for m in pattern.finditer(body):
        add_paragraphs(body[pos:m.start()])
        pos = m.end()
        path = [meta["title"]] + ([section] if section else [])
        if m.group(1) is not None:
            section = tex_text(m.group(1))
            out.append({"type": "heading", "level": 2, "text": section, "page": None, "path": [meta["title"]]})
        elif m.group(2) == "equation":
            latex = re.sub(r"\\label\{.*?\}", "", m.group(3)).strip()
            out.append({"type": "formula", "latex": latex, "page": None, "path": path})
        elif m.group(2) == "table":
            tab = re.search(r"\\begin\{tabular\}\{.*?\}(.*?)\\end\{tabular\}", m.group(3), re.S).group(1)
            rows = [r.strip() for r in re.split(r"\\\\", tab.replace(r"\hline", "")) if r.strip()]
            cells = [[tex_text(c) for c in re.split(r"(?<!\\)&", r)] for r in rows]
            out.append({"type": "table", "cells": cells, "page": None, "path": path})
        elif m.group(2) == "figure":
            n_fig += 1
            src = re.search(r"\\includegraphics(?:\[.*?\])?\{(.*?)\}", m.group(3)).group(1)
            cap = re.search(r"\\caption\{(.*?)\}", m.group(3), re.S)
            out.append({"type": "image", "src": src, "alt": None, "page": None, "path": path})
            if cap:
                out.append({"type": "caption", "text": f"Figure {n_fig}: " + tex_text(cap.group(1)),
                            "ref": len(out) - 1, "page": None, "path": path})
    add_paragraphs(body[pos:])
    return out, meta


FORMATS = {
    "FMJL": (write_fmjl, read_fmjl, "fmjl"),
    "Markdown": (write_md, read_md, "md"),
    "JSON": (write_json, read_json, "json"),
    "LaTeX": (write_latex, read_latex, "tex"),
}


def norm(s):
    return " ".join(str(s or "").split())


def score(got, meta):
    """Compare a reader's output with the truth. Returns {category: (correct, total)}."""
    texts = " ".join(norm(e.get("text")) for e in got if e["type"] in ("paragraph", "caption"))
    by_type = lambda t: [e for e in got if e["type"] == t]
    th = [e for e in TRUTH if e["type"] == "heading"]
    gh = by_type("heading")
    tt, gt = TRUTH[10]["cells"], (by_type("table") or [{"cells": []}])[0]["cells"]
    img = (by_type("image") or [{}])[0]
    cap = (by_type("caption") or [{}])[0]
    aligned = len(got) == len(TRUTH)
    s = {
        "Sentences (text exact)": (sum(norm(x) in texts for x in SENTENCES), 75),
        "Headings (text and level)": (sum(1 for a, b in zip(th, gh) if norm(a["text"]) == norm(b["text"]) and a["level"] == b["level"]), len(th)),
        "Formulas (LaTeX exact)": (sum(1 for f in (F1, F2) if norm(f) in [norm(e.get("latex")) for e in by_type("formula")]), 2),
        "Table cells": (sum(1 for r in range(len(tt)) for c in range(len(tt[0]))
                            if r < len(gt) and c < len(gt[r]) and norm(gt[r][c]) == norm(tt[r][c])), len(tt) * len(tt[0])),
        "Image file and description": (int(img.get("src") == IMAGE) + int(norm(img.get("alt")) == norm(ALT)), 2),
        "Caption text": (int(norm(cap.get("text")) == norm(CAPTION) or norm(CAPTION) in texts), 1),
        "Title and author": (int(meta.get("title") == TITLE) + int(meta.get("author") == AUTHOR), 2),
        "Element types, in order": (sum(1 for a, b in zip(TRUTH, got) if a["type"] == b["type"]) if aligned else 0, len(TRUTH)),
        "Caption linked to image": (int(bool(cap) and cap.get("ref") is not None and got[cap["ref"]]["type"] == "image"), 1),
        "Section path of each element": (sum(1 for a, b in zip(TRUTH, got) if a["path"] == b.get("path")) if aligned else 0, len(TRUTH)),
        "Page numbers": (sum(1 for a, b in zip(TRUTH, got) if a["page"] == b.get("page")) if aligned else 0, len(TRUTH)),
    }
    return s


def recovered_elements(got):
    """How many truth elements appear, complete and correct, in a (possibly damaged) reading."""
    def key(e):
        return (e["type"], norm(e.get("text")), norm(e.get("latex")), json.dumps(e.get("cells")), e.get("src"))
    have = {key(e) for e in got}
    return sum(1 for e in TRUTH if key(e) in have)


def timed(fn, runs):
    fn()
    ts = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1000


def tokenizer():
    try:
        from anthropic._tokenizers import sync_get_tokenizer
        tok = sync_get_tokenizer()
        return lambda s: len(tok.encode(s).ids)
    except Exception:
        return None


def edit_model():
    """One word changed (sentence 40) and one new paragraph inserted at the start of section 1."""
    els = copy.deepcopy(TRUTH)
    els[11]["text"] = els[11]["text"].replace("This saved the school", "This cut the school's bill by")\
                                     .replace(" on its electricity bill.", ".")
    new = {"type": "paragraph", "text": "Power cuts are common in many rural areas.", "page": 0}
    return with_paths(els[:2] + [new] + els[2:])


def fixed_chunks(text, size=1000):
    return [text[i:i + size] for i in range(0, len(text), size)]


def importers():
    """Import the sample PDF and Word file and score what came out (rulebook 10.1)."""
    import shutil
    import tempfile
    out = {}
    samples = [("PDF (examples/solar_report.pdf)", "pdf"), ("Word (examples/maintenance_guide.docx)", "docx")]
    tmp = Path(tempfile.mkdtemp(prefix="fmjl-bench-"))
    for label, kind in samples:
        src = next(HERE.parent.glob(f"examples/*.{kind}"))
        try:
            mod = __import__("fmjl_" + kind)
        except ImportError as e:
            out[label] = {"importer available": f"no ({e})"}
            continue
        t0 = time.perf_counter()
        rows, warnings = (mod.import_pdf if kind == "pdf" else mod.import_docx)(src, out_dir=tmp)
        ms = (time.perf_counter() - t0) * 1000
        target = tmp / src.with_suffix(".fmjl").name
        fmjl.write_rows(target, rows)
        els = rows[1:]
        by_id = {e["id"]: e for e in els}
        captions = [e for e in els if e["type"] == "caption"]
        out[label] = {
            "import time (ms)": round(ms, 1),
            "elements": len(els),
            "headings": sum(1 for e in els if e["type"] == "heading"),
            "tables": sum(1 for e in els if e["type"] == "table"),
            "tables with merged cells (html)": sum(1 for e in els if e["type"] == "table" and "html" in e),
            "images": sum(1 for e in els if e["type"] == "image"),
            "captions linked to their image or table": f"{sum(1 for c in captions if by_id.get(c.get('reference'), {}).get('type') in ('image', 'table'))}/{len(captions)}",
            "formulas as LaTeX": sum(1 for e in els if e["type"] == "formula"),
            "elements with a page": f"{sum(1 for e in els if 'page' in e or 'pages' in e)}/{len(els)}",
            "elements with a bbox": f"{sum(1 for e in els if 'bbox' in e)}/{len(els)}",
            "noise (headers, footers, page numbers)": sum(1 for e in els if e["type"] == "noise"),
            "passes fmjl check": not fmjl.check(target),
            "warnings": len(warnings),
        }
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    out_dir = HERE
    results = {"accuracy": {}, "speed": {}, "efficiency": {}, "stability": {}, "importers": {}}
    count = tokenizer()
    big_model = with_paths([copy.deepcopy(e) for _ in range(100) for e in TRUTH])
    content_chars = sum(len(s) for s in SENTENCES) + sum(len(e.get("text", "")) for e in TRUTH if e["type"] in ("heading", "caption")) \
        + len(F1) + len(F2) + sum(len(c) for r in TABLE for c in r) + len(ALT) + len(IMAGE) + len(AUTHOR)

    files = {}
    for name, (write, read, ext) in FORMATS.items():
        text = write(TRUTH)
        files[name] = text
        (out_dir / f"solar_schools.{ext}").write_text(text, encoding="utf-8")
        got, meta = read(text)
        results["accuracy"][name] = score(got, meta)

        big = write(big_model)
        results["speed"][name] = {
            "read 1 doc (ms)": timed(lambda: read(text), 50),
            "read 100 docs (ms)": timed(lambda: read(big), 5),
            "write 100 docs (ms)": timed(lambda: write(big_model), 5),
        }
        table_chunk = {"FMJL": lambda: json.loads(text.split("\n")[11])["md"],
                       "Markdown": lambda: md_table(TABLE),
                       "JSON": lambda: json.dumps(json.loads(text)["sections"][2]["blocks"][1], ensure_ascii=False, indent=2),
                       "LaTeX": lambda: re.search(r"\\begin\{table\}.*?\\end\{table\}", text, re.S).group(0)}[name]()
        results["efficiency"][name] = {
            "file size (bytes)": len(text.encode("utf-8")),
            "gzip size (bytes)": len(gzip.compress(text.encode("utf-8"), 9)),
            "tokens (whole file)": count(text) if count else None,
            "syntax overhead": round(1 - content_chars / len(text), 3),
            "tokens to send the table to an LLM": count(table_chunk) if count else None,
        }

    big_texts = {n: FORMATS[n][0](big_model) for n in FORMATS}

    def first_table_fmjl():
        for line in io.StringIO(big_texts["FMJL"]):
            if '"type":"table"' in line:
                return json.loads(line)

    finders = {"FMJL": first_table_fmjl,
               "Markdown": lambda: next(e for e in read_md(big_texts["Markdown"])[0] if e["type"] == "table"),
               "JSON": lambda: json.loads(big_texts["JSON"])["sections"][2]["blocks"][1],
               "LaTeX": lambda: re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", big_texts["LaTeX"], re.S).group(0)}
    for n, f in finders.items():
        results["speed"][n]["find first table in 100 docs (ms)"] = timed(f, 20)

    edited = edit_model()
    global TRUTH_UID, EDITED_UID
    TRUTH_UID = [dict(e, uid=i) for i, e in enumerate(TRUTH)]
    EDITED_UID = [dict(e, uid=i) for i, e in enumerate(TRUTH)]
    EDITED_UID = EDITED_UID[:2] + [{"type": "paragraph", "uid": None}] + EDITED_UID[2:]
    for name, (write, read, ext) in FORMATS.items():
        old, new = files[name], write(edited)
        if name == "FMJL":
            md = fmjl.export_md([json.loads(l) for l in old.strip().split("\n")])
            md = md.replace("This saved the school ₹15,248 on its electricity bill.", "This cut the school's bill by ₹15,248.")
            md = md.replace("<!-- e3 page=0 -->", "<!-- page=0 -->\nPower cuts are common in many rural areas.\n\n<!-- e3 page=0 -->")
            new_rows = fmjl.import_md(md, doc="solar_schools")
            new = "\n".join(fmjl.dumps(r) for r in new_rows) + "\n"
            old_rows = [json.loads(l) for l in old.strip().split("\n")][1:]
            old_ids = {r["id"]: r["hash"] for r in old_rows}
            new_ids = {r["id"]: r["hash"] for r in new_rows[1:]}
            kept = sum(1 for i in old_ids if i in new_ids)
            reembed = f"{sum(1 for i, hsh in new_ids.items() if old_ids.get(i) != hsh)} of {len(new_ids)} elements"
        elif name == "JSON":
            def positions(els):
                pos, sec, blk = {}, -1, -1
                for e in els:
                    if e["type"] == "heading" and e["level"] == 1:
                        pos["title"] = e.get("uid")
                    elif e["type"] == "heading":
                        sec, blk = sec + 1, -1
                        pos[("section", sec)] = e.get("uid")
                    elif e["type"] == "caption":
                        pos[("caption", sec, blk)] = e.get("uid")
                    else:
                        blk += 1
                        pos[("block", sec, blk)] = e.get("uid")
                return pos
            a, b = positions(TRUTH_UID), positions(EDITED_UID)
            kept = sum(1 for k, uid in a.items() if b.get(k) == uid)
            def blocks(t):
                d = json.loads(t)
                return [json.dumps(x, sort_keys=True) for sec in d["sections"] for x in sec["blocks"]]
            reembed = f"{len(set(blocks(new)) - set(blocks(old)))} of {len(blocks(new))} blocks (hashed by hand)"
        else:
            labelled = {"eq:1": 1, "eq:2": 1, "tab:results": 1, "fig:roof": 2}
            kept = sum(labelled.get(l, 0) for l in set(re.findall(r"\\label\{(.*?)\}", old)) & set(re.findall(r"\\label\{(.*?)\}", new)))
            reembed = f"{len(set(fixed_chunks(new)) - set(fixed_chunks(old)))} of {len(fixed_chunks(new))} chunks"
        diff = sum(1 for l in difflib.unified_diff(old.split("\n"), new.split("\n"), lineterm="")
                   if l[:1] in "+-" and l[:3] not in ("+++", "---"))

        cut = old[: int(len(old) * 0.9)]
        got_cut, _ = read(cut) if name != "LaTeX" else read(cut + "\n\\end{document}")
        broken = old.replace("which accounts for losses", "which accounts for lossez", 1)
        if name == "FMJL":
            p = out_dir / "_corrupt.fmjl"
            p.write_text(broken, encoding="utf-8")
            detected = any("hash is wrong" in e for e in fmjl.check(p))
            p.unlink()
        else:
            detected = False
        results["stability"][name] = {
            "same output when written twice": write(TRUTH) == old,
            "diff lines after the edit": diff,
            "elements keeping their ID after the edit": f"{kept}/{len(TRUTH)}",
            "chunks to re-embed after the edit": reembed,
            "elements recovered from a 90% cut file": f"{recovered_elements(got_cut)}/{len(TRUTH)}",
            "detects a silently changed letter": detected,
        }

    results["importers"] = importers()
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


if __name__ == "__main__":
    r = main()
    for section, data in r.items():
        print(f"\n=== {section.upper()} ===")
        names = list(data)
        rows = list(next(iter(data.values())))
        width = 14 if section != "importers" else 40
        print(f"{'':44s}" + "".join(f"{n:>{width}s}" for n in names))
        for row in rows:
            vals = []
            for n in names:
                v = data[n].get(row, "")
                if isinstance(v, tuple):
                    v = f"{v[0]}/{v[1]}"
                elif isinstance(v, float):
                    v = f"{v:.2f}"
                vals.append(f"{str(v):>{width}s}")
            print(f"{row:44s}" + "".join(vals))
