"""Writes examples/sample_book.pdf: a short generated novel laid out like a printed book, to test
the book rules of the PDF importer (rulebook 10.1): front matter before the first chapter,
"CHAPTER I." lines, running headers with page numbers, indented paragraphs, and paragraphs
that run over a page break.

  python examples/sources/make_sample_book.py examples/sample_book.pdf
"""
import sys
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

out = sys.argv[1]
TITLE = "THE LIGHTHOUSE KEEPER"
body = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=13, firstLineIndent=14,
                      alignment=TA_JUSTIFY)
chapter = ParagraphStyle("chapter", parent=body, firstLineIndent=0, alignment=TA_CENTER,
                         spaceBefore=40, spaceAfter=18)
title = ParagraphStyle("title", parent=chapter, fontName="Times-Bold", fontSize=22, leading=26)
small = ParagraphStyle("small", parent=chapter, fontSize=9, spaceBefore=6, spaceAfter=6)

SEASONS = ["autumn", "winter", "spring", "summer"]
THINGS = ["the lamp", "the logbook", "the brass rail", "the oil store", "the foghorn", "the stair"]


def paragraph(ch, n):
    season, thing = SEASONS[(ch + n) % 4], THINGS[(ch * 3 + n) % 6]
    return (f"In the {season} of that year Mara climbed the tower before dawn, as she had done for "
            f"eleven years, and checked {thing} with the slow care her father had taught her. The sea "
            f"below was grey and patient, and the gulls had not yet woken. She wrote the hour in the "
            f"margin, the state of the wind, and a line about the boats that had passed in the night, "
            f"because a keeper who forgets the small things will one day forget a large one. When the "
            f"light was steady she sat on the top step and watched the coast take shape out of the dark, "
            f"first the rocks, then the harbour wall, then the roofs of the village where nobody "
            f"remembered that the tower had a keeper at all.")


def header(canvas, doc):
    page = doc.page
    if page <= 3:
        return
    canvas.saveState()
    canvas.setFont("Times-Roman", 8)
    number = page + 6
    if page % 2:
        canvas.drawRightString(A5[0] - 1.6 * cm, A5[1] - 1.1 * cm, f"{TITLE}. {number}")
    else:
        canvas.drawString(1.6 * cm, A5[1] - 1.1 * cm, f"{number} {TITLE}.")
    canvas.restoreState()


story = [Spacer(1, 120), Paragraph(TITLE, title), Paragraph("A NOVEL", small), PageBreak(),
         Spacer(1, 200), Paragraph("This sample book was generated for testing the FMJL importer.", small),
         Paragraph("No part of it is a real publication.", small), PageBreak(),
         Paragraph("CONTENTS", small), Paragraph("I. The Tower", small), Paragraph("II. The Boat", small),
         Paragraph("III. The Storm", small), PageBreak()]
item = ParagraphStyle("item", parent=body, firstLineIndent=0, leftIndent=14)
for ch, name in enumerate(["I", "II", "III"]):
    story.append(Paragraph(f"CHAPTER {name}.", chapter))
    story += [Paragraph(paragraph(ch, n), body) for n in range(7)]
    if ch == 0:
        story += [Paragraph("Every evening she did the same four things:", body)]
        story += [Paragraph(t, item) for t in ("trimming the wick", "polishing the lens",
                                                "winding the clock", "writing the date in the log")]
    story.append(PageBreak())
story.pop()
SimpleDocTemplate(out, pagesize=A5, title="The Lighthouse Keeper", author="FMJL test team",
                  topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=1.6 * cm,
                  rightMargin=1.6 * cm).build(story, onFirstPage=header, onLaterPages=header)
print("wrote", out)
