---
fmjl: "1.1"
doc: readme
lang: en
access: ["all"]
source: README.md
protection: none
signed: false
last_id: 25
---

<!-- e1 -->
# FMJL

FMJL turns any document into a list of small parts that a search engine or a RAG system can
use directly: every heading, paragraph, table, formula, image and caption becomes one line
with a stable id, a content hash, its page and position on the page, and who may read it.
People never see those lines: they write and edit the same document as normal Markdown, and
the tool converts both ways without renumbering anything.

<!-- e2 -->
FMJL, short for Format, Markdown, JSON Lines, is a document format that combines four
languages, each doing the one job it is best at:

<!-- e3 -->
| Language | Job in FMJL | Why that one |
| --- | --- | --- |
| JSON Lines | The container: one element per line, with its id, hash, page, position and permissions | Every programming language reads JSON; one line per element means a file can be streamed, searched and cut without a parser |
| Markdown | All readable text: headings, paragraphs, lists, simple tables, image descriptions | People can read and write it directly; it is the language of GitHub, VS Code and every editor |
| LaTeX | Math formulas | The only language that writes every formula exactly |
| HTML | Tables with merged cells or multi-level headers | Markdown tables cannot merge cells; HTML can |

## Install in one line

```powershell
pip install fmjl            # converter, checker, Word importer, retriever chunks
pip install "fmjl[pdf]"     # the same plus the PDF importer
```

No Python? Download `fmjl.exe` from the Releases page and put it on your PATH. In VS Code,
install the **FMJL** extension (publisher rupakkumar): it converts and checks without Python.

## Convert in one line

```powershell
fmjl notes.md               # Markdown  -> notes.fmjl, then checks every rule
fmjl notes.fmjl             # .fmjl     -> notes.md; edit it and run the first line again
fmjl report.pdf             # PDF       -> report.fmjl and images/ (--md adds report.md)
fmjl report.docx            # Word      -> the same
fmjl export notes.fmjl --to docx   # .fmjl -> Word; also md, html, pdf, odt, epub
fmjl notes.md out\notes.fmjl    # a second name is the output file
```

The file extension tells the tool which way to go. Elements you did not change keep their
ids and hashes, so a vector store only re-embeds what changed.

## Use in RAG in ten lines

```python
import fmjl

rows = fmjl.load("report.fmjl")                     # header first, then one dict per element
for chunk in fmjl.chunks(rows, by="section"):       # or by="element", the default
    store.add(embed(chunk["text"]), metadata={
        "id": chunk["id"], "page": chunk.get("page"), "bbox": chunk.get("bbox"),
        "access": chunk["access"], "hash": chunk["hash"]})

new = fmjl.chunks(fmjl.load("report_v2.fmjl"), by="section")
for chunk in fmjl.changed_chunks(new, fmjl.chunks(rows, by="section")):
    store.replace(chunk["id"], embed(chunk["text"]))    # only what changed
```

Each chunk's `text` is the heading path above it, a blank line, then the content, with
captions and footnotes attached to what they describe. Filter by `access` before searching,
and cite answers with the element id and `page` plus 1. The same is available from the
command line as `fmjl chunks report.fmjl [--by section] [--since old.fmjl]`.
`examples/rag_demo.py` is the whole pipeline in one file with nothing to install: it
scores the chunks of every `.fmjl` in a folder against a question, prints the best ones
with their citation, and asks Claude when the `anthropic` package and a key are present.

## What a file looks like

Two lines of the storage form, `notes.fmjl`:

```json
{"type":"document","version":"1.0","doc":"notes","source":"notes.md","sha256":"...","protection":"none","signed":false,"converter":"fmjl 1.0","structure":true,"elements":2,"created":"2026-09-29T10:00:00Z","lang":"en","access":["all"],"last_id":2}
{"id":"notes#e2","hash":"b91ad9f6b39e617a","type":"paragraph","parent":"notes#e1","page":0,"bbox":[80,110,920,170],"characters":105,"md":"This policy applies to all full-time employees from their first day of work."}
```

The same document in the authoring form, `notes.md`, is plain Markdown with a small hidden
note before each block that carries the id and any fields Markdown cannot hold:

```markdown
<!-- e2 page=0 bbox=80,110,920,170 -->
This policy applies to all full-time employees from their first day of work.
```

<!-- e6 -->
One document has two forms that hold the same information:

<!-- e7 -->
| Form | File | Made for |
| --- | --- | --- |
| Storage | `name.fmjl` | Machines: search, RAG, databases |
| Authoring | `name.md` | People: reading, writing, reviewing |

Merged cells never need HTML by hand. In a Markdown table a cell holding only `^` joins
the cell above it and a cell holding only `<` joins the cell to its left; the tool writes
the HTML with `rowspan` and `colspan` for you, and shows the same shortcut when you
convert back:

```markdown
| Name | Score | < |
| --- | --- | --- |
| ^ | Math | AI |
| Rupak Kumar | 9 | 10 |
```

A caption points at the block next to it with `<!-- type=caption reference=above -->`.
The rulebook in `rulebook/` lists all 20 element types, every field, and every rule the
checker enforces.

## From a PDF or a Word file

The PDF importer reads the text layer and turns it into elements: headings by font size,
paragraphs, lists, tables with merged cells, charts and pictures with their captions
linked by `reference`, and repeated headers, footers and page numbers marked as `noise`.
Every element carries `page` (counted from 0) and `bbox` (0 to 1000), so an answer can
point at the exact place on the page. Open the `.md` afterwards, fix what the importer
got wrong, and run `fmjl report.md`; the ids stay. Scanned pages need Tesseract for OCR.

The Word importer reads the document's own structure: Heading styles, bullet and numbered
lists, tables with merged cells, images with captions, footnotes, Word formulas as LaTeX,
the header and footer as `noise`, and page numbers from the page breaks Word recorded.
Tracked changes are accepted with a warning. `examples/` holds a sample of each with its
imported `.fmjl` and `.md`.

## All commands

| Command | What it does |
| --- | --- |
| `fmjl new notes.md` | Authoring form to storage form |
| `fmjl md notes.fmjl` | Storage form to authoring form |
| `fmjl fill notes.fmjl` | Fills in `id`, `hash`, `characters` and `parent`; makes `md` canonical |
| `fmjl check notes.fmjl` | Checks every rule of the rulebook |
| `fmjl view notes.fmjl` | Prints the document as clean Markdown |
| `fmjl info notes.fmjl` | Prints the title, element counts and an outline |
| `fmjl upgrade old.fmjl` | Turns a version 0.1 to 1.0 file into 1.1 |
| `fmjl pdf report.pdf` | PDF to storage form and `images/`; `--md` also writes the authoring form |
| `fmjl docx report.docx` | Word to storage form and `images/`; `--md` also writes the authoring form |
| `fmjl chunks report.fmjl` | Retriever-ready chunks as JSON Lines; `--front` keeps a book's front matter |
| `fmjl export report.fmjl --to docx` | Storage form to clean Markdown, HTML, PDF, Word, OpenDocument or EPUB (PDF needs PyMuPDF; Word, OpenDocument and EPUB need pandoc) |
| `fmjl --version` | Prints the package and rulebook version |

Without the package installed, `python -m fmjl <command>` from this folder does the same;
`fmjl.cmd` here is the one-word shortcut for Windows.

## What the benchmark shows

The same 75-sentence report with two formulas, a table, an image and a caption was written
in FMJL, Markdown, JSON and LaTeX, then read back and scored (`benchmark/results.json`):

<!-- e18 -->
|  | FMJL | Markdown | JSON | LaTeX |
| --- | --- | --- | --- | --- |
| Page number of every element | 23/23 | 0/23 | 23/23 | 0/23 |
| Caption linked to its image | yes | no | yes | yes |
| Elements keeping their id after an edit | 23/23 | 0/23 | 21/23 | 5/23 |
| Detects a silently changed letter | yes | no | no | no |
| Read one document | 0.11 ms | 3.85 ms | 0.07 ms | 29.32 ms |

The same run imports the two sample files (rulebook section 10.1):

| | PDF, 3 pages | Word, 2 pages |
| --- | --- | --- |
| Elements found | 25 | 20 |
| Captions linked to their image or table | 2/2 | 3/3 |
| Tables with merged cells kept as HTML | 0 of 1 (none merged) | 1 of 2 |
| Elements with a page | 25/25 | 20/20 |
| Elements with a position on the page | 25/25 | 0/20 (Word has none) |
| Passes `fmjl check` | yes | yes |

## VS Code

Search for **FMJL** in the Extensions view and install it (publisher rupakkumar). It needs
no Python. Right-click a `.md` file for **FMJL: Convert Markdown to .fmjl**, or a `.fmjl`
file for **FMJL: Convert .fmjl to Markdown**. Any `.fmjl` file gets coloring, red
underlines for rule violations, and the command **FMJL: Check current file**. The
extension's converter is a JavaScript port of the Python package; `npm test` in `fmjl-vscode/`
proves the two give byte-identical output on every document in this repository.

## Folder layout

```text
fmjl/            the Python package: the converter and checker, the PDF and Word importers, chunks
pyproject.toml   the PyPI package: pip install fmjl
rulebook/        the specification, version 1.1, in both forms
docs/            the website, https://rupakkumar-76319.github.io/fmjl/ : introduction and rulebook
examples/        sample documents (Markdown, PDF, Word) with their images/, rag_demo.py, and the sample generators
fmjl-vscode/     the VS Code extension: convert, syntax coloring and live checking
benchmark/       the same document in FMJL, Markdown, JSON and LaTeX, the scores, and quality.py
tests/           the test suite: python -m unittest discover -s tests
project/         the checklist of stages and the notes for the next rulebook
archive/         older versions of the rulebook and the extension
```

## Status

Version 1.1. The rulebook is the authority; if the tool and the rulebook disagree, the
tool has a bug. From 1.0 on, every 1.x reader reads every 1.x file: later minor versions
only add optional fields, types or subtypes. The website is
https://rupakkumar-76319.github.io/fmjl/

## What 1.1 fixed

After 1.0, a 345-page scanned novel (Jane Austen's *Persuasion*, a Google Books scan) was
converted and its weak points were listed. Version 1.1 fixes them in the PDF importer and the
chunker (rulebook 10.1, rules 11 to 19, and 12.1). The same book, converted by 1.0 and by 1.1:

| | 1.0 | 1.1 |
| --- | --- | --- |
| Chapter headings | 5, all junk ("RESPONDET", "BookFund") | 24, CHAPTER I to XXIV |
| Elements under one parent | 2,734 of 2,772 | 138 of 1,609 |
| Paragraphs cut mid-sentence on a page | 1,198 | 45 |
| Median paragraph length | 144 characters | 286 characters |
| Running headers read as text | 104 | 0 in the story |
| Paragraphs over a page break linked | 157 | 234 of 241 |
| Front matter (library stamps, Google notice) | mixed into the text | marked; `fmjl chunks` skips it |
| First words of Chapter I | "IR WALTER ELLIOT" | "SIR WALTER ELLIOT" |

Five more books were checked with `python benchmark/quality.py`, which compares any PDF with
its conversion; it found and fixed margin quotes read across the text, lost hyphens, missed
chapter headers and drop caps. Run it on a new kind of PDF before trusting the conversion.

## Does it find answers better?

Measured with questions whose answer sentence is known, comparing FMJL chunks
(`fmjl chunks --by section`) with the same text cut into equal pieces. A hit means the answer
was in one of the top 5 chunks returned.

| Documents | Search | Plain text, 1,000 characters | Plain text, 1,500 characters | FMJL by section |
| --- | --- | --- | --- | --- |
| Structured: this rulebook, two non-fiction books (42 questions) | Keyword (BM25) | 83% | 88% | **95%** |
| Structured, same 42 questions | Embeddings (all-mpnet-base-v2) | 69% | 55% | **79%** |
| A novel, running prose (18 questions) | Embeddings | 50% | 67% | 67% |

On documents with tables, headings and lists, FMJL is clearly ahead: whole tables, list items
and sections stay together, and no answer is cut in two (equal pieces of 1,000 characters cut 4
of the 42). On running prose it is level with plain text; there its gain is what comes with each
chunk: the page to cite, the chapter path, stable ids, and re-embedding only what changed. The
questions are few and were written by the project, so take these as a signal; the details are in
`project/NOTES.md`.

## Author and license

Created by Rupak Kumar. Released under the MIT License (see `LICENSE`): use it freely,
keep the copyright line. Suggestions and bug reports go to
https://github.com/rupakkumar-76319/fmjl/issues.
