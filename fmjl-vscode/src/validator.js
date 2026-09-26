// FMJL validator for the VS Code extension - rulebook version 0.3.
// Pure JavaScript, no dependencies, so the extension works without Python.
// The Python tool `fmjl.py check` remains the final judge; this catches the same
// core errors live while typing (all except canonical-Markdown rewriting).

"use strict";
const crypto = require("crypto");

const TYPES = ["heading", "paragraph", "list", "table", "formula", "code", "image", "caption",
  "footnote", "form_field", "annotation", "redaction", "noise", "message", "utterance",
  "record", "citation", "quote", "toc", "group"];
const SUBTYPES = {
  image: ["logo", "stamp", "signature", "chart", "diagram", "photo", "qr_code", "barcode"],
  noise: ["header", "footer", "watermark", "page_number"],
  group: ["slide", "sidebar", "figure", "box", "sheet", "thread"],
};
const REQUIRED_HEADER = ["type", "version", "doc", "source", "sha256", "protection", "signed",
  "converter", "structure", "elements", "created", "lang", "access"];
const REQUIRED_ELEMENT = ["id", "hash", "type", "parent", "characters", "md"];
const ID_RE = /^[a-z0-9_-]+#e[1-9][0-9]*$/;
const LANG_RE = /^[a-z]{2,3}(-[A-Za-z0-9]+)*$/;

function elementHash(type, md) {
  return crypto.createHash("sha256").update(type + "\n" + md, "utf8").digest("hex").slice(0, 16);
}

function isInt(v) { return Number.isInteger(v); }
function isStr(v) { return typeof v === "string"; }

// Returns [{line, message, start, end}] - line is 0-based for VS Code.
function validate(text) {
  const problems = [];
  const add = (line, message, start, end) =>
    problems.push({ line, message, start: start || 0, end: end == null ? 400 : end });

  const rawLines = text.split("\n");
  const rows = []; // {line, obj}
  rawLines.forEach((raw, i) => {
    const last = i === rawLines.length - 1;
    if (raw === "" && last) return;               // final newline is fine
    if (raw.trim() === "") { add(i, "empty line (not allowed; delete it)"); return; }
    try {
      const obj = JSON.parse(raw);
      if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
        add(i, "must be one JSON object {...}");
      } else rows.push({ line: i, obj: obj, raw: raw });
    } catch (e) {
      const m = /position (\d+)/.exec(e.message);
      const col = m ? Number(m[1]) : 0;
      add(i, "not valid JSON: " + e.message, Math.max(0, col - 1), col + 1);
    }
  });
  if (!rows.length) { add(0, "file has no valid lines"); return problems; }

  const col = (row, field) => {           // underline the field name when possible
    const k = row.raw.indexOf('"' + field + '"');
    return k >= 0 ? [k, k + field.length + 2] : [0, Math.min(row.raw.length, 400)];
  };
  const addF = (row, field, msg) => { const c = col(row, field); add(row.line, msg, c[0], c[1]); };

  // ---- header ----
  const head = rows[0];
  const h = head.obj;
  if (head.line !== 0 || h.type !== "document") {
    add(head.line, 'line 1 must be the header line with "type":"document"');
  }
  for (const f of REQUIRED_HEADER) if (!(f in h)) add(head.line, "header is missing '" + f + "' (run: python fmjl.py fill)");
  if (isStr(h.version) && !/^[0-9]+\.[0-9]+$/.test(h.version)) addF(head, "version", "version must look like 0.3");
  if (isStr(h.doc) && !/^[a-z0-9_-]+$/.test(h.doc)) addF(head, "doc", "doc uses lowercase letters, digits, _ or -");
  if (isStr(h.sha256) && !/^[0-9a-f]{64}$/.test(h.sha256)) addF(head, "sha256", "sha256 must be 64 hex characters");
  if ("protection" in h && !["none", "password", "certificate", "drm"].includes(h.protection))
    addF(head, "protection", "protection must be none, password, certificate or drm");
  if ("signed" in h && typeof h.signed !== "boolean") addF(head, "signed", "signed must be true or false");
  if ("structure" in h && typeof h.structure !== "boolean") addF(head, "structure", "structure must be true or false");
  if ("elements" in h && h.elements !== null && !(isInt(h.elements) && h.elements >= 0))
    addF(head, "elements", "elements must be a whole number (or null while writing)");
  if (isStr(h.lang) && !LANG_RE.test(h.lang)) addF(head, "lang", "lang must be a language code like en, hi, as, bn");
  if ("access" in h && !(Array.isArray(h.access) && h.access.length && h.access.every(isStr)))
    addF(head, "access", "access must be a list of group names");
  if ("last_id" in h && !(isInt(h.last_id) && h.last_id >= 0)) addF(head, "last_id", "last_id must be a whole number");

  // ---- elements ----
  const els = rows.slice(1);
  const byId = new Map(), lineOf = new Map(), pos = new Map(), labels = new Map();
  els.forEach((row, index) => {
    const e = row.obj;
    if (e.type === "document") { add(row.line, "only line 1 may be a header"); return; }
    for (const f of REQUIRED_ELEMENT) if (!(f in e)) add(row.line, "missing '" + f + "' (run: python fmjl.py fill)");
    if (isStr(e.id)) {
      if (!ID_RE.test(e.id)) addF(row, "id", "id must look like " + (h.doc || "doc") + "#e7");
      else if (isStr(h.doc) && !e.id.startsWith(h.doc + "#")) addF(row, "id", "id must start with " + h.doc + "#");
      if (byId.has(e.id)) addF(row, "id", "id " + e.id + " is used twice");
      byId.set(e.id, e); lineOf.set(e.id, row.line); pos.set(e.id, index);
      if (isStr(h.doc) && isInt(h.last_id)) {
        const n = Number((e.id.split("#e")[1]) || 0);
        if (n > h.last_id) addF(row, "id", "id number is higher than last_id in the header");
      }
    }
    if ("type" in e && !TYPES.includes(e.type)) addF(row, "type", "'" + e.type + "' is not one of the 20 types");
    if ("subtype" in e) {
      if (!SUBTYPES[e.type]) addF(row, "subtype", "subtype is only for image, noise and group");
      else if (!SUBTYPES[e.type].includes(e.subtype))
        addF(row, "subtype", "subtype for " + e.type + " must be one of: " + SUBTYPES[e.type].join(", "));
    }
    if (e.type === "heading" && !isInt(e.level)) addF(row, "type", "a heading needs \"level\":1..6");
    if ("level" in e && (e.type !== "heading" || !isInt(e.level) || e.level < 1 || e.level > 6))
      addF(row, "level", "level (1..6) is only for headings");
    if (e.type === "formula" && !isStr(e.latex)) addF(row, "type", "a formula needs \"latex\"");
    if (e.type === "image" && !isStr(e.file)) addF(row, "type", "an image needs \"file\":\"images/...\"");
    if (e.type === "noise" && !isStr(e.subtype)) addF(row, "type", "noise needs a subtype");
    if (e.type === "group" && !isStr(e.subtype)) addF(row, "type", "a group needs a subtype");
    if ("html" in e && e.type !== "table") addF(row, "html", "html is only for tables");
    if ("latex" in e && e.type !== "formula") addF(row, "latex", "latex is only for formulas");
    if ("file" in e) {
      if (e.type !== "image") addF(row, "file", "file is only for images");
      else if (!/^images\/[^/]+\.(png|webp|jpg|jpeg|svg)$/.test(e.file))
        addF(row, "file", "file must be images/<name>.png|webp|jpg|jpeg|svg");
    }
    if ("label" in e && !(isStr(e.label) && /^[a-z][a-z0-9_-]*$/.test(e.label)))
      addF(row, "label", "label uses lowercase letters, digits, _ or -");
    if (isStr(e.label)) {
      if (labels.has(e.label)) addF(row, "label", "label " + e.label + " is used twice");
      labels.set(e.label, e.id);
    }
    if ("page" in e && "pages" in e) addF(row, "pages", "use page or pages, never both");
    if ("page" in e && !(isInt(e.page) && e.page >= 0)) addF(row, "page", "page is a whole number from 0");
    if ("pages" in e && !(Array.isArray(e.pages) && e.pages.length >= 2 && e.pages.every(p => isInt(p) && p >= 0)))
      addF(row, "pages", "pages is a list of at least two page numbers");
    if ("bbox" in e) {
      if (!("page" in e)) addF(row, "bbox", "bbox is allowed only together with page");
      if (!(Array.isArray(e.bbox) && e.bbox.length === 4 && e.bbox.every(v => isInt(v) && v >= 0 && v <= 1000)))
        addF(row, "bbox", "bbox is [left, top, right, bottom], whole numbers 0..1000");
    }
    if ("confidence" in e && !(typeof e.confidence === "number" && e.confidence >= 0 && e.confidence <= 1))
      addF(row, "confidence", "confidence is a number from 0 to 1");
    if ("lang" in e && !(isStr(e.lang) && LANG_RE.test(e.lang))) addF(row, "lang", "lang must be a language code");
    if ("access" in e && !(Array.isArray(e.access) && e.access.length && e.access.every(isStr)))
      addF(row, "access", "access must be a list of group names");
    if (Array.isArray(e.reference) && e.reference.length === 1)
      addF(row, "reference", "a single reference must be a string, not a list");
    if (isStr(e.md) && isStr(e.type)) {
      for (const field of ["md", "latex", "html"]) {
        const v = e[field];
        if (isStr(v) && [...v].some(c => c.charCodeAt(0) < 32 && c !== "\n" && c !== "\t"))
          addF(row, field, field + " has a hidden control character - write backslashes as \\\\ (e.g. \\\\frac)");
      }
      if (isStr(e.hash) && e.hash !== elementHash(e.type, e.md))
        addF(row, "hash", "hash is wrong (run: python fmjl.py fill)");
      if (isInt(e.characters) && e.characters !== [...e.md].length && e.characters !== e.md.length)
        addF(row, "characters", "characters should be " + e.md.length);
      if (e.type === "heading" && isInt(e.level)) {
        const m = /^(#{1,6})(?:[ \t]|$)/.exec(e.md);
        if (!m || m[1].length !== e.level) addF(row, "level", "level " + e.level + " does not match the #'s in md");
      }
    }
    if (isStr(e.hash) && !/^[0-9a-f]{16}$/.test(e.hash)) addF(row, "hash", "hash must be 16 hex characters");
  });

  // ---- cross references ----
  els.forEach((row, index) => {
    const e = row.obj;
    if (e.type === "document") return;
    const p = e.parent;
    if (p !== null && p !== undefined) {
      if (!byId.has(p)) addF(row, "parent", "parent " + p + " does not exist");
      else if (pos.get(p) >= index) addF(row, "parent", "parent must come before the element");
      else {
        const par = byId.get(p);
        if (par.type !== "heading" && par.type !== "group") addF(row, "parent", "parent must be a heading or a group");
        else if (e.type === "heading" && par.type === "heading" && (par.level || 0) >= (e.level || 0))
          addF(row, "parent", "a heading's parent must be a heading with a smaller level");
      }
    }
    const refs = isStr(e.reference) ? [e.reference] : Array.isArray(e.reference) ? e.reference : [];
    for (const r of refs) if (!byId.has(r)) addF(row, "reference", "reference " + r + " does not exist");
    if (isStr(e.continues)) {
      if (!byId.has(e.continues) || pos.get(e.continues) >= index)
        addF(row, "continues", "continues must point to an earlier element");
      else if (byId.get(e.continues).type !== e.type)
        addF(row, "continues", "continues must point to an element of the same type");
    }
    if (isStr(e.md) && e.type !== "code") {
      const noCode = e.md.replace(/^ {0,3}(`{3,}|~{3,})[\s\S]*?^ {0,3}\1/gm, "").replace(/(`+)[\s\S]*?\1/g, "");
      for (const m of noCode.matchAll(/\]\(#([a-z0-9_-]+)\)/g)) {
        const t = m[1];
        if (!byId.has((h.doc || "") + "#" + t) && !labels.has(t))
          add(row.line, "link to #" + t + " points to no element or label");
      }
    }
  });
  if (isInt(h.elements)) {
    const n = els.filter(r => r.obj.type !== "document").length;
    if (h.elements !== n) addF(head, "elements", "elements says " + h.elements + " but the file has " + n);
  }
  return problems;
}

module.exports = { validate: validate, elementHash: elementHash, TYPES: TYPES };
