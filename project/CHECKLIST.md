# FMJL Checklist

---

## Stage 1: Design the format

- [x] Rulebook version 0.4 written: `rulebook/fmjl_rulebook_v0.4.md`
- [x] Rulebook stored in its own format: `rulebook/fmjl_rulebook_v0.4.fmjl`
- [x] JSON Schema included in the rulebook (section 14)
- [x] Both forms of the document defined: storage (`.fmjl`) and authoring (`.md`)
- [x] 20 element types and their subtypes listed (section 6)

---

## Stage 2: Build the tool

- [x] `new` (Markdown to .fmjl)
- [x] `md` (.fmjl to Markdown)
- [x] `fill` (ids, hashes, characters, parents, canonical Markdown)
- [x] `check` (every rule, with line numbers)
- [x] `view` (clean Markdown)
- [x] `info` (title, counts, outline)
- [x] `upgrade` (0.1 or 0.2 to 0.3)
- [x] Round trip proven: rulebook .fmjl to .md to .fmjl gives the same bytes

```powershell
python fmjl.py check rulebook\fmjl_rulebook_v0.4.fmjl
python fmjl.py check examples\solar_schools.fmjl
python fmjl.py new rulebook\fmjl_rulebook_v0.4.md -o %TEMP%\test.fmjl
```

---

## Stage 3: Build the VS Code extension

- [x] Extension source in `fmjl-vscode/` (language, grammar, validator, command)
- [x] Packaged as `fmjl-vscode/fmjl-0.3.1.vsix`
- [x] Installed on this computer as `formatx.fmjl`

---

## Stage 4: Test the extension by hand

- [x] Ctrl+Shift+P, run **Developer: Reload Window**
- [x] Open `examples\solar_schools.fmjl`; the status bar shows **FMJL**
- [x] Field names, element types, strings and numbers are coloured
- [x] Change `"characters":33` to `34` on line 2; a red underline appears within a second
- [x] Ctrl+Shift+M opens the Problems panel and explains the error
- [x] Undo the change; the underline disappears
- [x] Ctrl+Shift+P, run **FMJL: Check current file**; a PASSED popup appears
- [x] Open `rulebook\fmjl_rulebook_v0.4.fmjl`; no errors

---

## Stage 5: Tidy the project folder

- [x] `fmjl.py` at the root
- [x] `README.md` at the root explaining the layout and commands
- [x] `rulebook/`, `examples/`, `benchmark/`, `archive/`, `fmjl-vscode/` folders
- [x] Sample image in `examples/images/` so the `file` field is correct
- [x] Install the benchmark's missing package: `pip install pylatexenc`
- [x] Run the benchmark: `python benchmark\benchmark.py`
- [x] Open `benchmark\results.json` and confirm FMJL scores 100% on accuracy

---

## Stage 6: Put the project under version control

- [x] Create `.gitignore` at the root with these lines:

```text
__pycache__/
*.pyc
node_modules/
benchmark/_corrupt.fmjl
```

- [x] Run:

```powershell
cd G:\FMJL
git init
git add .
git commit -m "FMJL 0.4: rulebook, tool, extension, benchmark"
```

- [x] Create an empty repository on GitHub (github.com/rupakkumar-76319/fmjl)
- [x] Push:

```powershell
git remote add origin https://github.com/<your-name>/<repo>.git
git branch -M main
git push -u origin main
```

---

## Stage 7: Decide the name and the license

- [x] Final name chosen: FMJL, short for Format, Markdown, JSON Lines (2026-09-26)
- [x] Name applied everywhere: rulebook 0.4, tool, extension 0.3.1, README
- [x] Check the name is free on GitHub and PyPI (the VS Code Marketplace has no "fmjl" yet)
- [x] License chosen: MIT, copyright Rupak Kumar
- [x] Add a `LICENSE` file at the root
- [x] Replace `fmjl-vscode/LICENSE.txt` with the same license
- [x] Update rulebook section 18 to remove the license item; add a line to section 17
- [x] Regenerate: `python fmjl.py md rulebook\fmjl_rulebook_v0.4.fmjl`, edit, `python fmjl.py new rulebook\fmjl_rulebook_v0.4.md`
- [x] Commit

---

## Stage 8: Publish the extension

- [x] Create a publisher at https://marketplace.visualstudio.com/manage
- [x] Make sure `"publisher"` in `fmjl-vscode/package.json` equals that publisher name (currently `rupakkumar`)
- [x] Add `"repository"` to `package.json` with the GitHub URL from stage 6
- [x] Create a Personal Access Token at https://dev.azure.com with scope **Marketplace: Manage**
- [x] Bump `"version"` in `package.json` to `0.4.0` and add a line to `CHANGELOG.md`
- [x] Publish:

```powershell
cd G:\FMJL\fmjl-vscode
npx @vscode/vsce login <publisher>
npx @vscode/vsce publish
```

- [x] After a few minutes, search "FMJL" in the VS Code Extensions view and install it from there
- [x] Commit the version bump

---

## Stage 9: Use the format for real documents

- [x] Write a real document as Markdown (a policy, a report, class notes)
- [x] `python fmjl.py new mydoc.md`; fix any errors it prints
- [x] Open `mydoc.fmjl` in VS Code and confirm zero problems
- [x] Edit the document: `python fmjl.py md mydoc.fmjl`, change the text, `python fmjl.py new mydoc.md`
- [x] Confirm unchanged elements kept their ids and hashes (`git diff --word-diff mydoc.fmjl`)
- [x] Try one document with a table that has merged cells (`<table>` with `rowspan`)
- [x] Try one document with a group (a figure with an image and a caption)
- [x] Write down anything the rulebook did not cover; these become the next rulebook changes

---

## Stage 10: PDF importer

- [x] `fmjl_pdf.py` at the root: `fmjl report.pdf` writes `report.fmjl` and `report.md`, images into `images/`
- [x] Headings from font size, paragraphs from columns, lists, tables (merged cells still plain Markdown, NOTES.md 6), images with captions
- [x] Every element carries `page` and `bbox`; repeated headers, footers and page numbers become `noise`
- [ ] Formulas kept as LaTeX where the PDF has them as text; otherwise as images (NOTES.md 7)
- [ ] Scanned PDFs: OCR step with `confidence` filled in (path exists, needs Tesseract to test)
- [ ] Tested on five real PDFs of different kinds (done: generated report, project report, scanned paper; still needed: slides, form); findings in `NOTES.md`

---

## Stage 11: Word importer

- [x] `fmjl_docx.py`: `fmjl report.docx` writes `report.fmjl` and `report.md`
- [x] Headings, lists, tables with merged cells, images, captions, footnotes taken from the document structure
- [ ] Tested on three real Word files (done: one generated sample; real files still needed); findings in `NOTES.md`

---

## Stage 12: Retriever output

- [x] `fmjl chunks report.fmjl`: one retriever-ready chunk per element or per heading section, with id, page, bbox, hash, access and the heading path as metadata; `--since old.fmjl` lists only what changed
- [x] `import fmjl` works as a Python library: `fmjl.load(path)`, `fmjl.chunks(rows)`, `fmjl.changed_chunks(new, old)`, `fmjl.check(path)`
- [x] One working example: `examples/rag_demo.py`, a folder of .fmjl files to chunks to a TF-IDF index to a question answered with page citations (Claude answers when a key is set)

---

## Stage 13: Rulebook 0.5

- [x] Every entry in `NOTES.md` resolved: in the rulebook first, then in `fmjl.py`, `converter.js` and `validator.js` (three stay open by design: LaTeX from PDF, three-column pages, OCR untested; rulebook section 18)
- [x] Rulebook section 17 says what changed and how to upgrade; `fmjl.py upgrade` handles 0.1 to 0.5
- [x] Rulebook regenerated with `fmjl new`; round trip still byte-identical; `npm test` passes

---

## Stage 14: Make it available to everyone

- [x] Python package built: `pyproject.toml`, `python -m build` gives `dist/fmjl-0.5.0-py3-none-any.whl` and the sdist; installed in a clean venv, the `fmjl` command converts, imports Word files and makes chunks (`pip install "fmjl[pdf]"` adds PyMuPDF)
- [x] Uploaded to PyPI on 2026-09-29: https://pypi.org/project/fmjl/ ; `pip install fmjl` in a clean environment gives 0.5.0 and a working command. For later releases:

```powershell
cd G:\FMJL
python -m build
twine upload dist/fmjl-0.5.0*
```

- [x] `fmjl.exe` for Windows built with PyInstaller into `dist/` (not committed; attach it to the 1.0 release in stage 15):

```powershell
pip uninstall -y typing
pyinstaller --onefile --clean --name fmjl --paths . --hidden-import fmjl.pdf --hidden-import fmjl.docx --hidden-import pymupdf --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module tensorflow --exclude-module transformers --exclude-module sklearn --exclude-module scipy --exclude-module matplotlib --exclude-module pandas --exclude-module numpy --exclude-module PIL --exclude-module cv2 --exclude-module IPython --exclude-module jupyter --exclude-module tkinter --distpath dist --workpath build\pyinstaller --specpath build fmjl\__main__.py
```

- [ ] Publish extension 0.6.0 (matches rulebook 0.5): `cd fmjl-vscode` then `npx @vscode/vsce publish`
- [x] README rewritten for a stranger: what FMJL is, install in one line, convert in one line, use in RAG in ten lines
- [x] GitHub: issue templates in `.github/ISSUE_TEMPLATE/`, test workflow `.github/workflows/test.yml` (Python checks, round trip, importers, package build, `npm test` on every push)
- [ ] GitHub topics: on the repository page click the gear next to About and add `fmjl`, `rag`, `document-format`, `jsonl`, `markdown`, `pdf`, `docx`, `retrieval`
- [x] Benchmark re-run with the importers included (`benchmark/results.json` has an `importers` section); the table is in `README.md`

---

## Stage 15: Release version 1.0

- [x] Rulebook renamed to version 1.0 (`rulebook/fmjl_rulebook_v1.0.*`, 0.5 in `archive/`); `.fmjl` regenerated with `new`, ids kept; section 17 has the 1.0 entry and section 13 the 1.x reader promise
- [x] `fmjl` VERSION and CONVERTER set to `1.0`; extension `1.0.0`; PyPI `1.0.0`; every example regenerated as 1.0; docs rebuilt
- [x] Release artifacts built into `dist/` (wheel, sdist, `fmjl.exe`) and `fmjl-vscode/fmjl-1.0.0.vsix`
- [x] Committed and tagged `v1.0.0`; PyPI has `fmjl` 1.0.0; the Marketplace has `rupakkumar.fmjl` 1.0.0 (2026-09-29)
- [x] Python 3.9 fixes after the first CI run (`Path.write_text(newline=)` and PyMuPDF 1.26 `Rect.get_area`); package 1.0.1 built, tested on 3.9 and 3.13
- [ ] Publish the fix: `git add -A`, `git commit -m "Python 3.9 and PyMuPDF 1.26 fixes; package 1.0.1"`, `git tag -f v1.0.0`, `git push origin main`, `git push -f origin v1.0.0`, then `twine upload dist/fmjl-1.0.1*`

- [x] GitHub release `v1.0.0` published 2026-09-30 with `fmjl.exe`, `fmjl-1.0.0.vsix` and both rulebook files attached
- [x] GitHub Pages live at https://rupakkumar-76319.github.io/fmjl/ (introduction and rulebook)
- [x] PyPI 1.0.1 (the Python 3.9 fix) is the latest version; the tag `v1.0.0` points at the green commit
- [x] GitHub topics set (2026-09-30): fmjl, rag, retrieval-augmented-generation, document-format, jsonl, markdown, pdf, docx, retrieval
- [x] Announce: `project/ANNOUNCEMENT.md` is the post, with the benchmark table and the links

---

## Where you are today (2026-09-29)

Everything is built for version 1.0: rulebook 1.0, the `fmjl` package, the PDF and Word importers, the
retriever output, extension 1.0.0, `fmjl.exe`, the website in `docs/`, and the announcement. What is left
is publishing with your accounts, listed in stage 15. After that, findings go to `project/NOTES.md` for 1.1.
