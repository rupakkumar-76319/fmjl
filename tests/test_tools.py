"""Tests for the importers, the chunker and export. Run from the repository root:

  python -m unittest discover -s tests -v

Word, OpenDocument and EPUB export tests run only when pandoc is installed.
"""
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fmjl
from fmjl import export, pdf

EXAMPLES = ROOT / "examples"


class Temp(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="fmjl-test-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class HyphenRule(unittest.TestCase):
    """Rulebook 10.1, rule 19."""

    def test_line_end_hyphen(self):
        s = pdf.SOFT
        els = [{"md": "Her self-esteem was high."},
               {"md": f"low self{s}esteem, some{s}thing, good{s}looking"},
               {"md": "something else"}]
        pdf._resolve_hyphens(els)
        self.assertEqual(els[1]["md"], "low self-esteem, something, goodlooking")

    def test_soft_hyphen(self):
        self.assertEqual(pdf._join_lines(["some­", "thing", "ex­tra"]), "something extra")


class BookRules(Temp):
    """Rulebook 10.1, rules 11 to 18, and chunks 12.1, on the generated sample book."""

    def setUp(self):
        super().setUp()
        rows, _ = pdf.import_pdf(EXAMPLES / "sample_book.pdf", out_dir=self.dir)
        self.rows = rows

    def test_chapters_and_body(self):
        heads = [e["md"] for e in self.rows[1:] if e["type"] == "heading"]
        self.assertEqual(heads, ["# CHAPTER I.", "# CHAPTER II.", "# CHAPTER III."])
        first = next(e["id"] for e in self.rows[1:] if e["type"] == "heading")
        self.assertEqual(self.rows[0]["meta"]["fmjl.body"], first)

    def test_running_headers_are_noise(self):
        self.assertFalse(any(e["type"] == "paragraph" and "LIGHTHOUSE KEEPER." in e["md"] for e in self.rows[1:]))

    def test_page_breaks_joined_in_chunks(self):
        self.assertEqual(sum("continues" in e for e in self.rows[1:]), 3)
        joined = [c for c in fmjl.chunks(self.rows) if "pages" in c]
        self.assertEqual(len(joined), 3)
        self.assertTrue(all(len(c["elements"]) == 2 for c in joined))

    def test_list_without_bullets(self):
        items = [e["md"] for e in self.rows[1:] if e["type"] == "list" and "trimming the wick" in e["md"]]
        self.assertTrue(items)
        self.assertEqual(items[0].count("\n- "), 3)

    def test_front_matter_left_out_of_chunks(self):
        body = fmjl.chunks(self.rows)
        everything = fmjl.chunks(self.rows, front=True)
        self.assertLess(len(body), len(everything))
        self.assertTrue(body[0]["md"].startswith("# CHAPTER I."))


class SampleOutputsUnchanged(Temp):
    """Element ids are stable: importing a sample again gives the committed file."""

    def same(self, rows, committed):
        new = [{k: v for k, v in r.items() if k != "created"} for r in rows]
        old = [{k: v for k, v in r.items() if k != "created"} for r in fmjl.load(committed)]
        self.assertEqual(new, old)

    def test_pdf_sample(self):
        rows, _ = pdf.import_pdf(EXAMPLES / "solar_report.pdf", out_dir=self.dir)
        self.same(rows, EXAMPLES / "solar_report.fmjl")

    def test_word_sample(self):
        from fmjl import docx
        rows, _ = docx.import_docx(EXAMPLES / "maintenance_guide.docx", out_dir=self.dir)
        self.same(rows, EXAMPLES / "maintenance_guide.fmjl")


@unittest.skipUnless(importlib.util.find_spec("docx"), "needs python-docx")
class WordFeatures(Temp):
    """Rulebook 10.1, rule 20, on a generated Word file with a marker word per feature."""

    def setUp(self):
        super().setUp()
        from fmjl import docx
        src = self.dir / "hard.docx"
        subprocess.run([sys.executable, str(EXAMPLES / "sources" / "make_hard_docx.py"), str(src)],
                       check=True, capture_output=True)
        self.rows, _ = docx.import_docx(src, out_dir=self.dir)
        self.text = " ".join(e["md"] for e in self.rows[1:])

    def test_kept(self):
        for word in ("INSERTEDWORD", "e-mail", "information", "LINKTEXT", "SECONDLINE", "4 October 2026",
                     "SDTPARAGRAPH", "SDTINLINE", "TEXTBOXCONTENT", "OUTERCELL", "INNERA", "AFTEREMPTY", "✓"):
            self.assertIn(word, self.text)
        self.assertEqual(self.text.count("TEXTBOXCONTENT"), 1)

    def test_dropped(self):
        for word in ("DELETEDWORD", "HIDDENTEXT", "MMMM yyyy"):
            self.assertNotIn(word, self.text)

    def test_lists_and_merged_cells(self):
        lists = [e["md"] for e in self.rows[1:] if e["type"] == "list"]
        self.assertIn("  - LISTTWO", lists[0])
        self.assertIn("1. NUMONE", lists[0])
        self.assertTrue(any('colspan="2"' in e.get("html", "") for e in self.rows[1:]))


class Export(Temp):
    """fmjl export, rulebook section 16."""

    def test_md_html_pdf(self):
        src = EXAMPLES / "solar_report.fmjl"
        md = export.export(src, "md", self.dir / "a.md")
        self.assertIn("solar_report_e16.png", md.read_text(encoding="utf-8"))
        page = export.export(src, "html", self.dir / "a.html").read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", page)
        import pymupdf
        text = " ".join(p.get_text() for p in pymupdf.open(str(export.export(src, "pdf", self.dir / "a.pdf"))))
        self.assertIn("Neither problem is expected to recur", text.replace("\n", " "))

    def test_never_replaces_without_force(self):
        target = self.dir / "a.html"
        target.write_text("keep me", encoding="utf-8")
        with self.assertRaises(ValueError):
            export.export(EXAMPLES / "solar_report.fmjl", "html", target)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")
        export.export(EXAMPLES / "solar_report.fmjl", "html", target, force=True)
        self.assertNotEqual(target.read_text(encoding="utf-8"), "keep me")

    def test_default_name_does_not_replace_original(self):
        shutil.copy(EXAMPLES / "maintenance_guide.docx", self.dir)
        shutil.copy(EXAMPLES / "maintenance_guide.fmjl", self.dir)
        before = (self.dir / "maintenance_guide.docx").read_bytes()
        with self.assertRaises(ValueError):
            export.export(self.dir / "maintenance_guide.fmjl", "docx")
        self.assertEqual((self.dir / "maintenance_guide.docx").read_bytes(), before)

    def test_math_is_not_money(self):
        text, found = export._math("costs $5 or $10, and $E = mc^2$ holds")
        self.assertEqual([latex for _, latex in found], ["E = mc^2"])

    @unittest.skipUnless(shutil.which("pandoc"), "needs pandoc")
    def test_word_equations_and_merged_cells(self):
        doc = export.export(EXAMPLES / "solar_schools.fmjl", "docx", self.dir / "s.docx")
        xml = zipfile.ZipFile(doc).read("word/document.xml").decode("utf-8")
        self.assertRegex(xml, r"<m:oMath\b")
        guide = export.export(EXAMPLES / "maintenance_guide.fmjl", "docx", self.dir / "g.docx")
        xml = zipfile.ZipFile(guide).read("word/document.xml").decode("utf-8")
        self.assertTrue("gridSpan" in xml or "vMerge" in xml)
        for fmt in ("odt", "epub"):
            self.assertTrue(export.export(EXAMPLES / "solar_report.fmjl", fmt, self.dir / f"s.{fmt}").stat().st_size > 0)


class Converter(Temp):
    """Blocks that must not swallow what follows them, and errors that must name their line."""

    def types(self, text):
        return [e["type"] for e in fmjl.import_md(text, doc="t")[1:]]

    def test_formula_line_with_text_after_it_is_a_paragraph(self):
        self.assertEqual(self.types("$$a$$ is the start of a sentence\n\nNext.\n\n# Heading"),
                         ["paragraph", "paragraph", "heading"])

    def test_unclosed_formula_block_ends_at_the_blank_line(self):
        rows = fmjl.import_md("$$\nx = 1\n\nAfter.\n\n# Heading", doc="t")
        self.assertEqual([e["type"] for e in rows[1:]], ["paragraph", "paragraph", "heading"])
        self.assertEqual(rows[1]["md"], "$$\nx = 1")
        back = fmjl.import_md(fmjl.export_md(rows), doc="t")
        self.assertEqual([(e["id"], e["md"]) for e in back[1:]], [(e["id"], e["md"]) for e in rows[1:]])

    def test_closed_formula_block_still_a_formula(self):
        rows = fmjl.import_md("$$\nx = 1\n$$\n\nAfter.", doc="t")
        self.assertEqual(rows[1]["type"], "formula")
        self.assertEqual(rows[1]["latex"], "x = 1")

    def test_word_starting_with_table_is_not_a_table(self):
        self.assertEqual(self.types("<tablet> is a word\n\nNext.\n\n# Heading"), ["paragraph", "paragraph", "heading"])
        self.assertEqual(self.types("<table>\n<tr><td>a</td></tr>\n</table>\n\nNext."), ["table", "paragraph"])

    def test_bad_rowspan_is_reported_not_a_crash(self):
        header = ('{"type":"document","version":"1.1","doc":"bad","source":"bad.md","sha256":"' + "0" * 64
                  + '","protection":"none","signed":false,"converter":"fmjl 1.1","structure":false,"elements":1,'
                  '"created":"2026-01-01T00:00:00Z","lang":"en","access":["all"],"last_id":1}')
        row = ('{"id":"bad#e1","hash":"0000000000000000","type":"table","parent":null,"characters":1,'
               '"html":"<table><tr><td rowspan=\\"x\\">a</td></tr></table>","md":"x"}')
        path = self.dir / "bad.fmjl"
        fmjl.write_text(path, header + "\n" + row + "\n")
        errors = fmjl.check(path)
        self.assertTrue(any("not canonical" in e for e in errors))

    def test_note_error_names_the_line(self):
        with self.assertRaisesRegex(ValueError, r"^line 5: page=abc is not a whole number"):
            fmjl.import_md("---\ndoc: t\n---\n\n<!-- page=abc -->\nHello", doc="t")
        with self.assertRaisesRegex(ValueError, r"^line 1: bbox=x is not a whole number"):
            fmjl.import_md("<!-- bbox=1,2,x,4 -->\nHello", doc="t")

    def test_confidence_is_a_plain_decimal_number(self):
        for good, value in (("0.9", 0.9), (".5", 0.5), ("1e-2", 0.01), ("1", 1.0), ("0", 0.0), ("1e-7", 1e-7)):
            self.assertEqual(fmjl.import_md(f"<!-- confidence={good} -->\nHello", doc="t")[1]["confidence"], value)
        for bad in ("0x10", "1_0", "", "nan", "inf", "1e999", "abc", "5", "-1", "+0.5", "-0", "1e22", "٣"):
            with self.assertRaisesRegex(ValueError, r"is not a number from 0 to 1"):
                fmjl.import_md(f"<!-- confidence={bad} -->\nHello", doc="t")

    def test_section_chunk_keeps_its_heading_with_the_first_part(self):
        rows = fmjl.import_md("# D\n\n" + "word " * 40 + "\n\n" + "more " * 40, doc="t")
        out = fmjl.chunks(rows, by="section", max_chars=50)
        self.assertEqual([c["id"] for c in out], ["t#e1/1", "t#e1/2"])
        self.assertEqual(out[0]["elements"], ["t#e1", "t#e2"])


class ListNumbers(unittest.TestCase):
    def test_only_ascii_digits_start_a_numbered_list(self):
        self.assertEqual(fmjl.import_md("4. item", doc="t")[1]["type"], "list")
        self.assertEqual(fmjl.import_md("\u096a. item", doc="t")[1]["type"], "paragraph")
        self.assertEqual(fmjl.import_md("\u0663) item", doc="t")[1]["type"], "paragraph")


class PdfVersion(unittest.TestCase):
    """PyMuPDF 2 damages table text without an error, so the importer must refuse it."""

    def test_pymupdf_2_is_refused(self):
        try:
            from fmjl import pdf
        except ImportError:
            self.skipTest("pymupdf is not installed")
        pdf._check_pymupdf("1.28.2")
        with self.assertRaisesRegex(RuntimeError, r"below 2, found 2\.1"):
            pdf._check_pymupdf("2.1")


class Version(unittest.TestCase):
    def test_version_flag(self):
        done = subprocess.run([sys.executable, "-m", "fmjl", "--version"], capture_output=True, text=True, cwd=ROOT)
        self.assertRegex(done.stdout, r"^fmjl \d+\.\d+\.\d+ \(rulebook \d+\.\d+\)")


if __name__ == "__main__":
    unittest.main()
