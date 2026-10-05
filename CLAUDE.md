# FMJL, notes for anyone working on this repository

FMJL, short for Format, Markdown, JSON Lines, is a document format for RAG pipelines. It combines four languages, each doing one job: JSON Lines is the container (one element per line), Markdown holds all readable text, LaTeX holds formulas, HTML holds tables with merged cells. It is not "JSON plus Markdown"; say four languages.

## Layout

```text
fmjl/            the Python package: __init__.py (converter, checker, chunks), pdf.py, docx.py, __main__.py
rulebook/        the specification in both forms; the .fmjl is the master
examples/        sample documents (Markdown, PDF, Word), images/, rag_demo.py, sources/ (sample generators)
fmjl-vscode/       the VS Code extension (published as rupakkumar.fmjl); src/converter.js is a JavaScript port of the package
benchmark/       the same document in four formats, scored; results.json; quality.py checks any PDF conversion
tests/           unittest suite: python -m unittest discover -s tests
docs/            the GitHub Pages site: index.html, rulebook.html (built by docs/build.py), style.css
project/         CHECKLIST.md (the stages of the project) and NOTES.md (findings for the next rulebook)
archive/         older rulebooks and extension packages
README.md        an FMJL document itself; README.fmjl is regenerated from it with `fmjl README.md`
```

## Rules that are not obvious from the code

1. The rulebook is the authority. When the tool and the rulebook disagree, the tool has a bug. Change the rulebook first, then `fmjl/__init__.py`, then `fmjl-vscode/src/converter.js` and `validator.js`.
2. The JavaScript converter must stay byte-identical to the Python one. `npm test` in `fmjl-vscode/` compares both on every document in the repository; it must pass before a commit.
3. Edit the rulebook only through its storage form: `fmjl md rulebook/fmjl_rulebook_vX.fmjl -o somewhere/rb.md`, edit that copy (it carries the ids), `fmjl new` it back to the `.fmjl`, then write the repository `.md` without the note lines. Ids are never reused and never renumbered.
4. Element ids are stable. Never regenerate a document in a way that renumbers unchanged elements; the tests and the benchmark check this.
5. No comment lines in code or documents. Docstrings are fine; `//`, `#` and `<!-- -->` comments are not, except the id notes that the tool itself writes.
6. Commits are made by the project owner. Never add Co-Authored-By or any AI attribution line to a commit message.
7. Never store secrets in the repository: the Marketplace token, the PyPI token, API keys. Never copy personal documents into `examples/` or anywhere else in the repository; use generated samples (`examples/sources/`).
8. Page numbers start at 0 in files and are shown to people as page plus 1. `bbox` is `[left, top, right, bottom]` in 0..1000.
9. Versions move together: rulebook version, `VERSION` and `CONVERTER` in `fmjl/__init__.py` and `fmjl-vscode/src/converter.js`, the package version `__version__` in `fmjl/__init__.py` (`pyproject.toml` reads it from there), and the extension version in `fmjl-vscode/package.json`. Section 17 of the rulebook lists every change.

## Everyday commands

```powershell
fmjl notes.md                     # or: python -m fmjl new notes.md
fmjl notes.fmjl                   # back to Markdown, ids kept
fmjl report.pdf                   # PDF importer (pip install pymupdf)
fmjl report.docx                  # Word importer
fmjl chunks notes.fmjl --by section
python benchmark\benchmark.py
cd fmjl-vscode; npm test            # converter vs Python, byte for byte
python -m unittest discover -s tests   # importers, book rules, Word features, export
python benchmark\quality.py some.pdf   # compare a PDF with its conversion before trusting it
python docs\build.py              # rebuild docs/rulebook.html from the rulebook
python -m build                   # wheel and sdist into dist/
```
