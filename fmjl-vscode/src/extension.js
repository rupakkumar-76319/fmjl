"use strict";
const vscode = require("vscode");
const { validate } = require("./validator.js");

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

function refresh(document) {
  if (document.languageId !== "fmjl") return;
  const problems = validate(document.getText());
  diagnostics.set(document.uri, toDiagnostics(document, problems));
  return problems;
}

function refreshSoon(document) {
  const key = document.uri.toString();
  clearTimeout(timers.get(key));
  timers.set(key, setTimeout(() => refresh(document), 300));
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
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
