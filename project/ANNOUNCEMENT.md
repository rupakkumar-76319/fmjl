# FMJL 1.0: a document format built for RAG, free for everyone

I built FMJL because every format I tried for retrieval lost something. Markdown cannot say which page a paragraph came from or which image a caption belongs to. JSON can, but nobody wants to write a report as JSON. LaTeX writes formulas perfectly and nothing else easily. HTML has merged-cell tables and is heavy everywhere else.

FMJL, short for Format, Markdown, JSON Lines, combines the four instead of replacing them. A document becomes one JSON object per line: one element (heading, paragraph, list, table, formula, image, caption, footnote, stamp, watermark...) with a stable id, a content hash, its page and position on the page, and who may read it. The readable text is Markdown, formulas are LaTeX, merged-cell tables are HTML. People never touch those lines: they write and edit the same document as ordinary Markdown, and the tool converts both ways without renumbering anything, so a vector store only re-embeds what changed.

What you get today, all MIT licensed:

- `pip install fmjl`: convert Markdown to `.fmjl` and back, check every rule, import PDF and Word files (headings, lists, merged cells, images with captions, footnotes, Word formulas as LaTeX), and print retriever-ready chunks with page citations.
- A VS Code extension (search "FMJL") that converts and checks without Python.
- `fmjl.exe` for Windows, for people without Python.
- A rulebook that is itself an FMJL document, with the JSON Schema, the canonical Markdown rules and the definition of a chunk.

The same 75-sentence report with two formulas, a table, an image and a caption, written in four formats and read back:

|  | FMJL | Markdown | JSON | LaTeX |
| --- | --- | --- | --- | --- |
| Page number of every element | 23/23 | 0/23 | 23/23 | 0/23 |
| Caption linked to its image | yes | no | yes | yes |
| Elements keeping their id after an edit | 23/23 | 0/23 | 21/23 | 5/23 |
| Detects a silently changed letter | yes | no | no | no |
| Read one document | 0.11 ms | 3.85 ms | 0.07 ms | 29.32 ms |

Ten lines of Python is the whole RAG side:

```python
import fmjl

rows = fmjl.load("report.fmjl")
for chunk in fmjl.chunks(rows, by="section"):
    store.add(embed(chunk["text"]), metadata={"id": chunk["id"], "page": chunk.get("page"), "access": chunk["access"]})
```

Website and rulebook: https://rupakkumar-76319.github.io/fmjl/
Source, examples and benchmark: https://github.com/rupakkumar-76319/fmjl
Package: https://pypi.org/project/fmjl/

It is version 1.0 and it is mine alone so far, so real documents from other people are the thing I want most. Bug reports and ideas go to the issue tracker.
