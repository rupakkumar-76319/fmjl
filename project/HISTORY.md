---
fmjl: "1.0"
doc: history
title: The FMJL Project, From the First Draft to Version 1.0
authors: Rupak Kumar
date: 2026-09-30
summary: Everything that was done to build FMJL, stage by stage, with the decisions, the problems met and how they were solved, up to the public 1.0 release.
lang: en
access: ["all"]
---

# The FMJL Project, From the First Draft to Version 1.0

This document records how FMJL was built, in the order it happened. It is written in FMJL's own authoring form and stored next to it as `HISTORY.fmjl`, so the project's story is itself a document the tools can read.

## What FMJL is

FMJL, short for Format, Markdown, JSON Lines, is a document format built for retrieval-augmented generation. A document becomes a list of elements, one per line, each with a stable id, a content hash, its page and position, and who may read it. It combines four languages, each doing one job: JSON Lines is the container, Markdown holds all readable text, LaTeX holds formulas, and HTML holds tables with merged cells. It is not "JSON plus Markdown"; it is four languages, and that sentence was repeated in every document until it stuck.

Every document has two forms holding the same information: the storage form `name.fmjl` for machines and the authoring form `name.md` for people. A tool converts either way, and elements that did not change keep their ids and hashes.

## Before the name: Format X

The project started under the placeholder name Format X. Version 0.1 was a first draft that used the extension `.jsonl`. Version 0.2 introduced the extension `.fmjl` and the first tool, `fmjl.py`. Version 0.3 added the authoring form, canonical Markdown so that the same content always gives the same hash, ids that never change, labels, the `group` type, `continues` for split elements, `meta` for custom data, header fields for title, authors, date and summary, and the rule that the rulebook is the authority over the tool. Those three versions and their evaluation are kept in `archive/`.

## Stage 1: the rulebook

The rulebook is the specification. Version 0.4 was written on 2026-09-26 and stored in both forms in `rulebook/`. It defines the header line with twelve required fields, the element line with six required fields and the optional ones, twenty element types with their subtypes, the rules for ids, hashes, pages, positions, parents and links, canonical Markdown, the authoring form with its notes and groups, the input formats, the processing order, the retrieval practices, the reader rules, a JSON Schema, examples, the tools, the version history and the open questions.

The rulebook is itself an FMJL document. Editing it always goes through the storage form: the tool writes the Markdown with ids, the text is edited, the tool writes the storage form back, and the repository copy of the Markdown is written without the note lines. Ids are never renumbered.

## Stage 2: the reference tool

`fmjl.py` was rebuilt on 2026-09-26 with seven commands: `new` (Markdown to storage form), `md` (storage form to Markdown), `fill` (ids, hashes, character counts, parents, canonical Markdown), `check` (every rule, with line numbers), `view`, `info` and `upgrade`. The round trip was proven byte for byte: the rulebook converted to Markdown and back gives the same file.

## Stages 3 and 4: the VS Code extension

The extension gives `.fmjl` files a language definition, syntax colouring, live checking with red underlines and messages in the Problems panel, and a command that answers PASSED or FAILED. It was tested by hand: an edit to a character count produced an underline within a second, and undoing it removed the underline.

## Stages 5 to 8: folder, git, name and licence, publishing

The project folder was tidied, the benchmark was run for the first time, and the repository went to GitHub as `rupakkumar-76319/fmjl`. On 2026-09-26 the final name FMJL was chosen, checked as free on GitHub, PyPI and the Marketplace, and applied everywhere; the licence became MIT with copyright Rupak Kumar. On 2026-09-27 the extension was published on the Marketplace as `rupakkumar.fmjl`, version 0.4.0.

## Stage 9: the first real documents

Real documents were written as Markdown, converted, edited and converted back with their ids kept, including a table with merged cells written as HTML and a figure written as a group. Five findings were written down in `NOTES.md`: a table typed without its separator row silently became a paragraph; merged cells needed raw HTML; the group's first block is its title without an id of its own; writing a reference needed the id of the image; and the missing-image message did not say to copy the images folder.

A question about the command form was settled the same day: the one-word command `fmjl <input> <output>` decides the direction from the file extensions, with the second name optional.

At the end of stage 9 the extension gained a pure JavaScript converter, a port of the Python tool, with a test that proves byte-identical output on every document in the repository. Extension 0.5.0 added the two conversion commands and right-click menu entries.

## Stage 10: the PDF importer

Built on 2026-09-29 with PyMuPDF. It turns the text layer into elements: headings by font size, paragraphs, lists, tables with and without ruling lines, images saved as PNG with their captions linked by `reference`, and repeated headers, footers and page numbers marked as `noise`. Every element carries `page` and `bbox`, and a paragraph that runs over a page break is linked with `continues`. Problems met and solved: a scanned article produced hundreds of image tiles, so pages with many image blocks and a text layer skip images; tables without lines needed a detector based on aligned columns; a bullet alone on a line had to be merged with the next line; a caption missed by one pixel needed a tolerance; a bullet list was mistaken for a table; a heading with a bracket was mistaken for a list. Eight more findings went to the notes.

## Stage 11: the Word importer

Built the same day with the standard library only: the document's own structure gives headings from the styles, bullet and numbered lists from the numbering definitions, tables with merged cells as HTML with rowspan and colspan, images with captions, footnotes, the header and footer as noise, and page numbers from the page breaks Word recorded. Problems solved: numbering defined at the style level, pages counted only after the first break, Title and Heading 1 both at level 1, a caption not replacing a generic picture name, and numbered items all showing "1.". Five findings went to the notes.

## Stage 12: the retriever output

`fmjl chunks` prints retriever-ready chunks as JSON Lines, one per element or one per heading section, each with its id, the heading path, the text to embed, page, position, hash and permissions; `--since` lists only the chunks that changed since an older file. The same is available as a Python library: `fmjl.load`, `fmjl.chunks`, `fmjl.changed_chunks`, `fmjl.check`. `examples/rag_demo.py` is a complete pipeline with nothing to install: TF-IDF retrieval with citations by document, page and element id, and an optional answer from Claude. Editing one number in a document and running the demo again showed that only that element, or its section, was reported as changed.

## Stage 13: rulebook 0.5

All twenty-one findings from the notes were resolved, in the rulebook first and then in the Python tool and the JavaScript converter and validator. The changes: merged cells can be written in a Markdown table with `^` to join the cell above and `<` to join the cell to the left, and tool-written HTML has one canonical form; a table typed without its separator row gives a warning; notes accept `above` and `below` in place of an id; the group title rule is written down; footnotes have a defined Markdown form; names starting with `fmjl.` are reserved in `meta`; a new section of importer rules covers merged cells, figures, caption matching by first word, heading levels that never skip, vector charts rendered to images, formulas, pages from Word, tracked changes and scans; and a new section defines what a chunk is. The PDF importer learned merged cells, vector charts with their axis labels, level clamping and headings for scans; the Word importer learned Word math converted to LaTeX, tracked-change counting and caption matching. Three findings stayed open by design: LaTeX from PDF formulas, pages with three or more columns, and OCR untested without Tesseract. Extension 0.6.0 was built.

## Stage 14: available to everyone

A `pyproject.toml` made the tool a PyPI package, `pip install fmjl`, with the PDF importer as the extra `fmjl[pdf]`; the wheel was tested in a clean virtual environment before upload. `fmjl.exe` was built with PyInstaller for people without Python; the first attempt weighed three gigabytes because PyMuPDF's optional imports pulled in machine-learning libraries, so the build excludes them and comes out at forty-two megabytes. A test workflow on GitHub Actions checks every document, round-trips the rulebook, runs both importers, builds the package and runs the extension test on every push. Issue templates were added. The README was rewritten for a stranger: what FMJL is, install in one line, convert in one line, use in RAG in ten lines. The benchmark gained a section that imports the two sample files and scores the result. PyPI received version 0.5.0 on 2026-09-29.

## The restructuring

Before the release the repository was given its final shape. The three Python files became the package `fmjl/` with `__init__.py`, `pdf.py`, `docx.py` and `__main__.py`, so `python -m fmjl` and the installed command replace the old script call. `project/` holds the checklist and the notes, `examples/sources/` holds the scripts that generate the sample PDF and Word file, and `CLAUDE.md` at the root holds the working rules of the project for anyone who joins it. A website was written in `docs/` in the spirit of json.org: a white page introducing FMJL with three diagrams of the file grammar, and the full rulebook rendered to HTML by a small build script. The extension folder kept its name `fmjl-vscode` because another program held it open when the rename was tried.

## Stage 15: version 1.0

The rulebook became version 1.0 on 2026-09-29 with no rule changes since 0.5, a promise in the reader rules that every 1.x reader reads every 1.x file, and the 0.5 files moved to the archive. Every version number moved to 1.0: the tool, the JavaScript converter, the extension 1.0.0, the package 1.0.0, every example. The announcement was written. The owner committed, tagged `v1.0.0`, uploaded to PyPI and published the extension.

The first run of the test workflow failed on Python 3.9 twice: `Path.write_text` only accepts a newline setting from Python 3.10, and the PyMuPDF build that Python 3.9 receives has no `Rect.get_area`. Python 3.9 was installed locally to reproduce both, a text-writing helper and an area helper fixed them, and because PyPI never replaces a file the package went out again as 1.0.1. The tag was moved to the green commit.

On 2026-09-30 the GitHub release `v1.0.0` was published with the executable, the extension package and both rulebook files attached; GitHub Pages went live at https://rupakkumar-76319.github.io/fmjl/ with the introduction and the rulebook; and the repository received its description, website and topics.

## Where things are

| What | Where |
| --- | --- |
| Source, rulebook, examples, benchmark | https://github.com/rupakkumar-76319/fmjl |
| Website and rulebook | https://rupakkumar-76319.github.io/fmjl/ |
| Python package, 1.0.1 | https://pypi.org/project/fmjl/ |
| VS Code extension, 1.0.0 | Marketplace, publisher rupakkumar, id `rupakkumar.fmjl` |
| Windows executable and release files | GitHub Releases, tag `v1.0.0` |

## Rules that held all the way through

1. The rulebook is the authority. When a tool and the rulebook disagree, the tool has a bug.
2. Change the rulebook first, then the Python package, then the JavaScript converter and validator; the JavaScript output must stay byte-identical to the Python output, and the test proves it before every commit.
3. Ids never change and are never reused; the rulebook and every example were regenerated many times without renumbering a single element.
4. Version numbers move together: rulebook, tool, converter, package and extension.
5. No comment lines in code or documents; no AI attribution in commits; commits are made by the owner.
6. No secrets in the repository and no personal documents among the examples; the samples are generated by scripts.

## What comes next

Findings from real documents go to `project/NOTES.md` and become rulebook 1.1, which may only add optional fields, types or subtypes. The candidates, in order of value: a loader for a vector database or a framework built on `fmjl.chunks`; a PPTX importer, since slides map to the group type the rulebook already defines; an XLSX and CSV importer for record elements; OCR tested on a real scan; and importers for the other formats the rulebook lists.
