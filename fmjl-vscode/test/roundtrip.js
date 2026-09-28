"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const conv = require("../src/converter.js");

const ROOT = path.resolve(__dirname, "..", "..");
const TOOL = path.join(ROOT, "fmjl.py");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "fmjl-test-"));
let failures = 0;

function python(args) {
  try {
    return execFileSync("python", [TOOL].concat(args), { encoding: "utf8" });
  } catch (e) {
    if (e.status === 1 && e.stdout && e.stdout.startsWith("wrote ")) return e.stdout;
    throw e;
  }
}

function same(name, a, b) {
  if (a === b) {
    console.log("ok    " + name);
    return;
  }
  failures += 1;
  const la = a.split("\n");
  const lb = b.split("\n");
  let i = 0;
  while (i < la.length && i < lb.length && la[i] === lb[i]) i += 1;
  console.log("FAIL  " + name + " (first difference at line " + (i + 1) + ")");
  console.log("  js: " + JSON.stringify(la[i] || ""));
  console.log("  py: " + JSON.stringify(lb[i] || ""));
}

function stripCreated(text) {
  return text.replace(/"created":"[^"]+"/, "\"created\":\"\"");
}

function listFmjl(dir) {
  return fs.readdirSync(dir).filter((f) => f.endsWith(".fmjl")).map((f) => path.join(dir, f));
}

const files = listFmjl(path.join(ROOT, "examples")).concat(listFmjl(path.join(ROOT, "rulebook")));
for (const file of files) {
  const label = path.relative(ROOT, file);
  const original = fs.readFileSync(file, "utf8");
  const rows = conv.readRows(original);

  const jsMd = conv.exportMd(rows);
  const pyMdFile = path.join(TMP, path.basename(file, ".fmjl") + ".py.md");
  python(["md", file, "-o", pyMdFile]);
  same(label + "  .fmjl -> .md matches Python", jsMd, fs.readFileSync(pyMdFile, "utf8"));

  const back = conv.importMd(jsMd, { doc: rows[0].doc, source: rows[0].source, base: path.dirname(file) });
  same(label + "  .fmjl -> .md -> .fmjl gives the same bytes", conv.writeRows(back), original);
}

const authored = fs.readdirSync(path.join(ROOT, "examples")).filter((f) => f.endsWith(".md"));
for (const name of authored) {
  const file = path.join(ROOT, "examples", name);
  const stem = path.basename(name, ".md");
  const text = fs.readFileSync(file, "utf8");
  const rows = conv.importMd(text, { doc: conv.docName(stem), source: name, base: path.dirname(file) });
  const pyOut = path.join(TMP, stem + ".py.fmjl");
  python(["new", file, "-o", pyOut]);
  same("examples/" + name + "  .md -> .fmjl matches Python", stripCreated(conv.writeRows(rows)),
    stripCreated(fs.readFileSync(pyOut, "utf8")));
}

const html = "<table>\n<tr><th rowspan=\"2\">Name</th><th colspan=\"2\">Score</th></tr>\n" +
  "<tr><th>Math</th><th>AI</th></tr>\n<tr><td>A &amp; B</td><td>9</td><td>x|y</td></tr>\n</table>";
same("merged cells flatten like Python", conv.htmlTableToMd(html),
  "| Name | Score | Score |\n| --- | --- | --- |\n| Name | Math | AI |\n| A & B | 9 | x\\|y |");

fs.rmSync(TMP, { recursive: true, force: true });
if (failures) {
  console.log("FAILED: " + failures);
  process.exit(1);
}
console.log("PASSED: all conversions match fmjl.py");
