# FMJL

FMJL, short for Format, Markdown, JSON Lines, is a document format that combines four
languages, each doing the one job it is best at:

| Language | Job in FMJL | Why that one |
| --- | --- | --- |
| JSON Lines | The container: one element per line, with its id, hash, page, position and permissions | Every programming language reads JSON; one line per element means a file can be streamed, searched and cut without a parser |
| Markdown | All readable text: headings, paragraphs, lists, simple tables, image descriptions | People can read and write it directly; it is the language of GitHub, VS Code and every editor |
| LaTeX | Math formulas | The only language that writes every formula exactly |
| HTML | Tables with merged cells or multi-level headers | Markdown tables cannot merge cells; HTML can |

No single format does this on its own. Markdown cannot carry an image's page and position,
cannot tie a caption to its image, and cannot say who may read a paragraph. JSON can hold
those facts but nobody wants to write or read a document as JSON. LaTeX writes formulas
perfectly but is slow to parse and hard for most people to write. HTML has the tables but
is heavy everywhere else. FMJL takes the strength of each and leaves the rest out.

A document becomes a list of small parts called elements: headings, paragraphs, lists,
tables, formulas, code, images, captions, footnotes, form fields, stamps, watermarks and
more. Every element has a stable id, a content hash, a page and position, and a permission
list. That is what RAG systems and search engines need, and it is why FMJL reads a document
in about a tenth of a millisecond (see `benchmark/`).

One document has two forms that hold the same information:

| Form | File | Made for |
| --- | --- | --- |
| Storage | `name.fmjl` | Machines: search, RAG, databases |
| Authoring | `name.md` | People: reading, writing, reviewing |

## Folder layout

```text
fmjl.py          the reference tool (needs Python 3.9+ and: pip install jsonschema)
rulebook/        the specification, version 0.4, in both forms
examples/        a sample document with its images/ folder
fmjl-vscode/     the VS Code extension: syntax coloring and live checking for .fmjl
benchmark/       the same document in FMJL, Markdown, JSON and LaTeX, and the scores
archive/         older versions (0.1, 0.2), the evaluation, and the first converter
```

## Everyday use

Write a normal Markdown file, then turn it into the storage form:

```powershell
python fmjl.py new notes.md
python fmjl.py check notes.fmjl
python fmjl.py md notes.fmjl
```

All commands:

| Command | What it does |
| --- | --- |
| `python fmjl.py new notes.md` | Authoring form to storage form |
| `python fmjl.py md notes.fmjl` | Storage form to authoring form |
| `python fmjl.py fill notes.fmjl` | Fills in `id`, `hash`, `characters` and `parent`; makes `md` canonical |
| `python fmjl.py check notes.fmjl` | Checks every rule of the rulebook |
| `python fmjl.py view notes.fmjl` | Prints the document as clean Markdown |
| `python fmjl.py info notes.fmjl` | Prints the title, element counts and an outline |
| `python fmjl.py upgrade old.fmjl` | Turns a version 0.1, 0.2 or 0.3 file into 0.4 |

## What the benchmark shows

The same 75-sentence report with two formulas, a table, an image and a caption was written
in FMJL, Markdown, JSON and LaTeX, then read back and scored (`benchmark/results.json`):

| | FMJL | Markdown | JSON | LaTeX |
| --- | --- | --- | --- | --- |
| Page number of every element | 23/23 | 0/23 | 23/23 | 0/23 |
| Caption linked to its image | yes | no | yes | yes |
| Elements keeping their id after an edit | 23/23 | 0/23 | 21/23 | 5/23 |
| Detects a silently changed letter | yes | no | no | no |
| Read one document | 0.11 ms | 3.85 ms | 0.07 ms | 29.32 ms |

## VS Code

Install the extension from `fmjl-vscode/fmjl-0.3.1.vsix` (Extensions view, "..." menu,
Install from VSIX). Any `.fmjl` file then gets coloring, red underlines for rule
violations, and the command **FMJL: Check current file**.

## Status

Draft, version 0.4. The rulebook is the authority; if `fmjl.py` and the rulebook
disagree, the tool has a bug.

## Author and license

Created by Rupak Kumar. Released under the MIT License (see `LICENSE`): use it freely,
keep the copyright line. Suggestions and bug reports go to
https://github.com/rupakkumar-76319/fmjl/issues.
