"use strict";
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const VERSION = "0.4";
const CONVERTER = "fmjl 0.4";

const TYPES = ["heading", "paragraph", "list", "table", "formula", "code", "image", "caption",
  "footnote", "form_field", "annotation", "redaction", "noise", "message", "utterance",
  "record", "citation", "quote", "toc", "group"];
const HEADER_ORDER = ["type", "version", "doc", "source", "sha256", "protection", "signed", "converter",
  "structure", "elements", "created", "lang", "access", "title", "authors", "date",
  "summary", "last_id", "meta"];
const ELEMENT_ORDER = ["id", "hash", "type", "subtype", "level", "label", "parent", "page", "pages",
  "bbox", "characters", "reference", "continues", "confidence", "lang", "access",
  "html", "latex", "file", "meta", "md"];
const FRONT_ORDER = ["fmjl", "doc", "title", "authors", "date", "summary", "lang", "access", "source",
  "sha256", "protection", "signed", "converter", "created", "last_id", "meta"];
const NOTE_KEYS = ["type", "subtype", "label", "level", "page", "pages", "bbox", "confidence", "lang",
  "access", "reference", "continues", "parent", "file", "meta"];

const ID_RE = /^[a-z0-9_-]+#e[1-9][0-9]*$/;
const SHORT_ID_RE = /^e[1-9][0-9]*$/;
const HEADING_RE = /^(#{1,6})(?:[ \t]|$)/;
const FENCE_RE = /^ {0,3}(`{3,}|~{3,})/;
const IMAGE_RE = /^!\[([\s\S]*)\]\((\S+?)\)$/;
const NOTE_RE = /^\s*<!--\s*([\s\S]*?)\s*-->\s*$/;
const SEP_CELL_RE = /^:?-+:?$/;
const QUOTE_STARTS = "\"'[{#&*!|>%@`";

const FLOAT = Symbol("float");

function isStr(v) { return typeof v === "string"; }
function isInt(v) { return Number.isInteger(v); }
function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
function lstrip(s) { return s.replace(/^\s+/, ""); }
function rstrip(s) { return s.replace(/\s+$/, ""); }
function stripNl(s) { return s.replace(/^\n+/, "").replace(/\n+$/, ""); }
function chars(s) { return [...s].length; }

function pyNum(v, asFloat) {
  if (Number.isInteger(v)) return asFloat ? v + ".0" : String(v);
  return String(v);
}

function pyJson(v, compact, floats) {
  if (v === null || v === undefined) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return pyNum(v, floats);
  if (typeof v === "string") return JSON.stringify(v);
  const comma = compact ? "," : ", ";
  if (Array.isArray(v)) return "[" + v.map((x) => pyJson(x, compact, floats)).join(comma) + "]";
  const colon = compact ? ":" : ": ";
  return "{" + Object.keys(v).map((k) => JSON.stringify(k) + colon + pyJson(v[k], compact, floats)).join(comma) + "}";
}

function elementHash(type, md) {
  return crypto.createHash("sha256").update(type + "\n" + md, "utf8").digest("hex").slice(0, 16);
}

function idNumber(id) {
  const i = id.lastIndexOf("#e");
  return Number(id.slice(i + 2));
}

function shortId(id, doc) {
  return isStr(id) && id.startsWith(doc + "#") ? id.slice(doc.length + 1) : id;
}

function dumps(row) {
  const order = row.type === "document" ? HEADER_ORDER : ELEMENT_ORDER;
  const known = order.filter((k) => k in row);
  const extra = Object.keys(row).filter((k) => !order.includes(k) && !k.startsWith("_"));
  let keys;
  if (row.type !== "document" && known.length && known[known.length - 1] === "md") {
    keys = known.slice(0, -1).concat(extra, ["md"]);
  } else {
    keys = known.concat(extra);
  }
  const parts = keys.map((k) => JSON.stringify(k) + ":" + pyJson(row[k], true, k === "confidence" && row[FLOAT]));
  return "{" + parts.join(",") + "}";
}

function readRows(text) {
  const rows = [];
  const lines = text.split("\n");
  lines.forEach((line, idx) => {
    line = line.replace(/\r$/, "");
    if (!line.trim()) return;
    let obj;
    try {
      obj = JSON.parse(line);
    } catch (e) {
      throw new Error("line " + (idx + 1) + ": not valid JSON: " + e.message);
    }
    if (!isObj(obj)) throw new Error("line " + (idx + 1) + ": must be one JSON object");
    rows.push(obj);
  });
  if (!rows.length) throw new Error("line 1: file has no lines");
  return rows;
}

function writeRows(rows) {
  return rows.map((r) => dumps(r) + "\n").join("");
}

function splitRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  const cells = [];
  let cur = "";
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (c === "\\" && i + 1 < s.length && s[i + 1] === "|") {
      cur += "\\|";
      i += 2;
      continue;
    }
    if (c === "|") {
      cells.push(cur.trim());
      cur = "";
    } else {
      cur += c;
    }
    i += 1;
  }
  cells.push(cur.trim());
  return cells;
}

function pipeRow(cells) {
  return "| " + cells.join(" | ") + " |";
}

function sepCell(cell) {
  return (cell.startsWith(":") ? ":" : "") + "---" + (cell.endsWith(":") ? ":" : "");
}

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: "\"", apos: "'", nbsp: " " };

function unescapeHtml(s) {
  return s.replace(/&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/g, (m, body) => {
    if (body[0] === "#") {
      const hex = body[1] === "x" || body[1] === "X";
      const code = hex ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : m;
    }
    return body in ENTITIES ? ENTITIES[body] : m;
  });
}

function parseAttrs(s) {
  const out = {};
  const re = /([^\s=\/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    let val = null;
    if (m[2] !== undefined) val = m[2];
    else if (m[3] !== undefined) val = m[3];
    else if (m[4] !== undefined) val = m[4];
    out[m[1].toLowerCase()] = val === null ? null : unescapeHtml(val);
  }
  return out;
}

function tableGrid(html) {
  const rows = [];
  let row = null;
  let cell = null;
  let span = [1, 1];
  const re = /<!--[\s\S]*?-->|<\/?([a-zA-Z][a-zA-Z0-9]*)([^>]*)>|([^<]+)|</g;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (m[0].startsWith("<!--")) continue;
    if (m[1] !== undefined) {
      const tag = m[1].toLowerCase();
      const closing = m[0].startsWith("</");
      if (!closing) {
        if (tag === "tr") {
          row = [];
        } else if ((tag === "td" || tag === "th") && row !== null) {
          cell = [];
          const a = parseAttrs(m[2]);
          span = [parseInt(a.rowspan, 10) || 1, parseInt(a.colspan, 10) || 1];
        } else if (tag === "br" && cell !== null) {
          cell.push(" ");
        }
      } else if ((tag === "td" || tag === "th") && cell !== null) {
        const text = cell.join("").replace(/\s+/g, " ").trim().replace(/\|/g, "\\|");
        row.push([text, span]);
        cell = null;
      } else if (tag === "tr" && row !== null) {
        rows.push(row);
        row = null;
      }
    } else if (cell !== null) {
      cell.push(unescapeHtml(m[0]));
    }
  }
  const grid = [];
  const pending = new Map();
  rows.forEach((r, ri) => {
    const line = [];
    let c = 0;
    const cells = r.slice();
    while (cells.length || pending.has(ri + "," + c)) {
      const key = ri + "," + c;
      if (pending.has(key)) {
        line.push(pending.get(key));
        pending.delete(key);
        c += 1;
        continue;
      }
      const [text, [rs, cs]] = cells.shift();
      for (let dc = 0; dc < cs; dc++) {
        line.push(text);
        for (let dr = 1; dr < rs; dr++) pending.set((ri + dr) + "," + (c + dc), text);
      }
      c += cs;
    }
    grid.push(line);
  });
  const width = grid.reduce((w, l) => Math.max(w, l.length), 0);
  return grid.map((l) => l.concat(new Array(width - l.length).fill("")));
}

function htmlTableToMd(html) {
  const grid = tableGrid(html);
  if (!grid.length) return "";
  const lines = [pipeRow(grid[0]), pipeRow(new Array(grid[0].length).fill("---"))];
  for (const r of grid.slice(1)) lines.push(pipeRow(r));
  return lines.join("\n");
}

function canonicalMd(type, md, latex, html) {
  if (type === "code") return md;
  if (type === "formula" && isStr(latex)) return "$$" + latex + "$$";
  if (type === "table" && html) return htmlTableToMd(html);
  const text = md.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  let out = text.split("\n").map((ln) => (ln.trim() && ln.endsWith("  ")) ? rstrip(ln) + "\\" : rstrip(ln));
  while (out.length && !out[0]) out.shift();
  while (out.length && !out[out.length - 1]) out.pop();
  if (type === "heading" && out.length) {
    const m = /^(#{1,6})\s*(.*)$/.exec(out[0]);
    if (m) {
      const t = m[2].replace(/(?:^|\s)#+$/, "").trim();
      out[0] = m[1] + (t ? " " + t : "");
    }
  }
  if (type === "list" || type === "form_field") {
    out = out.map((ln) => ln.replace(/^(\s*)[*+](\s)/, "$1-$2"));
  }
  if (type === "table" && out.length && out.every((ln) => lstrip(ln).startsWith("|"))) {
    const rows = out.map(splitRow);
    if (rows.length > 1 && rows[1].every((c) => SEP_CELL_RE.test(c))) rows[1] = rows[1].map(sepCell);
    out = rows.map(pipeRow);
  }
  return out.join("\n");
}

class Parents {
  constructor() {
    this.frames = [[null, []]];
  }
  default(row) {
    const [group, heads] = this.frames[this.frames.length - 1];
    if (row.type === "heading") {
      const level = row.level || 1;
      for (let i = heads.length - 1; i >= 0; i--) if (heads[i][0] < level) return heads[i][1];
      return group;
    }
    return heads.length ? heads[heads.length - 1][1] : group;
  }
  add(row) {
    if (row.type === "heading") {
      const level = row.level || 1;
      const heads = this.frames[this.frames.length - 1][1];
      while (heads.length && heads[heads.length - 1][0] >= level) heads.pop();
      heads.push([level, row]);
    }
  }
  openGroup(row) {
    this.frames.push([row, []]);
  }
  closeGroup() {
    if (this.frames.length > 1) this.frames.pop();
  }
}

function sha256File(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function fill(rowsIn, doc, base) {
  const rows = rowsIn.map((r) => Object.assign({}, r));
  if (!rows.length || rows[0].type !== "document") {
    throw new Error("line 1 must be the header line with \"type\":\"document\"");
  }
  const h = rows[0];
  doc = h.doc || doc;
  if (!doc) throw new Error("the header needs 'doc' (a short document name)");
  h.doc = doc;
  const els = rows.slice(1);
  const used = els.filter((e) => isStr(e.id) && ID_RE.test(e.id)).map((e) => idNumber(e.id));
  let last = Math.max(h.last_id || 0, ...used);
  for (const e of els) {
    if (!(isStr(e.id) && ID_RE.test(e.id))) {
      last += 1;
      e.id = doc + "#e" + last;
    }
  }
  const tracker = new Parents();
  for (const e of els) {
    const t = TYPES.includes(e.type) ? e.type : "paragraph";
    e.type = t;
    let md = isStr(e.md) ? e.md : "";
    if (t === "heading") {
      const m = HEADING_RE.exec(md);
      if (!isInt(e.level)) e.level = m ? m[1].length : 1;
      if (!m) md = "#".repeat(e.level) + " " + md.trim();
    }
    if (t === "formula" && !isStr(e.latex)) e.latex = stripDollars(md);
    e.md = canonicalMd(t, md, e.latex, e.html);
    if (!("parent" in e)) {
      const p = tracker.default(e);
      e.parent = p ? p.id : null;
    }
    tracker.add(e);
    e.hash = elementHash(t, e.md);
    e.characters = chars(e.md);
    for (const k of Object.keys(e)) if (k.startsWith("_")) delete e[k];
  }
  if (!("version" in h)) h.version = VERSION;
  if (!("source" in h)) h.source = doc + ".md";
  if (!h.sha256) {
    const src = path.join(base || ".", h.source);
    if (fs.existsSync(src) && fs.statSync(src).isFile()) {
      h.sha256 = sha256File(src);
    } else {
      const digest = crypto.createHash("sha256");
      for (const e of els) digest.update(e.type + "\n" + e.md + "\n", "utf8");
      h.sha256 = digest.digest("hex");
    }
  }
  if (!("protection" in h)) h.protection = "none";
  if (!("signed" in h)) h.signed = false;
  if (!("converter" in h)) h.converter = CONVERTER;
  h.structure = Boolean(h.structure) || els.some((e) => e.type === "heading");
  h.elements = els.length;
  if (!("created" in h)) h.created = nowIso();
  if (!("lang" in h)) h.lang = "en";
  if (!("access" in h)) h.access = ["all"];
  h.last_id = last;
  return rows;
}

function stripDollars(md) {
  let s = md.trim();
  if (s.startsWith("$$")) s = s.slice(2);
  if (s.endsWith("$$")) s = s.slice(0, -2);
  return s.trim().includes("\n") ? stripNl(s) : s.trim();
}

function parseNote(line) {
  const m = NOTE_RE.exec(line);
  if (!m || line.trim().includes("\n")) return null;
  let body = m[1];
  if (body.startsWith("/")) {
    const name = body.slice(1).trim();
    if (!name || name.includes(" ")) return null;
    return name === "group" ? ["endgroup", {}] : ["end", { name: name }];
  }
  let meta = null;
  const k = /(^|\s)meta=/.exec(body);
  if (k) {
    try {
      meta = JSON.parse(body.slice(k.index + k[0].length));
    } catch (e) {
      return null;
    }
    if (!isObj(meta)) return null;
    body = body.slice(0, k.index);
  }
  let toks = body.trim() ? body.trim().split(/\s+/) : [];
  let kind = "note";
  const attrs = {};
  if (toks.length && toks[0] === "group") {
    kind = "group";
    toks = toks.slice(1);
  }
  if (toks.length && SHORT_ID_RE.test(toks[0])) {
    attrs._id = toks[0];
    toks = toks.slice(1);
  } else if (kind === "note" && !toks.length) {
    return null;
  }
  for (const tok of toks) {
    const eq = tok.indexOf("=");
    if (eq < 0) return null;
    const key = tok.slice(0, eq);
    if (!NOTE_KEYS.includes(key)) return null;
    attrs[key] = tok.slice(eq + 1);
  }
  if (meta !== null) attrs.meta = meta;
  return [kind, attrs];
}

function detect(block) {
  const s = lstrip(block);
  if (HEADING_RE.test(s)) return "heading";
  if (FENCE_RE.test(block)) return "code";
  if (s.startsWith("|") || s.toLowerCase().startsWith("<table")) return "table";
  if (s.startsWith("$$")) return "formula";
  if (!block.trim().includes("\n") && IMAGE_RE.test(block.trim())) return "image";
  if (s.startsWith(">")) return "quote";
  if (/^([-*+]|\d+[.)])\s/.test(s)) return "list";
  return "paragraph";
}

function readBlock(lines, i) {
  const ln = lines[i];
  const s = lstrip(ln);
  const m = FENCE_RE.exec(ln);
  if (m) {
    const fence = m[1];
    let j = i + 1;
    while (j < lines.length) {
      const mm = FENCE_RE.exec(lines[j]);
      if (mm && mm[1][0] === fence[0] && mm[1].length >= fence.length &&
          !lines[j].trim().slice(mm[1].length).trim()) {
        return [lines.slice(i, j + 1).join("\n"), j + 1];
      }
      j += 1;
    }
    return [lines.slice(i).join("\n"), lines.length];
  }
  if (s.toLowerCase().startsWith("<table")) {
    let j = i;
    while (j < lines.length && !lines[j].toLowerCase().includes("</table>")) j += 1;
    return [lines.slice(i, j + 1).join("\n"), j + 1];
  }
  if (s.startsWith("$$")) {
    if (s.trim().length >= 4 && s.trim().endsWith("$$")) return [ln, i + 1];
    let j = i + 1;
    while (j < lines.length && !rstrip(lines[j]).endsWith("$$")) j += 1;
    return [lines.slice(i, j + 1).join("\n"), j + 1];
  }
  if (HEADING_RE.test(s)) return [ln, i + 1];
  let j = i + 1;
  while (j < lines.length) {
    const nxt = lines[j];
    if (!nxt.trim() || parseNote(nxt) || FENCE_RE.test(nxt) || HEADING_RE.test(lstrip(nxt))) break;
    j += 1;
  }
  return [lines.slice(i, j).join("\n"), j];
}

function findEnd(lines, i, name) {
  let j = i;
  let fence = null;
  while (j < lines.length) {
    const ln = lines[j];
    const m = FENCE_RE.exec(ln);
    if (fence) {
      if (m && m[1][0] === fence[0] && m[1].length >= fence.length) fence = null;
    } else if (m) {
      fence = m[1];
    } else {
      const note = parseNote(ln);
      if (note) {
        if (note[0] === "end" && note[1].name === name) return j;
        if (note[0] !== "end") return null;
      }
    }
    j += 1;
  }
  return null;
}

function splitFront(text) {
  if (!text.startsWith("---\n")) return [{}, text];
  let end = text.indexOf("\n---\n", 3);
  if (end === -1) {
    if (text.endsWith("\n---")) end = text.length - 4;
    else return [{}, text];
  }
  const front = text.slice(4, end);
  const body = text.slice(end + 5);
  const fields = {};
  for (const ln of front.split("\n")) {
    if (!ln.trim() || lstrip(ln).startsWith("#")) continue;
    const c = ln.indexOf(":");
    if (c < 0) throw new Error("front matter line '" + ln + "' needs the form key: value");
    const key = ln.slice(0, c).trim();
    fields[key] = frontValue(key, ln.slice(c + 1).trim());
  }
  return [fields, body];
}

function frontValue(key, raw) {
  if (key === "fmjl") return raw.replace(/^"+|"+$/g, "");
  if (raw.startsWith("\"") || raw.startsWith("[") || raw.startsWith("{")) {
    try {
      return JSON.parse(raw);
    } catch (e) {
      return raw;
    }
  }
  if (key === "authors") return raw.split(",").map((a) => a.trim()).filter(Boolean);
  if (raw === "true" || raw === "false") return raw === "true";
  if (raw === "null") return null;
  if ((key === "last_id" || key === "elements") && /^-?\d+$/.test(raw)) return Number(raw);
  return raw;
}

function ref(value, doc) {
  return SHORT_ID_RE.test(value) ? doc + "#" + value : value;
}

function toInt(v, key) {
  const s = String(v).trim();
  if (!/^[+-]?\d+$/.test(s)) throw new Error(key + "=" + v + " is not a whole number");
  return Number(s);
}

function applyNote(row, attrs, doc) {
  for (const key of Object.keys(attrs)) {
    const val = attrs[key];
    if (key === "_id" || key === "type") continue;
    if (key === "page") {
      row.page = toInt(val, key);
    } else if (key === "pages" || key === "bbox") {
      row[key] = val.split(",").filter((v) => v !== "").map((v) => toInt(v, key));
    } else if (key === "confidence") {
      const n = Number(val);
      if (!Number.isFinite(n)) throw new Error("confidence=" + val + " is not a number");
      row.confidence = n;
      row[FLOAT] = true;
    } else if (key === "access") {
      row.access = val.split(",").filter(Boolean);
    } else if (key === "reference") {
      const refs = val.split(",").filter(Boolean).map((v) => ref(v, doc));
      row.reference = refs.length === 1 ? refs[0] : refs;
    } else if (key === "continues" || key === "parent") {
      row[key] = val === "null" ? null : ref(val, doc);
    } else if (key === "level") {
      row.level = toInt(val, key);
    } else {
      row[key] = val;
    }
  }
}

function makeElement(block, attrs, doc) {
  const detected = detect(block);
  const t = attrs.type || detected;
  const row = { type: t };
  let md;
  if (t === "heading") {
    const m = HEADING_RE.exec(lstrip(block));
    row.level = m ? m[1].length : 1;
    md = block.trim();
  } else if (t === "image" && detected === "image") {
    const m = IMAGE_RE.exec(block.trim());
    row.file = m[2];
    md = m[1];
  } else if (t === "formula" && detected === "formula") {
    const latex = stripDollars(block);
    row.latex = latex;
    md = "$$" + latex + "$$";
  } else if (t === "table" && lstrip(block).toLowerCase().startsWith("<table")) {
    row.html = block.trim();
    md = htmlTableToMd(row.html);
  } else {
    md = block;
  }
  row.md = md;
  applyNote(row, attrs, doc);
  if ("_id" in attrs) row.id = doc + "#" + attrs._id;
  return row;
}

function place(row, tracker, els) {
  row._parent_row = tracker.default(row);
  tracker.add(row);
  els.push(row);
}

function importMd(text, opts) {
  opts = opts || {};
  text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const [front, body] = splitFront(text);
  const h = { type: "document" };
  for (const k of Object.keys(front)) h[k === "fmjl" ? "version" : k] = front[k];
  const doc = h.doc || opts.doc;
  if (!doc) throw new Error("no document name: add 'doc: my_doc' to the front matter");
  h.doc = doc;
  if (opts.source && !h.source) h.source = opts.source;

  const lines = body.split("\n");
  const els = [];
  const tracker = new Parents();
  const groups = [];
  let pending = null;
  let pendingGroup = null;
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (!ln.trim()) {
      i += 1;
      continue;
    }
    const note = parseNote(ln);
    if (note) {
      const [kind, attrs] = note;
      i += 1;
      if (kind === "group") {
        pendingGroup = attrs;
      } else if (kind === "endgroup") {
        if (groups.length) {
          groups.pop();
          tracker.closeGroup();
        }
      } else if (kind === "note") {
        const name = attrs._id || attrs.label;
        const j = name ? findEnd(lines, i, name) : null;
        if (j !== null) {
          const row = makeElement(stripNl(lines.slice(i, j).join("\n")), attrs, doc);
          place(row, tracker, els);
          i = j + 1;
        } else {
          pending = attrs;
        }
      }
      continue;
    }
    const [block, next] = readBlock(lines, i);
    i = next;
    if (pendingGroup !== null) {
      const attrs = Object.assign({}, pendingGroup, { type: "group" });
      pendingGroup = null;
      const row = makeElement(block, attrs, doc);
      row.md = block.trim();
      for (const k of ["file", "latex", "html", "level"]) delete row[k];
      place(row, tracker, els);
      tracker.openGroup(row);
      groups.push(row);
    } else {
      const row = makeElement(block, pending || {}, doc);
      pending = null;
      place(row, tracker, els);
    }
  }

  const seen = new Set();
  for (const e of els) {
    if ("id" in e) {
      if (seen.has(e.id)) throw new Error("id " + e.id + " is used twice in the notes");
      seen.add(e.id);
    }
  }
  const used = els.filter((e) => "id" in e).map((e) => idNumber(e.id));
  let last = Math.max(h.last_id || 0, ...used);
  for (const e of els) {
    if (!("id" in e)) {
      last += 1;
      e.id = doc + "#e" + last;
    }
  }
  h.last_id = last;
  const labels = {};
  for (const e of els) if (isStr(e.label)) labels[e.label] = e.id;
  const resolve = (v) => (isStr(v) && !ID_RE.test(v) && v in labels ? labels[v] : v);
  for (const e of els) {
    const p = e._parent_row;
    delete e._parent_row;
    if ("parent" in e) e.parent = resolve(e.parent);
    else e.parent = p ? p.id : null;
    if ("reference" in e) {
      e.reference = isStr(e.reference) ? resolve(e.reference) : e.reference.map(resolve);
    }
    if ("continues" in e) e.continues = resolve(e.continues);
  }
  return fill([h].concat(els), undefined, opts.base);
}

function needsQuotes(v) {
  return v === "" || v !== v.trim() || v.includes("\n") || v.includes(": ") || v.includes(", ") ||
    v.endsWith(":") || QUOTE_STARTS.includes(v[0]) || ["true", "false", "null"].includes(v) ||
    /^-?\d+(\.\d+)?$/.test(v);
}

function frontText(key, v) {
  if (key === "fmjl") return JSON.stringify(v);
  if (key === "authors" && Array.isArray(v) && v.every((a) => isStr(a) && !a.includes(","))) return v.join(", ");
  if (typeof v === "boolean") return v ? "true" : "false";
  if (v === null || v === undefined) return "null";
  if (typeof v === "number") return String(v);
  if (Array.isArray(v) || isObj(v)) return pyJson(v, false);
  return needsQuotes(v) ? JSON.stringify(v) : v;
}

function renderBlock(e) {
  const t = e.type;
  if (t === "image") return "![" + (e.md || "") + "](" + (e.file || "") + ")";
  if (t === "formula") {
    const latex = isStr(e.latex) ? e.latex : stripDollars(e.md || "");
    return latex.includes("\n") ? "$$\n" + latex + "\n$$" : "$$" + latex + "$$";
  }
  if (t === "table" && isStr(e.html) && e.html) return e.html;
  return e.md || "";
}

function inside(e, groupId, byId) {
  let p = e.parent;
  let steps = 0;
  while (isStr(p) && steps < 10000) {
    if (p === groupId) return true;
    p = byId.has(p) ? byId.get(p).parent : undefined;
    steps += 1;
  }
  return false;
}

function noteAttrs(e, doc, defaultParent, block) {
  const parts = [];
  if (e.type !== "group" && detect(block) !== e.type) parts.push("type=" + e.type);
  for (const k of ["subtype", "label"]) if (k in e) parts.push(k + "=" + e[k]);
  if ("page" in e) parts.push("page=" + e.page);
  if ("pages" in e) parts.push("pages=" + e.pages.join(","));
  if ("bbox" in e) parts.push("bbox=" + e.bbox.join(","));
  if ("confidence" in e) parts.push("confidence=" + pyNum(e.confidence, e[FLOAT]));
  if ("lang" in e) parts.push("lang=" + e.lang);
  if ("access" in e) parts.push("access=" + e.access.join(","));
  if ("reference" in e) {
    const refs = Array.isArray(e.reference) ? e.reference : [e.reference];
    parts.push("reference=" + refs.map((r) => shortId(r, doc)).join(","));
  }
  if ("continues" in e) parts.push("continues=" + shortId(e.continues, doc));
  const dp = defaultParent ? defaultParent.id : null;
  const parent = e.parent === undefined ? null : e.parent;
  if (parent !== dp) parts.push("parent=" + (e.parent ? shortId(e.parent, doc) : "null"));
  if ("meta" in e) parts.push("meta=" + pyJson(e.meta, true));
  return parts;
}

function exportMd(rows) {
  const h = rows[0];
  const els = rows.slice(1);
  const doc = h.doc;
  const out = ["---"];
  const front = Object.assign({}, h);
  front.fmjl = "version" in front ? front.version : VERSION;
  delete front.version;
  for (const k of FRONT_ORDER) if (k in front) out.push(k + ": " + frontText(k, front[k]));
  for (const k of Object.keys(front)) {
    if (!FRONT_ORDER.includes(k) && !["type", "structure", "elements"].includes(k)) {
      out.push(k + ": " + frontText(k, front[k]));
    }
  }
  out.push("---", "");

  const byId = new Map();
  for (const e of els) if (isStr(e.id)) byId.set(e.id, e);
  const tracker = new Parents();
  const openGroups = [];
  for (const e of els) {
    while (openGroups.length && !inside(e, openGroups[openGroups.length - 1].id, byId)) {
      out.push("<!-- /group -->", "");
      openGroups.pop();
      tracker.closeGroup();
    }
    const block = renderBlock(e);
    const attrs = [shortId(e.id, doc)].concat(noteAttrs(e, doc, tracker.default(e), block));
    if (e.type === "group") {
      out.push("<!-- group " + attrs.join(" ") + " -->", block, "");
      tracker.add(e);
      tracker.openGroup(e);
      openGroups.push(e);
    } else {
      out.push("<!-- " + attrs.join(" ") + " -->", block);
      if (block.includes("\n\n") && e.type !== "code") out.push("<!-- /" + shortId(e.id, doc) + " -->");
      out.push("");
      tracker.add(e);
    }
  }
  while (openGroups.length) {
    out.push("<!-- /group -->", "");
    openGroups.pop();
  }
  return out.join("\n");
}

function docName(stem) {
  return stem.toLowerCase().replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
}

module.exports = {
  VERSION, CONVERTER, TYPES,
  elementHash, dumps, readRows, writeRows, canonicalMd, htmlTableToMd,
  fill, importMd, exportMd, docName,
};
