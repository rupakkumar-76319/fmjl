# Changelog
## 1.1.1
- A `$$` line with text after the closing `$$`, or a `$$` block that is never closed, is a paragraph; it no longer swallows the rest of the document into one formula. Same for a paragraph starting with a word like `<tablet`, which is no longer read as a table. Both end at a blank line, as in Markdown.
- Converting a `.md` with a bad note value (`page=abc`) reports the line: `line 5: page=abc is not a whole number`.
- `confidence=` accepts only a plain decimal number from 0 to 1, the same values as the Python package. `0x10` and an empty value are errors now, not 16 and 0, and `confidence=1e22` can no longer write a line that is not valid JSON.
- Small numbers are written as Python writes them (`1e-07`).
- Control characters and rare Unicode spaces (form separators, next line, byte-order mark) count as space exactly as they do in the Python package, and the line and paragraph separators no longer stop a heading from being tidied. The live checker follows the same rule for empty lines.
- Matches the Python package 1.1.3 byte for byte.
## 1.1.0
- Matches rulebook version 1.1. The converter writes `"version":"1.1"`; files written as 1.0 stay valid.
- New command FMJL: Fill, also offered as a quick fix (light bulb) on every problem that `fmjl fill` repairs. Existing ids are kept.
- Outline view and breadcrumbs: headings, groups, tables, images, formulas and code, nested by parent.
- Hover shows an element's Markdown rendered; hover on an id shows the element it points to.
- Go to Definition and Find All References for element ids.
- The live checker now reports everything `fmjl check` reports: `\r\n` line endings, a byte-order mark, a missing final newline, `created` that is not a date-time, `elements` left as null, `date`, `authors`, `meta`, group names in `access`, and wrong value types for `parent`, `reference`, `continues`, `md` and others. `characters` is counted in code points, as in Python (an emoji counts as 1).
- `test/checker.js` breaks a document in 18 ways and checks that the extension and `fmjl check` flag the same lines.
- Converting saves an open, unsaved file first, and asks before replacing a `.fmjl` with fresh ids or a `.md` that was edited after the `.fmjl`.
- Ids are colored as ids.
## 1.0.0
- Matches rulebook version 1.0, the first stable version. Files written as 0.5 stay valid; the converter writes `"version":"1.0"`.
## 0.6.0
- Matches rulebook version 0.5: merged cells can be typed in a Markdown table with `^` (join the cell above) and `<` (join the cell to the left); the converter writes the HTML and shows the shortcut again when converting back.
- Notes accept `reference=above` and `reference=below`, so a caption can point at its picture without knowing the id.
- A table typed without its separator row gives a warning instead of silently becoming a paragraph.
- The missing-image message now says to copy the images/ folder.
## 0.5.0
- New commands: FMJL: Convert Markdown to .fmjl and FMJL: Convert .fmjl to Markdown, also in the right-click menu of .md and .fmjl files. Pure JavaScript; no Python needed. Output is byte-identical to fmjl.py (test/roundtrip.js proves it).
- The live checker now tests canonical Markdown and whether image files exist, so it covers every rule fmjl check covers.
## 0.4.0
- Matches rulebook version 0.4. Licensed under MIT, copyright Rupak Kumar.
- Marketplace links point to github.com/rupakkumar-76319/fmjl.
## 0.3.1
- The format is now called FMJL; the placeholder name "Format X" is gone. No rule changes.
## 0.3.0
- First release, matching rulebook version 0.3.
- Language definition, syntax coloring, live validation, FMJL: Check command.
