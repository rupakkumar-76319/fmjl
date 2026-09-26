---
fmjl: "0.4"
doc: fmjl_rulebook
title: "FMJL Rulebook, Version 0.4"
summary: "The rules of FMJL: one document, two forms - .fmjl storage for machines and Markdown authoring for people."
lang: en
access: ["all"]
source: fmjl_rulebook_v0.4.md
sha256: 44900c5a8380d6289d163706ebbb3b02801b4997de26d439eb6669d9d05afb18
protection: none
signed: false
converter: fmjl 0.4
created: 2026-09-26T17:10:54Z
last_id: 114
---

# FMJL Rulebook, Version 0.4

Status: draft. The license is not decided yet.

This rulebook is the authority for FMJL. The `fmjl.py` tool is the reference implementation: if the tool and this rulebook disagree, the tool has a bug.

## 1. What FMJL Is

FMJL stores any document as a list of small parts called elements, such as headings, paragraphs, tables, and images. It is built so that people can read and write documents easily, and machines can search and use them quickly.

FMJL combines four languages:

| Language | Role | Where it appears |
| --- | --- | --- |
| JSON (JSON Lines) | The container of the storage form | Every line of an `.fmjl` file |
| Markdown | All readable text | The `md` field, and the whole authoring form |
| LaTeX | Math formulas | The `latex` field |
| HTML | Tables with merged cells | The `html` field |

Three rules make sure nothing is lost:

1. Every part of the original document becomes an element, including stamps, logos, watermarks, and blacked-out areas.
2. Every element from a page-based file records its page and position, so its exact spot in the original can always be found.
3. The original file is always kept next to the FMJL files.

## 2. One Document, Two Forms

Every FMJL document can be written in two forms that hold exactly the same information:

|  | Storage form | Authoring form |
| --- | --- | --- |
| File | `name.fmjl` | `name.md` |
| Looks like | One JSON object per line | Normal Markdown, with small hidden notes |
| Made for | Machines: search, RAG, databases | People: reading, writing, reviewing |
| Opens in | Any JSON Lines tool or language | Any Markdown editor, GitHub, VS Code preview |

The tool converts between the two forms without losing anything: `fmjl new` turns the authoring form into the storage form, and `fmjl md` turns it back. Converting there and back always gives the same result.

Recommended use:

1. People write and edit the authoring form.
2. Machines read the storage form.
3. Version control (such as Git) keeps the authoring form, because its short lines make changes easy to see.

## 3. Storage Layout

While processing, each document is stored as one folder:

```text
leave_policy/
  leave_policy.fmjl     the storage form
  leave_policy.md       the authoring form (optional)
  images/               cropped images
  original/             the untouched original file
```

For sharing, the same folder is packed into one zip file.

The name FMJL is short for Format, Markdown, JSON Lines, and it is also the file extension, `.fmjl`. Rules for the storage form:

1. Text encoding is UTF-8.
2. Each line is exactly one JSON object. Lines end with a newline character, and there are no empty lines.
3. Line 1 is the header line. Every following line is an element line.
4. Element lines appear in reading order.

Lines in the storage form can be very long, because a whole table is one line. To compare two versions, use the authoring form, or `git diff --word-diff` on the storage form.

## 4. The Header Line

The header line describes the whole document. It has `"type": "document"` and these 12 required fields:

| Field | Value | Meaning |
| --- | --- | --- |
| `version` | Text | The rulebook version the file follows, for example `"0.4"` |
| `doc` | Text | Short document name, using lowercase letters, digits, `_` or `-` |
| `source` | Text | The original file name |
| `sha256` | 64 hexadecimal characters | Fingerprint of the original file, used to skip duplicate uploads |
| `protection` | `none`, `password`, `certificate`, or `drm` | How the original file was locked |
| `signed` | `true` or `false` | Whether the original carries a digital signature |
| `converter` | Text | The tool and version that created this file |
| `structure` | `true` or `false` | `false` means no headings were found, so the file should be converted again with a better tool |
| `elements` | Whole number, or `null` | The number of element lines; `null` only while the file is still being written |
| `created` | Date and time (ISO 8601, UTC) | When the file was created |
| `lang` | Language code | The main language, for example `"en"`, `"hi"`, `"as"`, or `"bn"` |
| `access` | List of group names | The default permission, for example `["all"]` or `["hr"]` |

Optional header fields describe the document itself:

| Field | Value | Meaning |
| --- | --- | --- |
| `title` | Text | The document's title |
| `authors` | List of names | Who wrote the document |
| `date` | `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` | The document's own date, not the conversion date |
| `summary` | Text | A short summary of the whole document |
| `last_id` | Whole number | The highest element number ever given, so numbers are never reused (section 7.1) |
| `meta` | Object | Custom data (section 7.6) |

Security rule: `protection` records only how a file was locked. A password or key is never stored anywhere in FMJL.

## 5. Element Lines

### 5.1 Required Fields

Every element line has these 6 fields:

| Field | Value | Meaning |
| --- | --- | --- |
| `id` | Text | `<doc>#e<number>`, for example `leave_policy#e7` (section 7.1) |
| `hash` | 16 hexadecimal characters | Content fingerprint (section 7.2) |
| `type` | One of the 20 types | What kind of part this is (section 6) |
| `parent` | Element ID or `null` | The heading or group this element belongs to (section 7.4) |
| `characters` | Whole number | The number of characters in `md` |
| `md` | Text | The content, in canonical Markdown (section 8) |

### 5.2 Optional Fields

| Field | Value | Used when |
| --- | --- | --- |
| `subtype` | Text | The element is an `image`, `noise`, or `group` |
| `label` | Lowercase name, for example `inputs` | People want to refer to the element by name |
| `level` | 1 to 6 | The element is a `heading` (required for headings) |
| `page` | Whole number, from 0 | The element sits on one page |
| `pages` | List of page numbers | The element spans several pages |
| `bbox` | `[left, top, right, bottom]` | The position on the page is known |
| `reference` | Element ID, or a list of two or more IDs | The element points to other elements |
| `continues` | Element ID | The element is the next part of a split element |
| `confidence` | Number from 0 to 1 | The content came from OCR or an AI model |
| `lang` | Language code | The element's language differs from the header |
| `access` | List of group names | The element's permission differs from the header |
| `html` | Text | A `table` has merged cells or multi-level headers |
| `latex` | Text | The element is a `formula` (required for formulas) |
| `file` | Path | The element is an `image` (required for images) |
| `meta` | Object | Custom data (section 7.6) |

When an optional field is missing, a default applies: no `confidence` means fully certain (1), and no `lang` or `access` means the header's value applies.

## 6. Element Types

| # | Type | Holds | Rules |
| --- | --- | --- | --- |
| 1 | `heading` | Titles and subtitles | Needs `level` |
| 2 | `paragraph` | Normal text | Inline math uses `$...$` (section 8) |
| 3 | `list` | Bullet or numbered points | A whole list is one element |
| 4 | `table` | Rows and columns | May add `html`; long tables may be split (section 11) |
| 5 | `formula` | Display math | Needs `latex`; `md` is `$$` + `latex` + `$$` |
| 6 | `code` | Program code | `md` is a fenced code block that names the language |
| 7 | `image` | Pictures, charts, logos, stamps, signatures, QR codes | Needs `file`; `md` holds a text description |
| 8 | `caption` | The label of a table or image | `reference` points to that table or image |
| 9 | `footnote` | Notes at the bottom of a page | `reference` points to the text that uses it |
| 10 | `form_field` | Form entries and checkboxes | `md` looks like `- [x] Married` |
| 11 | `annotation` | Comments and handwritten notes | Usually has `confidence` |
| 12 | `redaction` | Blacked-out hidden parts | `md` is `[REDACTED]` |
| 13 | `noise` | Page headers, footers, watermarks, page numbers | Needs `subtype` |
| 14 | `message` | One email or chat message | Sender and date go at the top of `md` |
| 15 | `utterance` | One speaker's turn in a transcript | Speaker and time go at the top of `md` |
| 16 | `record` | One CSV row or one JSON object | `md` lists the fields as `Name: value` |
| 17 | `citation` | A reference or bibliography entry | In-text markers link here with `reference` |
| 18 | `quote` | Quoted text from another source | `md` uses `>` |
| 19 | `toc` | A table of contents | Kept for structure |
| 20 | `group` | A container, such as a slide, a sidebar, or a figure with several images | Needs `subtype`; `md` holds its title |

Subtypes:

1. For `image`: `logo`, `stamp`, `signature`, `chart`, `diagram`, `photo`, `qr_code`, or `barcode`. For `qr_code` and `barcode`, `md` also holds the decoded value.
2. For `noise`: `header`, `footer`, `watermark`, or `page_number`.
3. For `group`: `slide`, `sidebar`, `figure`, `box`, `sheet`, or `thread`.

## 7. Field Rules

### 7.1 IDs

1. An ID is `<doc>#e<number>` and is unique in the document.
2. An ID never changes once given, even when other elements are added or removed.
3. A new element gets the next free number, which is `last_id` plus 1. Numbers of removed elements are never reused.
4. Reading order comes from the order of the lines, not from the ID numbers.

### 7.2 Hash

`hash` is the first 16 hexadecimal characters of the SHA-256 of the text `type`, a newline, then `md`, encoded in UTF-8. When a document is uploaded again, only elements whose `hash` changed need new embeddings.

Hashes are only compared within one document, so 16 characters (64 bits) are enough. Even a document with 1 million elements has about a 1 in 37 million chance of any two hashes matching.

### 7.3 Pages and Positions

1. Page numbers start at 0. When showing a page number to users, add 1.
2. An element has `page` or `pages`, never both. `pages` holds at least two numbers, in order.
3. `bbox` is `[left, top, right, bottom]` in whole numbers from 0 to 1000, where 1000 is the full page width or height and `[0, 0]` is the top-left corner.
4. `bbox` is allowed only together with `page`.
5. For slides, `page` is the slide number. For spreadsheets, it is the sheet number.

### 7.4 Parents and Groups

1. `parent` points to a `heading` or a `group` that comes earlier in the file.
2. By default, an element's parent is the nearest heading above it with a lower level. Inside a group, the default parent is the group, or a heading inside that group.
3. A heading's parent, when it is a heading, must have a smaller level.
4. Groups can hold any elements, including headings and other groups.

### 7.5 Links Between Elements

1. `reference` links an element to others: a caption to its table, a footnote to its text, a chart image to the table holding its data.
2. `continues` links the parts of a split element in order. Each part has the same type as the part before it.
3. Inside `md`, a Markdown link can point to an element in the same document by ID or label: `[Table 1](#e7)` or `[Table 1](#inputs)`.
4. A `label` is unique in the document and never changes the ID.

### 7.6 Custom Data

`meta` holds custom data on the header or on any element. To avoid clashes, use names that start with your organization, such as `"acme.department"`. One name is reserved: `facts`, a list of extracted facts, for example `[{"name": "fee", "value": "₹5,000"}]`.

## 8. Canonical Markdown

The same content must always give the same `md` text, so that the same content always gives the same `hash`. `md` follows CommonMark plus GitHub-style tables, strikethrough, and task lists, written in this canonical form:

1. Lines end with a newline character only, with no spaces at the end of a line.
2. A hard line break is written as a backslash at the end of the line.
3. Headings use `#` marks followed by one space, for example `## Annual Leave`.
4. Bullet list markers are `-`.
5. Tables are written as `| cell | cell |`, with separator cells `---`, `:---`, `---:`, or `:---:`.
6. A `table` with `html`: the HTML is the exact structure, and `md` is made from it by repeating each merged cell in every cell it covers.
7. A `formula`: `latex` is the formula, and `md` is `$$` + `latex` + `$$`.
8. Inline math is written between single dollar signs. A dollar sign followed by a digit is always money, never math, so "$50" is always an amount. A literal dollar sign can also be written as `\$`.
9. `code` elements keep their text exactly as written.

The `fmjl fill` command rewrites any `md` into canonical form.

## 9. The Authoring Form

The authoring form is a normal Markdown file that anyone can read and write. The tool turns each block of Markdown into one element.

### 9.1 Front Matter

The file can start with front matter between two `---` lines. It holds the header fields, one per line:

```markdown
---
doc: photosynthesis
title: Photosynthesis Notes
authors: Riya Das, Amit Roy
date: 2026-09-26
lang: en
---
```

Missing header fields are filled in by the tool.

### 9.2 Blocks Become Elements

The tool recognizes the type of each block by itself:

| You write | It becomes |
| --- | --- |
| `# Title`, `## Section` | `heading` |
| Normal text | `paragraph` |
| `- item` or `1. item` | `list` |
| A Markdown table | `table` |
| `<table>...</table>` | `table` with `html` |
| `$$ ... $$` on its own | `formula` |
| `![description](images/file.png)` on its own | `image` |
| A fenced code block | `code` |
| `> quoted text` | `quote` |

### 9.3 Notes

A note is an HTML comment on its own line, directly before a block. Markdown viewers hide notes, so the document stays clean to read. A note adds fields to the block after it:

```markdown
<!-- type=caption reference=inputs -->
Table 1: Inputs of photosynthesis
```

A note can hold:

1. The element's ID, such as `e7`, first.
2. `type=` for types the tool cannot recognize by itself, such as `caption`, `footnote`, or `noise`.
3. `subtype=`, `label=`, `page=`, `lang=`, `confidence=`, `parent=`, and `continues=`.
4. Lists separated by commas: `pages=`, `bbox=`, `access=`, and `reference=`.
5. `meta=` followed by JSON, always at the end of the note.

References, `parent=`, and `continues=` can use an ID (`e7`) or a label (`inputs`). HTML comments that do not start like a note stay in the document as normal content.

### 9.4 Groups

A group starts with `<!-- group subtype=... -->`. The next block is the group's title, and every block until `<!-- /group -->` belongs to the group:

```markdown
<!-- group subtype=figure -->
**Figure 1: Inside a leaf**

![Cross-section of a leaf](images/leaf.png)

<!-- /group -->
```

### 9.5 Elements With Several Blocks

When one element holds several blocks, such as an email with a blank line inside it, it starts with a note that has an ID or a label, and ends with a matching end note:

```markdown
<!-- type=message label=hr-email -->
**From:** HR

Please submit the form by Friday.
<!-- /hr-email -->
```

### 9.6 Editing an Existing Document

1. Turn the storage form into the authoring form: `python fmjl.py md name.fmjl`.
2. Edit `name.md` in any editor. Each block keeps its ID in a small note, such as `<!-- e7 -->`.
3. Turn it back: `python fmjl.py new name.md`.

Blocks you did not change keep their IDs and hashes, new blocks get new IDs, and removed IDs are never reused.

## 10. Input Formats

FMJL accepts all formats, in five groups:

| Group | Formats | How they are converted |
| --- | --- | --- |
| Page-based | PDF, TIFF, PNG, JPG, and other scans | Full pipeline with OCR and layout detection; fills `page`, `bbox`, and `confidence` |
| Structured | DOCX, DOC, PPTX, ODT, RTF, HTML, Markdown, EPUB, LaTeX | Structure is read directly, with no OCR; each slide becomes a `group` with subtype `slide` |
| Tables | XLSX, XLS, ODS, CSV, TSV | Each sheet becomes a `group` with subtype `sheet`, holding `table` parts; CSV rows become `record` elements |
| Code and data | Source code, JSON, JSONL, YAML, XML | Code becomes one `code` element per function or class; data becomes one `record` per object |
| Email and transcripts | EML, MSG, MBOX, chat exports, SRT, VTT | One `message` per message, inside a `group` with subtype `thread`; one `utterance` per speaker turn |

Images saved by FMJL use PNG, WebP, JPG, or SVG. TIFF is accepted as input only.

## 11. Processing Order

1. Quick check: confirm the file is valid, not a duplicate (`sha256`), which pages are digital or scanned, the language, and the page count.
2. Convert: extract every part into elements and write the storage form.
3. Final check: run the checks listed below.
4. Chunk: pack elements into chunks by `characters`.
5. Embed: create embeddings and store them in the vector database.

If the final check fails, convert again with a stronger tool and check again.

Large elements: a table longer than a converter's limit is split into parts, each repeating the header rows, linked with `continues`. A paragraph or list longer than one chunk is split at sentence boundaries when chunking.

The final check confirms that:

1. Every line passes the JSON Schema in section 14.
2. `elements` in the header is a number and equals the number of element lines.
3. IDs and labels are unique, and no ID number is higher than `last_id`.
4. Every `parent`, `reference`, `continues`, and in-document link points to an existing element.
5. Every `file` exists in the `images/` folder.
6. Every `md` is in canonical form, and every `hash` and `characters` value matches it.

## 12. Recommended Retrieval Practices

One rule is required: always filter by `access` before searching, so users never see parts they are not allowed to see.

The rest are recommendations. A system may change them for good reasons:

1. Don't embed `noise`, `toc`, or `redaction` elements.
2. Embed `md`, including for tables that also have `html`.
3. Add each element's section path, rebuilt from its `parent` chain, to its chunk for context.
4. Return `caption` and `citation` elements together with the elements they reference, and a chart together with its data table.
5. When an answer uses content with low `confidence`, show the original region using `page` and `bbox`.
6. Cite answers with the element `id` and the page number plus 1.

## 13. Reader Rules

1. Readers ignore fields they do not know, so newer files stay readable.
2. Readers treat unknown types as `paragraph`.
3. A reader for version 0.x can read any file of version 0.x. The `fmjl upgrade` command turns older files into the current version.

## 14. JSON Schema

This schema checks every line of the storage form automatically (JSON Schema draft 2020-12). A line is valid if it matches either the header or the element definition. Checks that need the whole file are listed in section 11.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "FMJL line, version 0.4",
  "oneOf": [
    {
      "$ref": "#/$defs/header"
    },
    {
      "$ref": "#/$defs/element"
    }
  ],
  "$defs": {
    "header": {
      "type": "object",
      "required": [
        "type",
        "version",
        "doc",
        "source",
        "sha256",
        "protection",
        "signed",
        "converter",
        "structure",
        "elements",
        "created",
        "lang",
        "access"
      ],
      "properties": {
        "type": {
          "const": "document"
        },
        "version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+$"
        },
        "doc": {
          "type": "string",
          "pattern": "^[a-z0-9_-]+$"
        },
        "source": {
          "type": "string",
          "minLength": 1
        },
        "sha256": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "protection": {
          "enum": [
            "none",
            "password",
            "certificate",
            "drm"
          ]
        },
        "signed": {
          "type": "boolean"
        },
        "converter": {
          "type": "string",
          "minLength": 1
        },
        "structure": {
          "type": "boolean"
        },
        "elements": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "created": {
          "type": "string",
          "format": "date-time"
        },
        "lang": {
          "type": "string",
          "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)*$"
        },
        "access": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "pattern": "^[A-Za-z0-9_.:-]+$"
          }
        },
        "title": {
          "type": "string"
        },
        "authors": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "date": {
          "type": "string",
          "pattern": "^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$"
        },
        "summary": {
          "type": "string"
        },
        "last_id": {
          "type": "integer",
          "minimum": 0
        },
        "meta": {
          "type": "object"
        }
      }
    },
    "element": {
      "type": "object",
      "required": [
        "id",
        "hash",
        "type",
        "parent",
        "characters",
        "md"
      ],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
        },
        "hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{16}$"
        },
        "type": {
          "enum": [
            "heading",
            "paragraph",
            "list",
            "table",
            "formula",
            "code",
            "image",
            "caption",
            "footnote",
            "form_field",
            "annotation",
            "redaction",
            "noise",
            "message",
            "utterance",
            "record",
            "citation",
            "quote",
            "toc",
            "group"
          ]
        },
        "subtype": {
          "type": "string"
        },
        "label": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_-]*$"
        },
        "level": {
          "type": "integer",
          "minimum": 1,
          "maximum": 6
        },
        "parent": {
          "type": [
            "string",
            "null"
          ],
          "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
        },
        "page": {
          "type": "integer",
          "minimum": 0
        },
        "pages": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "integer",
            "minimum": 0
          }
        },
        "bbox": {
          "type": "array",
          "minItems": 4,
          "maxItems": 4,
          "items": {
            "type": "integer",
            "minimum": 0,
            "maximum": 1000
          }
        },
        "characters": {
          "type": "integer",
          "minimum": 0
        },
        "reference": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
            },
            {
              "type": "array",
              "minItems": 2,
              "items": {
                "type": "string",
                "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
              }
            }
          ]
        },
        "continues": {
          "type": "string",
          "pattern": "^[a-z0-9_-]+#e[1-9][0-9]*$"
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "lang": {
          "type": "string",
          "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)*$"
        },
        "access": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "pattern": "^[A-Za-z0-9_.:-]+$"
          }
        },
        "html": {
          "type": "string"
        },
        "latex": {
          "type": "string"
        },
        "file": {
          "type": "string",
          "pattern": "^images/[^/]+\\.(png|webp|jpg|jpeg|svg)$"
        },
        "meta": {
          "type": "object"
        },
        "md": {
          "type": "string"
        }
      },
      "dependentRequired": {
        "bbox": [
          "page"
        ]
      },
      "not": {
        "required": [
          "page",
          "pages"
        ]
      },
      "allOf": [
        {
          "if": {
            "required": [
              "type"
            ],
            "properties": {
              "type": {
                "const": "heading"
              }
            }
          },
          "then": {
            "required": [
              "level"
            ]
          }
        },
        {
          "if": {
            "required": [
              "type"
            ],
            "properties": {
              "type": {
                "const": "formula"
              }
            }
          },
          "then": {
            "required": [
              "latex"
            ]
          }
        },
        {
          "if": {
            "required": [
              "type"
            ],
            "properties": {
              "type": {
                "const": "image"
              }
            }
          },
          "then": {
            "required": [
              "file"
            ],
            "properties": {
              "subtype": {
                "enum": [
                  "logo",
                  "stamp",
                  "signature",
                  "chart",
                  "diagram",
                  "photo",
                  "qr_code",
                  "barcode"
                ]
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "type"
            ],
            "properties": {
              "type": {
                "const": "noise"
              }
            }
          },
          "then": {
            "required": [
              "subtype"
            ],
            "properties": {
              "subtype": {
                "enum": [
                  "header",
                  "footer",
                  "watermark",
                  "page_number"
                ]
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "type"
            ],
            "properties": {
              "type": {
                "const": "group"
              }
            }
          },
          "then": {
            "required": [
              "subtype"
            ],
            "properties": {
              "subtype": {
                "enum": [
                  "slide",
                  "sidebar",
                  "figure",
                  "box",
                  "sheet",
                  "thread"
                ]
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "level"
            ]
          },
          "then": {
            "properties": {
              "type": {
                "const": "heading"
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "html"
            ]
          },
          "then": {
            "properties": {
              "type": {
                "const": "table"
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "latex"
            ]
          },
          "then": {
            "properties": {
              "type": {
                "const": "formula"
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "file"
            ]
          },
          "then": {
            "properties": {
              "type": {
                "const": "image"
              }
            }
          }
        },
        {
          "if": {
            "required": [
              "subtype"
            ]
          },
          "then": {
            "properties": {
              "type": {
                "enum": [
                  "image",
                  "noise",
                  "group"
                ]
              }
            }
          }
        }
      ]
    }
  }
}
```

## 15. Examples

A short leave policy PDF in the storage form:

```json
{"type":"document","version":"0.4","doc":"leave_policy","source":"leave_policy.pdf","sha256":"af179a761f988e6a40d5154b3c3ce735ba94d23ebd82d8e24e3d80de4e2dda68","protection":"none","signed":false,"converter":"docling 2.x","structure":true,"elements":6,"created":"2026-09-26T10:30:00Z","lang":"en","access":["all"],"title":"Leave Policy","last_id":6}
{"id":"leave_policy#e1","hash":"b323ab53d73b48e7","type":"heading","level":1,"parent":null,"page":0,"bbox":[80,60,620,95],"characters":14,"md":"# Leave Policy"}
{"id":"leave_policy#e2","hash":"b91ad9f6b39e617a","type":"paragraph","parent":"leave_policy#e1","page":0,"bbox":[80,110,920,170],"characters":105,"md":"This policy applies to all full-time employees from their first day of work. See [Table 1](#leave-types)."}
{"id":"leave_policy#e3","hash":"79e15a433bf84d1c","type":"table","label":"leave-types","parent":"leave_policy#e1","page":0,"bbox":[80,190,700,330],"characters":89,"md":"| Leave type | Days per year |\n| --- | --- |\n| Sick leave | 12 |\n| Paternity leave | 15 |"}
{"id":"leave_policy#e4","hash":"fd6cd4502fca6a4a","type":"caption","parent":"leave_policy#e1","page":0,"bbox":[80,335,400,355],"characters":20,"reference":"leave_policy#e3","md":"Table 1: Leave types"}
{"id":"leave_policy#e5","hash":"8f843b2362f0d607","type":"image","subtype":"stamp","parent":"leave_policy#e1","page":0,"bbox":[700,820,900,940],"characters":66,"confidence":0.91,"file":"images/leave_policy_e5.png","md":"Round blue stamp reading \"Brightpath Technologies, HR Department\"."}
{"id":"leave_policy#e6","hash":"731af9f7a14feaf5","type":"noise","subtype":"footer","parent":"leave_policy#e1","page":0,"bbox":[460,960,540,980],"characters":6,"md":"Page 1"}
```

The same document in the authoring form:

```markdown
---
fmjl: "0.4"
doc: leave_policy
title: Leave Policy
lang: en
access: ["all"]
source: leave_policy.pdf
protection: none
signed: false
last_id: 6
---

<!-- e1 page=0 bbox=80,60,620,95 -->
# Leave Policy

<!-- e2 page=0 bbox=80,110,920,170 -->
This policy applies to all full-time employees from their first day of work. See [Table 1](#leave-types).

<!-- e3 label=leave-types page=0 bbox=80,190,700,330 -->
| Leave type | Days per year |
| --- | --- |
| Sick leave | 12 |
| Paternity leave | 15 |

<!-- e4 type=caption page=0 bbox=80,335,400,355 reference=e3 -->
Table 1: Leave types

<!-- e5 subtype=stamp page=0 bbox=700,820,900,940 confidence=0.91 -->
![Round blue stamp reading "Brightpath Technologies, HR Department".](images/leave_policy_e5.png)

<!-- e6 type=noise subtype=footer page=0 bbox=460,960,540,980 -->
Page 1
```

## 16. Tools

The reference tool `fmjl.py` has seven commands:

| Command | What it does |
| --- | --- |
| `python fmjl.py new notes.md` | Turns the authoring form into the storage form, `notes.fmjl` |
| `python fmjl.py md notes.fmjl` | Turns the storage form into the authoring form, `notes.md` |
| `python fmjl.py fill notes.fmjl` | Fills in `id`, `hash`, `characters`, and `parent`, and makes `md` canonical |
| `python fmjl.py check notes.fmjl` | Checks every rule and prints errors with line numbers |
| `python fmjl.py view notes.fmjl` | Prints the document as clean Markdown, without notes |
| `python fmjl.py info notes.fmjl` | Prints the title, element counts, and an outline |
| `python fmjl.py upgrade old.fmjl` | Turns a version 0.1, 0.2 or 0.3 file into version 0.4 |

It needs Python and two packages: `pip install markdown-it-py jsonschema`. Tools in other languages are welcome; they follow this rulebook, not the Python tool.

## 17. Version History

1. Version 0.1: first draft, with the extension `.jsonl`.
2. Version 0.2: the extension `.fmjl` and the `fmjl.py` tool.
3. Version 0.3: the authoring form; canonical Markdown; IDs that never change; labels; the `group` type; `continues`; `meta`; header fields `title`, `authors`, `date`, `summary`, and `last_id`; `elements` may be `null` while writing; JPG and SVG images; retrieval rules become recommendations; the rulebook becomes the authority over the tool.
4. Version 0.4: the format is named FMJL, short for Format, Markdown, JSON Lines; the placeholder name "Format X" is retired. No rules changed, so 0.3 files stay valid.

Moving from 0.2 to 0.3: run `fmjl upgrade`. Some `md` texts change once into canonical form, so their hashes change and those elements are embedded again once.

## 18. Not Decided Yet

1. The license.
2. Version 1.0 will be released after the accuracy benchmark. From 1.0 on, every 1.x reader will read every 1.x file.
