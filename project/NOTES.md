# Notes from using FMJL

Findings that the rulebook did not cover. Each one is resolved in the next rulebook version or listed as still open.

## Still open (rulebook 1.0, section 18)

1. Formulas in a PDF are read as ordinary text; there is no way yet to recover LaTeX from a PDF (was note 7).
2. Reading order for two-column pages uses a simple left-then-right rule per band; three columns or a sidebar come out wrong (was note 13).
3. The PDF importer's OCR path is untested because Tesseract is not installed here (was note 12).

## Resolved in rulebook 0.5 (2026-09-29)

1. A table typed without the separator row became a paragraph: the tool now warns (9.2).
2. Merged cells needed raw HTML: `^` and `<` in a Markdown table now do it, and tool-written HTML has one canonical form (8.6, 9.2).
3. The group's first block is its title and has no id of its own: written down (9.4).
4. Writing `reference=e9` needed the image's id: `reference=above` and `reference=below` (9.3).
5. The missing-image message now says to copy the `images/` folder too.
6. PDF merged cells come out as HTML with rowspan and colspan (10.1).
7. Still open, see above.
8. Importers write an image and its caption as two linked elements, not a group (10.1).
9. Vector charts are rendered to PNG with their axis labels (10.1).
10. Heading levels never jump more than one step (10.1).
11. Scans without font sizes get headings from capital or numbered short lines (10.1).
12. Still open, see above.
13. Still open, see above.
14. Word formulas (OMML) become LaTeX; display math is a `formula` element (10.1).
15. Word pages come from recorded page breaks and never have a bbox: written down (10.1).
16. Tracked changes are accepted with a warning and counted in `meta` as `fmjl.tracked_changes` (7.6, 10.1).
17. A caption picks a table or an image by its first word (10.1).
18. Footnote markers are `[^n]` and the footnote's `md` starts with `[^n]: ` (7.5).
19. A caption or footnote joins the chunk of the element it references (12.1).
20. A heading with nothing under it joins the next section's chunk (12.1).
21. What a chunk is: defined (12.1).
