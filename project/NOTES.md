# Notes from using FMJL

Findings that the rulebook did not cover. Each one is resolved in the next rulebook version or listed as still open.

## Still open (rulebook 1.1, section 18)

1. Formulas in a PDF are read as ordinary text; there is no way yet to recover LaTeX from a PDF (was note 7).
2. Reading order for two-column pages uses a simple left-then-right rule per band; three columns come out wrong (was note 13). Sidebars are handled since 1.1.
3. The PDF importer's OCR path is untested because Tesseract is not installed here (was note 12).
4. Printed page numbers: a book prints its own numbers ("PERSUASION. 101") that differ from `page`. The running header keeps the printed number as a `noise` element, but nothing maps a page to its printed number yet.
5. A decorated first letter (drop cap) is a picture in scans, so the first word of a chapter loses its first letter ("IR WALTER" for "SIR WALTER").

## Resolved in rulebook 1.1 (2026-10-04)

Found by converting a 345-page scanned novel (Persuasion, Google Books scan) after the 1.0 release.

1. The text layer of a scan split one paragraph into several blocks, often mid-sentence (1,198 such splits): blocks are joined by layout (10.1, rule 12).
2. A line's last word stood in a block of its own and came out after the paragraph (63 cases): it goes back into its line (10.1, rule 12).
3. Words without a space between them ("onlytwo", "hopeI"; 331 cases): spaces are restored on scanned pages (10.1, rule 15).
4. Running headers "PERSUASION. 11" and "102 PERSUASION." were paragraphs on 60 pages because their page number had a different number of digits: a header is matched by its letters (10.1, rule 11).
5. Chapters "CHAPTER I." were paragraphs, so 2,734 of 2,772 elements had one parent: chapter lines become headings (10.1, rule 14).
6. Library bookplate words became headings ("RESPONDET", "BookFund"): headings before the first chapter become paragraphs, and `fmjl.body` marks where the book starts (7.6, 10.1 rule 14).
7. Paragraphs cut by a page break were linked only when the next page started in lower case: the layout decides (10.1, rule 13), and `fmjl chunks` joins linked parts into one chunk (12.1).
8. Blank endpapers were saved as images with a "no text layer" warning: blank pages are skipped (10.1, rule 15).

Then five more books were converted and screened with `benchmark/quality.py` before anyone used them. Problems it found:

9. Real hyphens were dropped at line ends ("selfesteem", "wellbeing"): kept when the document writes the word with a hyphen (10.1, rule 12).
10. Running headers that name the chapter repeat on fewer than 30% of pages and were missed (13 in one book): three pages are enough, and Roman page numbers are ignored (rule 11).
11. A margin column of quotations was read across the body text: 229 of 496 pages came out in the wrong order and 2,359 paragraphs were cut. Sidebars are now their own stream (rule 16); wrong-order pages fell to 19.
12. Drop caps were glued to the heading above ("The Demonic Rake I" and "n the early 1880s"): they rejoin their paragraph (rule 12).
13. Titles ending in "?" were paragraphs, and chapter numbers on their own line were headings "## 6": both fixed (rule 17).
14. Footnote markers "[xix]" became paragraphs of their own: they rejoin their line (rule 12).
15. Letter and Roman list markers ("I.", "a)") were lost: kept (rule 18).

Run `python benchmark/quality.py some.pdf` on every new kind of PDF before trusting it; CI runs it on the samples with `--strict`.

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
