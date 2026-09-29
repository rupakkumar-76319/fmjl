# Notes from using FMJL

1. A table typed without | at the ends and no separator row became a paragraph (e4). The tool should warn.
2. Merged cells work, but I had to write raw HTML. A shortcut would help.
3. In a group, the first bold line becomes the group title and its id vanishes. The rulebook should say this clearly.
4. To write reference=e9 I first had to regenerate the .md to learn the image's id.
5. When the output .fmjl is written to another folder, the check says the image file does not exist. The message should say "copy the images folder too".

## From the PDF importer (2026-09-29)

6. Merged cells in a PDF table come out as a plain Markdown table with empty cells; the importer should write HTML with rowspan and colspan when PyMuPDF reports a merged cell.
7. Formulas in a PDF are read as ordinary text (the letters and symbols of the equation). There is no way yet to recover LaTeX from a PDF.
8. A figure with its caption is written as two elements linked by reference=, not as a group. The rulebook should say which one importers must produce.
9. Charts drawn as vector graphics (lines and shapes, not an embedded picture) are skipped; only embedded images are exported.
10. Heading levels come from font sizes, so a document with inconsistent fonts gets uneven levels (a level 4 heading directly under level 2). A "compact levels" step would help.
11. An OCR text layer from an old scan has no reliable font sizes, so almost no headings are found. A scanned paper needs a different heading rule, for example all-capital short lines.
12. The importer has an OCR path for pages without text, but it is untested because Tesseract is not installed here.
13. Reading order for two-column pages is handled by a simple left-then-right rule per band; a page with three columns or a sidebar will come out wrong.

## From the Word importer (2026-09-29)

14. Formulas in Word (OMML) are read as plain text. A converter from OMML to LaTeX would make Word the best source for formulas.
15. Word has no pages; the importer uses the page breaks Word recorded at its last save, which can be stale. No bbox is possible.
16. Tracked changes: insertions are read as final text and deletions are dropped, without any warning.
17. Word captions sit above tables and below figures; the importer links to the nearest image or table, before or after. A caption between a table and an image is ambiguous.
18. Footnotes are separate elements with reference= to the citing paragraph, and the paragraph text carries [^n]. The rulebook does not say how footnote markers should appear in md.
