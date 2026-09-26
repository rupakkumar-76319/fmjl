# FMJL for VS Code

Support for FMJL `.fmjl` files. FMJL, short for Format, Markdown, JSON Lines, is a
document format that combines four languages: JSON Lines as the container (one element
per line), Markdown for all readable text, LaTeX for formulas, and HTML for tables with
merged cells.

## Features
- Recognizes `.fmjl` files and colors field names, element types, strings and numbers.
- Live error checking while you type, with red underlines and messages in the Problems panel:
  JSON mistakes, missing required fields, wrong types and subtypes, wrong `hash` and
  `characters` values, duplicate ids and labels, broken `parent` / `reference` /
  `continues` links, dead `[text](#label)` links, page and bbox rules, and header rules.
- Command **FMJL: Check current file** (Ctrl+Shift+P) for a clear PASSED / FAILED answer.

## Notes
- The Python tool `fmjl.py check` remains the final judge. This extension catches the
  same core errors live; the only rule it does not test is canonical-Markdown rewriting.
- People usually write the authoring form (a normal Markdown file) and convert it with
  `python fmjl.py new notes.md`; this extension is for reading and fixing the `.fmjl` file.

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
See the rulebook: `rulebook/fmjl_rulebook_v0.4.md`.
