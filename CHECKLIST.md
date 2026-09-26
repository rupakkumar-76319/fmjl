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

- [ ] Create `.gitignore` at the root with these lines:

```text
__pycache__/
*.pyc
node_modules/
benchmark/_corrupt.fmjl
```

- [ ] Run:

```powershell
cd G:\FMJL
git init
git add .
git commit -m "FMJL 0.4: rulebook, tool, extension, benchmark"
```

- [ ] Create an empty repository on GitHub (no README, no license yet)
- [ ] Push:

```powershell
git remote add origin https://github.com/<your-name>/<repo>.git
git branch -M main
git push -u origin main
```

---

## Stage 7: Decide the name and the license

- [x] Final name chosen: FMJL, short for Format, Markdown, JSON Lines (2026-09-26)
- [x] Name applied everywhere: rulebook 0.4, tool, extension 0.3.1, README
- [ ] Check the name is free on GitHub and PyPI (the VS Code Marketplace has no "fmjl" yet)
- [ ] Choose a license (MIT is the simplest choice for a format and a tool)
- [ ] Add a `LICENSE` file at the root
- [ ] Replace `fmjl-vscode/LICENSE.txt` with the same license
- [ ] Update rulebook section 18 to remove the license item; add a line to section 17
- [ ] Regenerate: `python fmjl.py md rulebook\fmjl_rulebook_v0.4.fmjl`, edit, `python fmjl.py new rulebook\fmjl_rulebook_v0.4.md`
- [ ] Commit

---

## Stage 8: Publish the extension

- [ ] Create a publisher at https://marketplace.visualstudio.com/manage
- [ ] Make sure `"publisher"` in `fmjl-vscode/package.json` equals that publisher name
- [ ] Add `"repository"` to `package.json` with the GitHub URL from stage 6
- [ ] Create a Personal Access Token at https://dev.azure.com with scope **Marketplace: Manage**
- [ ] Bump `"version"` in `package.json` (for example `0.3.1`) and add a line to `CHANGELOG.md`
- [ ] Publish:

```powershell
cd G:\FMJL\fmjl-vscode
npx @vscode/vsce login <publisher>
npx @vscode/vsce publish
```

- [ ] After a few minutes, search "FMJL" in the VS Code Extensions view and install it from there
- [ ] Commit the version bump

---

## Stage 9: Use the format for real documents

- [ ] Write a real document as Markdown (a policy, a report, class notes)
- [ ] `python fmjl.py new mydoc.md`; fix any errors it prints
- [ ] Open `mydoc.fmjl` in VS Code and confirm zero problems
- [ ] Edit the document: `python fmjl.py md mydoc.fmjl`, change the text, `python fmjl.py new mydoc.md`
- [ ] Confirm unchanged elements kept their ids and hashes (`git diff --word-diff mydoc.fmjl`)
- [ ] Try one document with a table that has merged cells (`<table>` with `rowspan`)
- [ ] Try one document with a group (a figure with an image and a caption)
- [ ] Write down anything the rulebook did not cover; these become the next rulebook changes

---

## Stage 10: Release version 1.0

- [ ] Resolve every gap found in stage 9, in the rulebook first, then in `fmjl.py` and `validator.js`
- [ ] Rulebook section 17 says what changed and how to upgrade
- [ ] `fmjl.py upgrade` handles every version from 0.1 to 1.0
- [ ] Benchmark re-run; results copied into `README.md`
- [ ] Rulebook renamed to version 1.0; `.fmjl` regenerated with `new`
- [ ] `fmjl.py` VERSION and CONVERTER set to `1.0`
- [ ] Extension bumped to `1.0.0` and published (stage 8 steps)
- [ ] Git tag: `git tag v1.0.0` and `git push --tags`
- [ ] GitHub release created with the `.vsix` attached

---

## Where you are today (2026-09-27)

Stages 1 to 5 are complete. In stage 7 the name is decided (FMJL); the license is still open.
Start at stage 6.
