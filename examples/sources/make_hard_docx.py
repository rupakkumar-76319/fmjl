"""Writes a Word file with the features that break importers: tracked changes, hyphens, fields,
content controls, a comment, a text box, nested lists, merged and nested tables, a symbol, hidden
text. Each carries a marker word, so a test can check what came through (rulebook 10.1).

  python examples/sources/make_hard_docx.py hard.docx
"""
import sys
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

out = sys.argv[1]
d = Document()
W = nsdecls("w")


def raw(xml):
    body = d.element.body
    body.insert(len(body) - 1, parse_xml(xml))


sec = d.sections[0]
sec.header.paragraphs[0].text = "HEADERTEXT Hard Sample Report"
sec.footer.paragraphs[0].text = "FOOTERTEXT Confidential"

d.add_paragraph("Hard Sample Report", style="Title")
d.add_paragraph("A subtitle line", style="Subtitle")
d.add_heading("1. Tracked changes", level=1)
raw(f'<w:p {W}><w:r><w:t xml:space="preserve">The budget is </w:t></w:r>'
    f'<w:del w:id="1" w:author="A" w:date="2026-01-01T00:00:00Z"><w:r><w:delText>DELETEDWORD</w:delText></w:r></w:del>'
    f'<w:ins w:id="2" w:author="A" w:date="2026-01-01T00:00:00Z"><w:r><w:t>INSERTEDWORD</w:t></w:r></w:ins>'
    f'<w:r><w:t xml:space="preserve"> dollars.</w:t></w:r></w:p>')
d.add_heading("2. Hyphens", level=1)
raw(f'<w:p {W}><w:r><w:t>Send an e</w:t></w:r><w:r><w:noBreakHyphen/></w:r><w:r><w:t>mail about the in</w:t></w:r>'
    f'<w:r><w:softHyphen/></w:r><w:r><w:t>formation today.</w:t></w:r></w:p>')
d.add_heading("3. Hyperlink and line break", level=1)
raw(f'<w:p {W} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    f'<w:r><w:t xml:space="preserve">Visit </w:t></w:r><w:hyperlink r:id="rIdX"><w:r><w:t>LINKTEXT</w:t></w:r></w:hyperlink>'
    f'<w:r><w:t xml:space="preserve"> now.</w:t></w:r><w:r><w:br/><w:t>SECONDLINE after a break.</w:t></w:r></w:p>')
d.add_heading("4. Fields", level=1)
raw(f'<w:p {W}><w:r><w:t xml:space="preserve">Page </w:t></w:r><w:fldSimple w:instr=" PAGE "><w:r><w:t>7</w:t></w:r></w:fldSimple>'
    f'<w:r><w:t xml:space="preserve"> of the report, dated </w:t></w:r>'
    f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> DATE \\@ "d MMMM yyyy" </w:instrText></w:r>'
    f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>4 October 2026</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
    f'<w:r><w:t>.</w:t></w:r></w:p>')
d.add_heading("5. Content control", level=1)
raw(f'<w:sdt {W}><w:sdtPr><w:alias w:val="Client"/></w:sdtPr><w:sdtContent>'
    f'<w:p><w:r><w:t>SDTPARAGRAPH Client name is Acme Ltd.</w:t></w:r></w:p></w:sdtContent></w:sdt>')
raw(f'<w:p {W}><w:r><w:t xml:space="preserve">Inline control: </w:t></w:r><w:sdt><w:sdtContent><w:r><w:t>SDTINLINE</w:t></w:r></w:sdtContent></w:sdt>'
    f'<w:r><w:t xml:space="preserve"> end.</w:t></w:r></w:p>')
d.add_heading("6. Comment", level=1)
raw(f'<w:p {W}><w:commentRangeStart w:id="0"/><w:r><w:t>Commented sentence stays.</w:t></w:r><w:commentRangeEnd w:id="0"/>'
    f'<w:r><w:commentReference w:id="0"/></w:r></w:p>')
d.add_heading("7. Text box", level=1)
raw(f'<w:p {W} xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    f'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    f'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:v="urn:schemas-microsoft-com:vml">'
    f'<w:r><w:t xml:space="preserve">Before the box. </w:t></w:r><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing>'
    f'<wp:anchor><wp:extent cx="1" cy="1"/><a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
    f'<wps:wsp><wps:txbx><w:txbxContent><w:p><w:r><w:t>TEXTBOXCONTENT inside a box.</w:t></w:r></w:p></w:txbxContent></wps:txbx></wps:wsp>'
    f'</a:graphicData></a:graphic></wp:anchor></w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape><v:textbox><w:txbxContent>'
    f'<w:p><w:r><w:t>TEXTBOXCONTENT inside a box.</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>'
    f'</mc:AlternateContent></w:r><w:r><w:t xml:space="preserve">After the box.</w:t></w:r></w:p>')
d.add_heading("8. Lists", level=1)
d.add_paragraph("LISTONE first point", style="List Bullet")
d.add_paragraph("LISTTWO nested point", style="List Bullet 2")
d.add_paragraph("LISTTHREE back out", style="List Bullet")
d.add_paragraph("NUMONE first step", style="List Number")
d.add_paragraph("NUMTWO second step", style="List Number")
d.add_heading("9. Merged table", level=1)
t = d.add_table(rows=3, cols=3)
t.style = "Table Grid"
for r, row in enumerate([["Region", "Q1", "Q2"], ["North", "10", "12"], ["South", "8", "9"]]):
    for c, v in enumerate(row):
        t.cell(r, c).text = v
t.cell(0, 1).merge(t.cell(0, 2)).text = "QUARTERS"
d.add_heading("10. Table inside a table", level=1)
outer = d.add_table(rows=1, cols=2)
outer.style = "Table Grid"
outer.cell(0, 0).text = "OUTERCELL"
inner = outer.cell(0, 1).add_table(rows=1, cols=2)
inner.cell(0, 0).text = "INNERA"
inner.cell(0, 1).text = "INNERB"
d.add_heading("11. Bold line used as a heading", level=1)
p = d.add_paragraph()
p.add_run("FAKEHEADING Results Overview").bold = True
d.add_paragraph("Body text under the fake heading.")
d.add_heading("12. Symbols and special characters", level=1)
raw(f'<w:p {W}><w:r><w:t xml:space="preserve">Tick </w:t></w:r><w:r><w:sym w:font="Wingdings" w:char="F0FC"/></w:r>'
    f'<w:r><w:t xml:space="preserve"> and tab</w:t></w:r><w:r><w:tab/><w:t>TABBED, price 5 € and 10°C.</w:t></w:r></w:p>')
d.add_heading("13. Empty and whitespace paragraphs", level=1)
d.add_paragraph("")
d.add_paragraph("   ")
d.add_paragraph("AFTEREMPTY text.")
d.add_heading("14. Small caps and hidden text", level=1)
raw(f'<w:p {W}><w:r><w:t xml:space="preserve">Visible </w:t></w:r><w:r><w:rPr><w:vanish/></w:rPr><w:t>HIDDENTEXT</w:t></w:r>'
    f'<w:r><w:t xml:space="preserve"> end.</w:t></w:r></w:p>')
d.save(out)
print("wrote", out)
