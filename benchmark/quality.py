"""Quality check for the PDF importer: converts PDFs and compares each result with its PDF,
so problems are found before anyone relies on a conversion.

  python benchmark/quality.py                              every PDF in examples/
  python benchmark/quality.py report.pdf book.pdf ...      convert and report
  python benchmark/quality.py --strict examples/*.pdf      exit 1 when a hard limit is broken

Nothing is written next to the PDFs; conversions go to a temporary folder. The checks know
nothing about a particular document:

  words lost          words of the PDF's text layer that are missing from the output
  word order          pages whose words come out in a different order than in the PDF
  glued words         a rare word that is two common words of the same document joined
  split mid-sentence  two paragraphs on one page where the first stops mid-sentence and
                      the second starts in lower case
  page-break cuts     the same across a page break, without continues
  fragments           paragraphs of one or two words
  repeated lines      short paragraphs repeated on three or more pages: missed headers
  headings            headings that are too short or too long, or end like a sentence
  flat structure      one parent holding more than half of the elements
"""
import argparse
import collections
import difflib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf

import fmjl
from fmjl import pdf as fmjl_pdf

SENTENCE_END = tuple('.!?:;"”’)]—…')
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.U)
STRICT = {"words lost": 0.01, "word order": 0.02, "split mid-sentence": 0.03, "page-break cuts": 0.05,
          "repeated lines": 0.02}


def _words(text):
    return [w.lower() for w in WORD.findall(text.replace("-", ""))]


def check(pdf_path, rows, show=4):
    """Returns {check name: (count, out of, examples)} for one PDF and its converted rows."""
    els = rows[1:]
    doc = pymupdf.open(pdf_path)
    found = collections.OrderedDict()

    def add(name, count, total, examples):
        found[name] = (count, total, examples[:show])

    page_words, pdf_words = {}, collections.Counter()
    for i, page in enumerate(doc):
        ws = _words(re.sub(r"-\s*\n\s*", "", page.get_text()))
        page_words[i] = ws
        pdf_words.update(ws)
    out_words = collections.Counter(w for e in els for w in _words(e.get("md", "")))
    lost = pdf_words - out_words
    for w in list(lost):
        if any(out_words[w[:k]] and out_words[w[k:]] for k in range(1, len(w))):
            del lost[w]
    add("words lost", sum(lost.values()), sum(pdf_words.values()) or 1,
        [f"{w} x{c}" for w, c in lost.most_common(show)])

    glued = []
    for w, c in out_words.items():
        if c > 2 or len(w) < 5:
            continue
        for k in range(2, len(w) - 1):
            if out_words[w[:k]] >= 20 and out_words[w[k:]] >= 20:
                glued.append(f"{w} = {w[:k]} {w[k:]}")
                break
    add("glued words", len(glued), len(out_words) or 1, glued)

    by_page = collections.defaultdict(list)
    for e in els:
        if isinstance(e.get("page"), int):
            by_page[e["page"]].append(e)
    order = []
    for p, es in by_page.items():
        ws = [w for e in es for w in _words(e.get("md", ""))]
        ref = page_words.get(p, [])
        if len(ref) >= 50 and ws:
            r = difflib.SequenceMatcher(None, ref, ws, autojunk=False).ratio()
            if r < 0.85:
                order.append((round(r, 2), p + 1))
    order.sort()
    add("word order", len(order), len(by_page) or 1, [f"page {p}: {r}" for r, p in order])

    body = [e for e in els if e.get("type") not in ("noise", "image", "caption")]
    pairs = list(zip(body, body[1:]))
    split = [(a, b) for a, b in pairs if a["type"] == b["type"] == "paragraph" and a.get("page") == b.get("page")
             and not a["md"].rstrip().endswith(SENTENCE_END) and b["md"][:1].islower()]
    add("split mid-sentence", len(split), len(body) or 1,
        [f"page {a['page'] + 1}: ...{a['md'][-30:]!r} | {b['md'][:30]!r}" for a, b in split])
    cut = [(a, b) for a, b in pairs if a["type"] == b["type"] == "paragraph" and isinstance(a.get("page"), int)
           and b.get("page") == a["page"] + 1 and not a["md"].rstrip().endswith(SENTENCE_END)
           and b["md"][:1].islower() and "continues" not in b]
    add("page-break cuts", len(cut), len(body) or 1,
        [f"page {a['page'] + 1}: ...{a['md'][-30:]!r} | {b['md'][:30]!r}" for a, b in cut])
    frag = [e for e in body if e["type"] == "paragraph" and len(e["md"].split()) <= 2]
    add("fragments", len(frag), len(body) or 1, [f"page {e.get('page', -1) + 1}: {e['md'][:30]!r}" for e in frag])

    pages_of = collections.defaultdict(set)
    for e in body:
        key = re.sub(r"[^a-z]+", "", e["md"].lower())
        if e["type"] == "paragraph" and len(e["md"]) < 80 and key:
            pages_of[key].add(e.get("page"))
    repeated = sorted(((len(p), k) for k, p in pages_of.items() if len(p) >= 3), reverse=True)
    add("repeated lines", len(repeated), len(body) or 1, [f"{k!r} on {n} pages" for n, k in repeated])

    heads = [e for e in els if e.get("type") == "heading"]
    odd = [e for e in heads if len(re.sub(r"^#+\s*", "", e["md"])) < 3 or len(e["md"]) > 120
           or re.search(r"[a-z][.,;]$", e["md"])]
    add("headings", len(odd), len(heads) or 1, [f"page {e.get('page', -1) + 1}: {e['md'][:50]!r}" for e in odd])
    parents = collections.Counter(e.get("parent") for e in els)
    holder, held = parents.most_common(1)[0] if parents else (None, 0)
    flat = int(held > 0.5 * len(els) and len(doc) > 20)
    add("flat structure", flat, 1, [f"{holder} holds {held} of {len(els)}; {len(heads)} headings"] if flat else [])
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="*", help="PDF files to check (default: every PDF in examples/)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a check is above its limit")
    ap.add_argument("--show", type=int, default=4, help="examples to print per problem")
    a = ap.parse_args(argv)
    if not a.pdf:
        a.pdf = sorted(str(p) for p in (Path(__file__).resolve().parent.parent / "examples").glob("*.pdf"))
        print("checking every PDF in examples/: " + ", ".join(Path(p).name for p in a.pdf))
    broken = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in a.pdf:
            rows, warnings = fmjl_pdf.import_pdf(path, out_dir=tmp)
            errors = fmjl.check_rows(list(enumerate(rows, 1)), base=tmp)
            found = check(path, rows, a.show)
            print(f"\n{path}: {rows[0]['meta']['pages']} pages, {len(rows) - 1} elements, "
                  f"{len(errors)} rule errors, {len(warnings)} warnings")
            for name, (count, total, examples) in found.items():
                if not count:
                    continue
                share = count / total
                limit = STRICT.get(name)
                over = limit is not None and share > limit
                if over:
                    broken.append(f"{path}: {name} {share:.1%} > {limit:.0%}")
                print(f"  {count:6} {share:7.1%}  {name}{'   OVER LIMIT' if over else ''}")
                for x in examples:
                    print("                   ", x)
            if errors:
                broken.append(f"{path}: {len(errors)} rule errors")
    if a.strict and broken:
        print("\nFAILED:\n  " + "\n  ".join(broken))
        return 1
    print("\nPASSED" if not broken else "\nlimits broken (see above); --strict makes this fail")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
