"use strict";
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const { validate } = require("./validator.js");
const conv = require("./converter.js");

const SELECTOR = { language: "fmjl" };
const ID_WORD = /[a-z0-9_-]+#e[1-9][0-9]*/;
const ID_NOTE = /^\s*<!--\s*(group\s+)?e[1-9][0-9]*(\s|-->)/m;
const FILLABLE = /\(run: fmjl fill\)|empty line|\\r\\n|must end with a newline/;
const ICONS = {
  heading: vscode.SymbolKind.Namespace, group: vscode.SymbolKind.Module, table: vscode.SymbolKind.Struct,
  image: vscode.SymbolKind.File, formula: vscode.SymbolKind.Number, code: vscode.SymbolKind.Function,
};

let diagnostics;
const timers = new Map();
const indexes = new WeakMap();

function toDiagnostics(document, problems) {
  return problems.map((p) => {
    const lineLen = p.line < document.lineCount ? document.lineAt(p.line).text.length : 0;
    const start = Math.min(p.start, Math.max(lineLen - 1, 0));
    const end = Math.min(p.end, lineLen) || lineLen;
    const range = new vscode.Range(p.line, start, p.line, Math.max(end, start + 1));
    const d = new vscode.Diagnostic(range, p.message, vscode.DiagnosticSeverity.Error);
    d.source = "fmjl";
    return d;
  });
}

function baseOf(document) {
  return document.uri.scheme === "file" ? path.dirname(document.uri.fsPath) : null;
}

function bomOnDisk(document) {
  if (document.uri.scheme !== "file") return false;
  try {
    const fd = fs.openSync(document.uri.fsPath, "r");
    const buf = Buffer.alloc(3);
    const n = fs.readSync(fd, buf, 0, 3, 0);
    fs.closeSync(fd);
    return n === 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf;
  } catch (e) {
    return false;
  }
}

function refresh(document) {
  if (document.languageId !== "fmjl") return;
  const problems = validate(document.getText(),baseOf(document), { bom: bomOnDisk(document) });
  diagnostics.set(document.uri, toDiagnostics(document, problems));
  return problems;
}

function refreshSoon(document) {
  const key = document.uri.toString();
  clearTimeout(timers.get(key));
  timers.set(key, setTimeout(() => { timers.delete(key); refresh(document); }, 300));
}

function indexOf(document) {
  const cached = indexes.get(document);
  if (cached && cached.version === document.version) return cached;
  const rows = [];
  const byId = new Map();
  for (let i = 0; i < document.lineCount; i++) {
    const text = document.lineAt(i).text;
    if (!text.trim()) continue;
    let obj;
    try {
      obj = JSON.parse(text);
    } catch (e) {
      continue;
    }
    if (obj === null || typeof obj !== "object" || Array.isArray(obj)) continue;
    const row = { line: i, obj: obj };
    rows.push(row);
    if (typeof obj.id === "string") byId.set(obj.id, row);
  }
  const index = { version: document.version, rows: rows, byId: byId };
  indexes.set(document, index);
  return index;
}

function idAt(document, position) {
  const range = document.getWordRangeAtPosition(position, ID_WORD);
  return range ? { id: document.getText(range), range: range } : null;
}

function shortText(md, max) {
  const flat = md.replace(/^#{1,6}\s+/, "").replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max - 1) + "…" : flat;
}

function symbolName(e) {
  const md = typeof e.md === "string" ? e.md : "";
  let name = "";
  if (e.type === "table") name = (md.split("\n")[0] || "").split(/(?<!\\)\|/).map((c) => c.trim()).filter(Boolean).join(", ");
  else if (e.type === "code") {
    const lang = /^ {0,3}(?:`{3,}|~{3,})[ \t]*(\S+)/.exec(md);
    name = lang ? "code (" + lang[1] + ")" : "code";
  }
  else if (e.type === "formula") name = typeof e.latex === "string" ? e.latex : md;
  else if (e.type === "image") name = (/^!\[([\s\S]*?)\]/.exec(md) || [])[1] || e.file || "";
  else name = md;
  return shortText(name, 80) || e.type;
}

function where(e) {
  if (Number.isInteger(e.page)) return "page " + (e.page + 1);
  if (Array.isArray(e.pages) && e.pages.every(Number.isInteger)) return "pages " + e.pages.map((p) => p + 1).join(", ");
  return "";
}

function describe(e, document) {
  const kind = e.type + (e.subtype ? " (" + e.subtype + ")" : "");
  const parts = ["**" + kind + "**", "`" + e.id + "`"];
  if (e.label) parts.push("label `" + e.label + "`");
  const page = where(e);
  if (page) parts.push(page);
  const md = new vscode.MarkdownString(parts.join(" · ") + "\n\n---\n\n");
  md.baseUri = document.uri;
  if (e.type === "formula" && typeof e.latex === "string") md.appendCodeblock(e.latex, "latex");
  else if (typeof e.md === "string") md.appendMarkdown(e.md);
  return md;
}

const hoverProvider = {
  provideHover(document, position) {
    const index = indexOf(document);
    const hit = idAt(document, position);
    if (hit) {
      const target = index.byId.get(hit.id);
      if (!target) return new vscode.Hover("No element has the id `" + hit.id + "`.", hit.range);
      return new vscode.Hover(describe(target.obj, document), hit.range);
    }
    const row = index.rows.find((r) => r.line === position.line);
    if (!row || row.obj.type === "document" || typeof row.obj.id !== "string") return null;
    return new vscode.Hover(describe(row.obj, document));
  },
};

const definitionProvider = {
  provideDefinition(document, position) {
    const hit = idAt(document, position);
    if (!hit) return null;
    const target = indexOf(document).byId.get(hit.id);
    if (!target) return null;
    const col = document.lineAt(target.line).text.indexOf('"' + hit.id + '"');
    return new vscode.Location(document.uri, new vscode.Position(target.line, Math.max(col + 1, 0)));
  },
};

const referenceProvider = {
  provideReferences(document, position, context) {
    const hit = idAt(document, position);
    if (!hit) return [];
    const needle = '"' + hit.id + '"';
    const out = [];
    for (let i = 0; i < document.lineCount; i++) {
      const text = document.lineAt(i).text;
      let k = text.indexOf(needle);
      while (k >= 0) {
        const isDeclaration = text.slice(Math.max(0, k - 5), k) === '"id":';
        if (!isDeclaration || context.includeDeclaration) {
          out.push(new vscode.Location(document.uri, new vscode.Range(i, k + 1, i, k + needle.length - 1)));
        }
        k = text.indexOf(needle, k + needle.length);
      }
    }
    return out;
  },
};

const symbolProvider = {
  provideDocumentSymbols(document) {
    const index = indexOf(document);
    const symbols = new Map();
    const roots = [];
    for (const row of index.rows) {
      const e = row.obj;
      if (e.type === "document" || typeof e.id !== "string" || !(e.type in ICONS)) continue;
      const lineRange = document.lineAt(row.line).range;
      const name = symbolName(e);
      const detail = [e.type === "heading" ? "" : e.type, where(e)].filter(Boolean).join(" · ");
      const symbol = new vscode.DocumentSymbol(name, detail, ICONS[e.type], lineRange, lineRange);
      symbols.set(e.id, symbol);
      const up = typeof e.parent === "string" ? symbols.get(e.parent) : null;
      if (up) up.children.push(symbol);
      else roots.push(symbol);
    }
    for (const row of index.rows) {
      const end = document.lineAt(row.line).range.end;
      const seen = new Set();
      for (let p = row.obj.parent; typeof p === "string" && index.byId.has(p) && !seen.has(p);
        p = index.byId.get(p).obj.parent) {
        seen.add(p);
        const owner = symbols.get(p);
        if (owner && owner.range.end.isBefore(end)) owner.range = new vscode.Range(owner.range.start, end);
      }
    }
    return roots;
  },
};

const codeActionProvider = {
  provideCodeActions(document, range, context) {
    const fixable = context.diagnostics.filter((d) => d.source === "fmjl" && FILLABLE.test(d.message));
    if (!fixable.length) return [];
    const action = new vscode.CodeAction("Fix with FMJL: Fill (hashes, counts, canonical Markdown)", vscode.CodeActionKind.QuickFix);
    action.command = { command: "fmjl.fill", title: "FMJL: Fill", arguments: [document.uri] };
    action.diagnostics = fixable;
    action.isPreferred = true;
    return [action];
  },
};

async function fill(uri) {
  const editor = uri
    ? await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(uri))
    : vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "fmjl") {
    vscode.window.showInformationMessage("Open an .fmjl file first.");
    return;
  }
  const document = editor.document;
  let filled;
  try {
    filled = conv.writeRows(conv.fill(conv.readRows(document.getText()), undefined, baseOf(document) || undefined));
  } catch (e) {
    vscode.window.showErrorMessage("FMJL: cannot fill: " + e.message);
    return;
  }
  const whole = new vscode.Range(0, 0, document.lineCount, 0);
  const sameText = filled === document.getText();
  if (sameText && document.eol === vscode.EndOfLine.LF) {
    vscode.window.showInformationMessage("FMJL: nothing to fill");
  } else {
    await editor.edit((b) => {
      if (!sameText) b.replace(whole, filled);
      b.setEndOfLine(vscode.EndOfLine.LF);
    });
  }
  const problems = refresh(document) || [];
  if (problems.length) {
    vscode.window.showWarningMessage("FMJL: filled; " + problems.length + " problems need a hand edit - see the Problems panel");
  } else if (!sameText) {
    vscode.window.showInformationMessage("FMJL: filled, PASSED (0 errors). Existing ids were kept.");
  }
}

async function saveIfOpen(uri) {
  const open = vscode.workspace.textDocuments.find((d) => d.uri.toString() === uri.toString());
  if (open && open.isDirty) await open.save();
}

async function fileFor(uri, ext) {
  if (!uri) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showInformationMessage("Open a " + ext + " file first.");
      return null;
    }
    uri = editor.document.uri;
  }
  if (uri.scheme !== "file" || !uri.fsPath.toLowerCase().endsWith(ext)) {
    vscode.window.showInformationMessage("FMJL: this command needs a " + ext + " file.");
    return null;
  }
  await saveIfOpen(uri);
  return uri.fsPath;
}

async function confirm(message, button) {
  return (await vscode.window.showWarningMessage(message, { modal: true }, button)) === button;
}

function report(outFile, problems, warnings) {
  const name = path.basename(outFile);
  if (warnings && warnings.length) {
    vscode.window.showWarningMessage("FMJL: " + warnings.join("; "));
  }
  if (problems.length === 0) {
    vscode.window.showInformationMessage("FMJL: wrote " + name + ", PASSED (0 errors)");
  } else {
    vscode.window.showWarningMessage("FMJL: wrote " + name + ", FAILED (" + problems.length + " errors) - see the Problems panel");
    vscode.commands.executeCommand("workbench.actions.view.problems");
  }
}

async function toFmjl(uri) {
  const file = await fileFor(uri, ".md");
  if (!file) return;
  try {
    const text = fs.readFileSync(file, "utf8");
    const stem = path.basename(file, path.extname(file));
    const dir = path.dirname(file);
    const out = path.join(dir, stem + ".fmjl");
    if (fs.existsSync(out) && !ID_NOTE.test(text) &&
        !(await confirm(path.basename(out) + " already exists, but " + path.basename(file) +
          " has no <!-- e7 --> id notes, so every element gets a fresh id and links to the old ids break. " +
          "To keep ids, convert " + path.basename(out) + " to Markdown first and edit that. Replace it anyway?", "Replace"))) {
      return;
    }
    await saveIfOpen(vscode.Uri.file(out));
    const warnings = [];
    const rows = conv.importMd(text, { doc: conv.docName(stem), source: path.basename(file), base: dir, warnings: warnings });
    fs.writeFileSync(out, conv.writeRows(rows), "utf8");
    const document = await vscode.workspace.openTextDocument(out);
    await vscode.window.showTextDocument(document, { preview: false });
    report(out, refresh(document) || [], warnings);
  } catch (e) {
    vscode.window.showErrorMessage("FMJL: " + e.message);
  }
}

async function toMd(uri) {
  const file = await fileFor(uri, ".fmjl");
  if (!file) return;
  try {
    const rows = conv.readRows(fs.readFileSync(file, "utf8"));
    const out = path.join(path.dirname(file), path.basename(file, path.extname(file)) + ".md");
    if (fs.existsSync(out) && fs.statSync(out).mtimeMs > fs.statSync(file).mtimeMs &&
        !(await confirm(path.basename(out) + " was changed after " + path.basename(file) +
          " was written. Converting replaces it, and those changes are lost. Replace it?", "Replace"))) {
      return;
    }
    fs.writeFileSync(out, conv.exportMd(rows), "utf8");
    const document = await vscode.workspace.openTextDocument(out);
    await vscode.window.showTextDocument(document, { preview: false });
    vscode.window.showInformationMessage("FMJL: wrote " + path.basename(out) + "; ids are kept, edit and convert back");
  } catch (e) {
    vscode.window.showErrorMessage("FMJL: " + e.message);
  }
}

function check() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "fmjl") {
    vscode.window.showInformationMessage("Open an .fmjl file first.");
    return;
  }
  const problems = refresh(editor.document) || [];
  if (problems.length === 0) {
    vscode.window.showInformationMessage("FMJL: PASSED ✓ (0 errors)");
  } else {
    vscode.window.showWarningMessage("FMJL: FAILED (" + problems.length + " errors) - see the Problems panel");
    vscode.commands.executeCommand("workbench.actions.view.problems");
  }
}

function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("fmjl");
  context.subscriptions.push(diagnostics);

  vscode.workspace.textDocuments.forEach(refresh);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(refresh),
    vscode.workspace.onDidSaveTextDocument(refresh),
    vscode.workspace.onDidChangeTextDocument((e) => refreshSoon(e.document)),
    vscode.workspace.onDidCloseTextDocument((d) => diagnostics.delete(d.uri)),
    vscode.languages.registerHoverProvider(SELECTOR, hoverProvider),
    vscode.languages.registerDefinitionProvider(SELECTOR, definitionProvider),
    vscode.languages.registerReferenceProvider(SELECTOR, referenceProvider),
    vscode.languages.registerDocumentSymbolProvider(SELECTOR, symbolProvider),
    vscode.languages.registerCodeActionsProvider(SELECTOR, codeActionProvider,
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }),
    vscode.commands.registerCommand("fmjl.check", check),
    vscode.commands.registerCommand("fmjl.fill", fill),
    vscode.commands.registerCommand("fmjl.toFmjl", toFmjl),
    vscode.commands.registerCommand("fmjl.toMd", toMd)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
