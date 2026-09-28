# Changelog
## 0.5.0
- New commands: FMJL: Convert Markdown to .fmjl and FMJL: Convert .fmjl to Markdown, also in the right-click menu of .md and .fmjl files. Pure JavaScript; no Python needed. Output is byte-identical to fmjl.py (test/roundtrip.js proves it).
- The live checker now tests canonical Markdown and whether image files exist, so it covers every rule fmjl.py check covers.
## 0.4.0
- Matches rulebook version 0.4. Licensed under MIT, copyright Rupak Kumar.
- Marketplace links point to github.com/rupakkumar-76319/fmjl.
## 0.3.1
- The format is now called FMJL; the placeholder name "Format X" is gone. No rule changes.
## 0.3.0
- First release, matching rulebook version 0.3.
- Language definition, syntax coloring, live validation, FMJL: Check command.
