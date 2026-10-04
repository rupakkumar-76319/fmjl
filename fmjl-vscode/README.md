# FMJL for VS Code

Support for FMJL `.fmjl` files. FMJL, short for Format, Markdown, JSON Lines, is a
document format that combines four languages: JSON Lines as the container (one element
per line), Markdown for all readable text, LaTeX for formulas, and HTML for tables with
merged cells.

## Features
- **Convert without leaving VS Code.** Right-click any `.md` file and choose
  **FMJL: Convert Markdown to .fmjl**; right-click any `.fmjl` file and choose
  **FMJL: Convert .fmjl to Markdown**. Both are also in the Command Palette (Ctrl+Shift+P).
  Element ids are kept across edits, so converting back and forth never renumbers anything.
- Recognizes `.fmjl` files and colors field names, element types, strings and numbers.
- Live error checking while you type, with red underlines and messages in the Problems panel:
  JSON mistakes, missing required fields, wrong types and subtypes, wrong `hash` and
  `characters` values, non-canonical Markdown, missing image files, duplicate ids and
  labels, broken `parent` / `reference` / `continues` links, dead `[text](#label)` links,
  page and bbox rules, and header rules.
- **One-click fixes.** Problems such as a wrong `hash`, a wrong `characters` count, a missing
  field or non-canonical Markdown show a light bulb: **Fix with FMJL: Fill**. The same command,
  **FMJL: Fill**, is in the right-click menu. It works like `fmjl fill`: existing ids never change,
  new elements get the next free id.
- **Outline and breadcrumbs.** Headings, groups, tables, images, formulas and code appear in the
  Outline view, nested by `parent`, with the page shown as people count it (page 0 is page 1).
- **Hover** over an element line to read its Markdown rendered, instead of the escaped JSON
  string. Hover over an id in `parent`, `reference` or `continues` to see the element it points to.
- **Go to Definition** (F12) on an id jumps to that element; **Find All References** (Shift+F12)
  lists its children and everything that references it.
- Command **FMJL: Check current file** for a clear PASSED / FAILED answer. The live checker
  reports the same problems as `fmjl check`, including `\r\n` line endings, a byte-order mark
  and a missing newline at the end; `test/checker.js` proves it.
- Converting asks first before it would lose work: when a `.md` without id notes would replace
  an existing `.fmjl` (every id would change), or when the `.md` was edited after the `.fmjl`.

## How to use it
1. Write a normal Markdown file, for example `notes.md`. Put images in an `images/` folder
   next to it.
2. Right-click the file, **FMJL: Convert Markdown to .fmjl**. `notes.fmjl` opens with a
   PASSED or FAILED message.
3. To edit later, right-click `notes.fmjl`, **FMJL: Convert .fmjl to Markdown**, change the
   text, and convert back. Unchanged elements keep their ids and hashes.

## Notes
- The converter is pure JavaScript and needs no Python. Its output is byte-identical to the
  reference Python package `fmjl`; `npm test` checks that on every document in the repository.
- The rulebook is the authority. If this extension and the rulebook disagree, the
  extension has a bug: https://github.com/rupakkumar-76319/fmjl/issues

## The format
FMJL stores any document as elements (headings, paragraphs, lists, tables, formulas,
code, images, captions, footnotes, stamps, watermarks...) with ids, hashes, pages,
positions and permissions - built for RAG systems and search.

| Language | Job in FMJL |
| --- | --- |
| JSON Lines | The container: one element per line with its id, hash, page and permissions |
| Markdown | All readable text, and the whole authoring form people write in |
| LaTeX | Math formulas, in the `latex` field |
| HTML | Tables with merged cells, in the `html` field |

Markdown alone cannot record an image's page, link a caption to its image, or say who may
read a paragraph. JSON alone is unreadable for people. LaTeX alone is slow and hard to
write. HTML alone is heavy. FMJL keeps the strength of each.
See the rulebook: `rulebook/fmjl_rulebook_v1.1.md`, or read it at https://rupakkumar-76319.github.io/fmjl/rulebook.html
