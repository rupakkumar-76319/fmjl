"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const conv = require("../src/converter.js");
const { validate, elementHash } = require("../src/validator.js");

const ROOT = path.resolve(__dirname, "..", "..");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "fmjl-check-"));
let failures = 0;
fs.cpSync(path.join(ROOT, "examples", "images"), path.join(TMP, "images"), { recursive: true });

const good = fs.readFileSync(path.join(ROOT, "examples", "my_notes.fmjl"), "utf8");
const lines = good.trimEnd().split("\n");

function withLine(n, change) {
  const copy = lines.slice();
  const row = JSON.parse(copy[n]);
  change(row);
  copy[n] = conv.dumps(row);
  return copy.join("\n") + "\n";
}

function rehash(row) {
  row.hash = elementHash(row.type, row.md);
  return row;
}

const cases = {
  "repository file": good,
  "CRLF line endings": good.replace(/\n/g, "\r\n"),
  "byte-order mark": "﻿" + good,
  "no newline at the end": good.trimEnd(),
  "empty line": lines.slice(0, 2).join("\n") + "\n\n" + lines.slice(2).join("\n") + "\n",
  "broken JSON": lines.slice(0, 3).join("\n") + "\n{\"id\":\n" + lines.slice(4).join("\n") + "\n",
  "created is not a date-time": withLine(0, (h) => { h.created = "yesterday"; }),
  "elements is null": withLine(0, (h) => { h.elements = null; }),
  "date in the wrong form": withLine(0, (h) => { h.date = "29/09/2026"; }),
  "access group with a space": withLine(0, (h) => { h.access = ["all staff"]; }),
  "characters counted in UTF-16": withLine(3, (e) => {
    e.md = "Solar \u{1F31E} power"; rehash(e); e.characters = e.md.length;
  }),
  "parent is a number": withLine(3, (e) => { e.parent = 2; }),
  "reference list of one": withLine(3, (e) => { e.reference = [lines[1] && JSON.parse(lines[1]).id]; }),
  "wrong hash": withLine(3, (e) => { e.hash = "0000000000000000"; }),
  "md is not a string": withLine(3, (e) => { e.md = 5; }),
  "dead link": withLine(3, (e) => { e.md = "See [there](#nowhere)."; rehash(e); e.characters = [...e.md].length; }),
  "duplicate id": withLine(4, (e) => { e.id = JSON.parse(lines[3]).id; }),
  "meta is not an object": withLine(3, (e) => { e.meta = "x"; }),
};

const names = Object.keys(cases);
names.forEach((name, i) => fs.writeFileSync(path.join(TMP, "case" + i + ".fmjl"), cases[name], "utf8"));
const script = "import fmjl, json, sys\n" +
  "print(json.dumps([fmjl.check(p) for p in sys.argv[1:]]))";
const files = names.map((_, i) => path.join(TMP, "case" + i + ".fmjl"));
const pyResults = JSON.parse(execFileSync("python", ["-c", script].concat(files), { encoding: "utf8", cwd: ROOT }));

names.forEach((name, i) => {
  const py = [...new Set(pyResults[i].map((s) => Number(s.split(":")[0].slice(5))))].sort((a, b) => a - b);
  const js = [...new Set(validate(cases[name], TMP).map((p) => p.line + 1))].sort((a, b) => a - b);
  const expectErrors = name !== "repository file";
  if (String(py) === String(js) && (js.length > 0) === expectErrors) {
    console.log("ok    " + name + "  (lines " + (js.join(", ") || "none") + ")");
  } else {
    failures += 1;
    console.log("FAIL  " + name);
    console.log("  py: " + JSON.stringify(pyResults[i]));
    console.log("  js: " + JSON.stringify(validate(cases[name], TMP).map((p) => (p.line + 1) + ": " + p.message)));
  }
});

fs.rmSync(TMP, { recursive: true, force: true });
if (failures) {
  console.log("FAILED: " + failures);
  process.exit(1);
}
console.log("PASSED: the live checker flags the same lines as fmjl check");
