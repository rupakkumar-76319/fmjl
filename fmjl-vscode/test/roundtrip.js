"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const conv = require("../src/converter.js");

const ROOT = path.resolve(__dirname, "..", "..");
const TOOL = ["-m", "fmjl"];
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "fmjl-test-"));
let failures = 0;

function python(args) {
  try {
    return execFileSync("python", TOOL.concat(args), { encoding: "utf8", cwd: ROOT });
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

const shortcut = "| Name | Score | < |\n| --- | --- | --- |\n| ^ | Math | AI |\n| A & B | 9 | x\\|y |";
const built = conv.shortcutToHtml([["Name", "Score", "<"], ["^", "Math", "AI"], ["A & B", "9", "x\\|y"]]);
same("merged-cell shortcut builds the canonical HTML", built,
  "<table>\n<tr><th rowspan=\"2\">Name</th><th colspan=\"2\">Score</th></tr>\n" +
  "<tr><td>Math</td><td>AI</td></tr>\n<tr><td>A &amp; B</td><td>9</td><td>x|y</td></tr>\n</table>");
const scRows = conv.importMd("---\ndoc: sc\n---\n\n" + shortcut + "\n", { doc: "sc" });
same("merged-cell shortcut round-trips through the authoring form",
  conv.exportMd(scRows).split("\n").slice(-6, -1).join("\n"), "<!-- e1 -->\n" + shortcut);
const scWarn = [];
conv.importMd("---\ndoc: sc\n---\n\nName | Age\nRupak | 20\n", { doc: "sc", warnings: scWarn });
same("a table without separator row gives one warning", String(scWarn.length), "1");

const noteValues = ["0.9", ".5", "1", "0", "1.0", "1e-2", "1e-5", "1e-7", "0.000001", "2.5e-10", "0.30000000000000004",
  "0x10", "1_0", "", "nan", "inf", "1e999", "abc", "5", "-1", "+0.5", "-0", "1e22", "\u0663"];
const noteScript = "import json, sys\nimport fmjl\nout = []\n" +
  "for v in json.loads(sys.stdin.read()):\n" +
  "    try:\n        out.append(fmjl.dumps(fmjl.import_md('<!-- confidence=' + v + ' -->\\nHello', doc='t')[1]))\n" +
  "    except ValueError as e:\n        out.append(str(e))\n" +
  "print(json.dumps(out))\n";
const pyNotes = JSON.parse(execFileSync("python", ["-X", "utf8", "-c", noteScript],
  { encoding: "utf8", cwd: ROOT, input: JSON.stringify(noteValues) }));
noteValues.forEach((v, i) => {
  let js;
  try {
    js = conv.dumps(conv.importMd("<!-- confidence=" + v + " -->\nHello", { doc: "t" })[1]);
    JSON.parse(js);
  } catch (e) {
    js = e.message;
  }
  same("confidence=" + JSON.stringify(v) + " matches Python", js, pyNotes[i].replace(/^line \d+: /, "line 1: "));
});

const oddChars = ["\x0b", "\x0c", "\x1c", "\x1f", "\x85", "\xa0", "\u2003", "\u2028", "\u2029", "\u3000", "\ufeff"];
const oddTemplates = ["<!-- e1{c}type=paragraph -->\nHello", "<!--{c}e1{c}-->\nHello", "<!-- e1 -->{c}\nHello",
  "Hello{c}\n\nNext", "One\n{c}\nTwo", "# Title{c}\n\nText", "## {c} #{c}Text", "- a{c}\n- b",
  "| a{c} | b |\n|---|---|\n| 1 | {c}2 |", "---\ntitle: My{c}\n---\n\nText", "<table{c}><tr><td>a</td></tr></table>"];
const oddInputs = ["\u0663. item", "\u096a) item"];
for (const t of oddTemplates) for (const c of oddChars) oddInputs.push(t.split("{c}").join(c));
const oddScript = "import json, sys\nimport fmjl\nout = []\n" +
  "for md in json.loads(sys.stdin.read()):\n" +
  "    try:\n        rows = fmjl.import_md(md, doc='t', source='t.md')\n        rows[0].pop('created', None)\n" +
  "        out.append(''.join(fmjl.dumps(r) + '\\n' for r in rows) + fmjl.export_md(rows))\n" +
  "    except ValueError:\n        out.append('rejected')\n" +
  "print(json.dumps(out))\n";
const pyOdd = JSON.parse(execFileSync("python", ["-X", "utf8", "-c", oddScript],
  { encoding: "utf8", cwd: ROOT, input: JSON.stringify(oddInputs) }));
oddInputs.forEach((md, i) => {
  let js;
  try {
    const rows = conv.importMd(md, { doc: "t", source: "t.md" });
    delete rows[0].created;
    js = rows.map((r) => conv.dumps(r) + "\n").join("") + conv.exportMd(rows);
  } catch (e) {
    js = "rejected";
  }
  same("unusual characters " + i + " match Python", js, pyOdd[i]);
});

fs.rmSync(TMP, { recursive: true, force: true });
if (failures) {
  console.log("FAILED: " + failures);
  process.exit(1);
}
console.log("PASSED: all conversions match the Python package");
