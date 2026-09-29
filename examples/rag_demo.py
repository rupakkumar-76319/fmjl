#!/usr/bin/env python3
"""rag_demo.py - a complete retrieval example on FMJL documents, in plain Python.

  python examples/rag_demo.py "How much did electricity bills fall?"
  python examples/rag_demo.py "Who checks the inverter?" --folder my_docs

Steps:
  1. Load every .fmjl file in the folder (fmjl.load).
  2. Turn each document into chunks (fmjl.chunks): the text of one element with the
     headings above it, plus its id, page, bbox, hash and permissions.
  3. Score the chunks against the question. This file uses TF-IDF with cosine
     similarity so it runs with nothing installed; swap in any embedding model here.
  4. Print the best chunks with their citation: document, page number, element id.
  5. If the anthropic package is installed and a key is configured, ask Claude to
     answer from those chunks only and cite the ids.

Copyright (c) 2026 Rupak Kumar. MIT License, see LICENSE.
"""
import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fmjl

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = set("a an and are as at be by did do does for from how in is it of on or the this to was were what when where which who why with".split())


def tokens(text):
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


class TfidfIndex:
    def __init__(self, chunk_list):
        self.chunks = chunk_list
        self.docs = [Counter(tokens(c["text"])) for c in chunk_list]
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs) or 1
        self.idf = {t: math.log((n + 1) / (k + 1)) + 1 for t, k in df.items()}
        self.vectors = [self._vector(d) for d in self.docs]

    def _vector(self, counts):
        v = {t: (1 + math.log(k)) * self.idf.get(t, 1.0) for t, k in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, question, top=3, allowed=("all",)):
        q = self._vector(Counter(tokens(question)))
        scored = []
        for c, v in zip(self.chunks, self.vectors):
            if not set(c["access"]) & set(allowed):
                continue
            score = sum(w * v.get(t, 0.0) for t, w in q.items())
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda s: -s[0])
        return scored[:top]


def citation(c):
    where = f"page {c['page'] + 1}" if "page" in c else "no page"
    return f"{c['doc']}, {where}, {c['id'].split('#')[1]}"


def load_folder(folder):
    out = []
    for path in sorted(Path(folder).glob("*.fmjl")):
        errors = fmjl.check(path)
        if errors:
            print(f"skipping {path.name}: {errors[0]}")
            continue
        out.extend(c for c in fmjl.chunks(fmjl.load(path)) if c["type"] != "heading")
    return out


def ask_claude(question, hits):
    try:
        import anthropic
    except ImportError:
        return None
    context = "\n\n".join(f"[{c['id']}] ({citation(c)})\n{c['text']}" for _, c in hits)
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=16000,
            system=("Answer the question using only the passages given. After each fact, cite the "
                    "passage id in square brackets, like [solar_report#e5]. If the passages do not "
                    "contain the answer, say so."),
            messages=[{"role": "user", "content": f"Passages:\n\n{context}\n\nQuestion: {question}"}],
        )
    except anthropic.AuthenticationError:
        print("(anthropic is installed but no key is configured; set ANTHROPIC_API_KEY to get an answer)")
        return None
    if response.stop_reason == "refusal":
        return "(Claude declined to answer this question)"
    return "".join(b.text for b in response.content if b.type == "text")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--folder", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--access", default="all", help="comma-separated groups the reader belongs to")
    a = ap.parse_args()
    chunk_list = load_folder(a.folder)
    print(f"{len(chunk_list)} chunks from {a.folder}\n")
    index = TfidfIndex(chunk_list)
    hits = index.search(a.question, top=a.top, allowed=a.access.split(","))
    if not hits:
        print("nothing matched")
        return 1
    for score, c in hits:
        print(f"[{score:.2f}] {citation(c)}")
        print("   " + c["text"].replace("\n", "\n   ")[:400])
        print()
    answer = ask_claude(a.question, hits)
    if answer:
        print("Answer:\n" + answer)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
