"use strict";
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");
const { validate } = require("./validator.js");
const conv = require("./converter.js");

let diagnostics;
const timers = new Map();

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

function refresh(document) {
  if (document.languageId !== "fmjl") return;
  const problems = validate(document.getText(), baseOf(document));
  diagnostics.set(document.uri, toDiagnostics(document, problems));
  return problems;
}

function refreshSoon(document) {
  const key = document.uri.toString();
  clearTimeout(timers.get(key));
  timers.set(key, setTimeout(() => refresh(document), 300));
}

async function fileFor(uri, ext) {
  if (!uri) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showInformationMessage("Open a " + ext + " file first.");
      return null;
    }
    if (editor.document.isDirty) await editor.document.save();
    uri = editor.document.uri;
  }
  if (uri.scheme !== "file" || !uri.fsPath.toLowerCase().endsWith(ext)) {
    vscode.window.showInformationMessage("FMJL: this command needs a " + ext + " file.");
    return null;
  }
  return uri.fsPath;
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
    const warnings = [];
    const rows = conv.importMd(text, { doc: conv.docName(stem), source: path.basename(file), base: dir, warnings: warnings });
    const out = path.join(dir, stem + ".fmjl");
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
    fs.writeFileSync(out, conv.exportMd(rows), "utf8");
    const document = await vscode.workspace.openTextDocument(out);
    await vscode.window.showTextDocument(document, { preview: false });
    vscode.window.showInformationMessage("FMJL: wrote " + path.basename(out) + "; ids are kept, edit and convert back");
  } catch (e) {
    vscode.window.showErrorMessage("FMJL: " + e.message);
  }
}

function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("fmjl");
  context.subscriptions.push(diagnostics);

  vscode.workspace.textDocuments.forEach(refresh);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(refresh),
    vscode.workspace.onDidChangeTextDocument((e) => refreshSoon(e.document)),
    vscode.workspace.onDidCloseTextDocument((d) => diagnostics.delete(d.uri)),
    vscode.commands.registerCommand("fmjl.check", () => {
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
    }),
    vscode.commands.registerCommand("fmjl.toFmjl", toFmjl),
    vscode.commands.registerCommand("fmjl.toMd", toMd)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
