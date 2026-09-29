import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
                                ListFlowable, ListItem, PageBreak)

out, image = sys.argv[1], sys.argv[2]
styles = getSampleStyleSheet()
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=14, spaceAfter=8)
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, leading=24, spaceAfter=12)
h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, leading=18, spaceBefore=10, spaceAfter=6)
cap = ParagraphStyle("cap", parent=body, fontSize=9, textColor=colors.grey)


def deco(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "Solar Schools Programme - Annual Report 2026")
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, "Page %d" % doc.page)
    canvas.restoreState()


story = [
    Paragraph("Solar Schools Programme", h1),
    Paragraph("Annual report on the rooftop solar installations completed in 240 schools during 2026. "
              "The programme is funded jointly by the state and the participating districts.", body),
    Paragraph("1. Summary", h2),
    Paragraph("Installed capacity reached 9.6 megawatts across all schools, which is 20 percent more than "
              "planned. Electricity bills fell by an average of 61 percent. Three districts finished ahead of "
              "schedule and two are still in progress because of monsoon delays.", body),
    Paragraph("The main results of the year were:", body),
    ListFlowable([ListItem(Paragraph("240 schools connected, 40 kilowatts each on average", body)),
                  ListItem(Paragraph("9.6 megawatts of installed capacity", body)),
                  ListItem(Paragraph("61 percent lower electricity bills", body))], bulletType="bullet"),
    Paragraph("2. Results by district", h2),
    Paragraph("Table 1 lists the schools completed and the capacity installed in each district.", body),
]
data = [["District", "Schools", "Capacity (kW)", "Bill reduction"],
        ["Patna", "62", "2,480", "64%"], ["Gaya", "48", "1,920", "59%"],
        ["Muzaffarpur", "55", "2,200", "62%"], ["Bhagalpur", "41", "1,640", "58%"],
        ["Darbhanga", "34", "1,360", "60%"]]
t = Table(data, hAlign="LEFT")
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                       ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
story += [t, Paragraph("Table 1: Completed installations by district", cap), Spacer(1, 8), PageBreak(),
          Paragraph("3. A typical installation", h2),
          Paragraph("Most schools received panels on the main building. The photo below shows a completed "
                    "rooftop in Gaya district. Panels are cleaned monthly by the school's maintenance staff, "
                    "and the inverter is checked every quarter by the district engineer.", body),
          Image(image, width=10 * cm, height=6 * cm), Paragraph("Figure 1: Rooftop panels on a school in Gaya", cap),
          Paragraph("4. Problems found", h2),
          Paragraph("Two problems appeared during the year. The first was theft of cables at four schools, "
                    "which was solved by moving the inverters indoors. The second was shading from trees, "
                    "which reduced output at eleven schools; the trees were trimmed and output recovered "
                    "within a month. Neither problem is expected to", body)]
story += [PageBreak(),
          Paragraph("recur in 2027 because the new installation checklist covers both. The checklist is "
                    "attached as an appendix.", body),
          Paragraph("5. Next year", h2),
          Paragraph("The programme will add 300 schools in 2027 and start battery storage trials in "
                    "twenty of them.", body)]
SimpleDocTemplate(out, pagesize=A4, title="Solar Schools Programme Annual Report 2026",
                  author="Rupak Kumar").build(story, onFirstPage=deco, onLaterPages=deco)
print("wrote", out)
