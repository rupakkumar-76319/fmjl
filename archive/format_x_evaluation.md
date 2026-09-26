# Format X (.fmjl) v0.2 — Unbiased Evaluation

## Overview

Format X is a document decomposition format that breaks any document into atomic, addressable **elements** (one JSON object per line) for use in RAG pipelines. It combines **4 languages**: JSON Lines (container), Markdown (text), LaTeX (math), and HTML (complex tables).

This evaluation covers the complete 15-section spec, the embedded JSON Schema (draft 2020-12), the example, and the tooling story.

---

## ✅ PROS

### 1. Container choice is near-optimal
JSON Lines is the right call for this use case. It's streamable, line-by-line processable, requires no custom parser, and every programming language has native JSON support. You can `grep`, `wc -l`, `head`, `tail`, and `jq` your way through a Format X file with zero tooling. This is a significant advantage over XML-based alternatives (ALTO, PAGE XML) or proprietary binary formats.

### 2. Markdown as the content language is LLM-native
LLMs are trained on billions of tokens of Markdown. By storing all readable content in `md`, retrieved chunks are **immediately usable in prompts** without format conversion. This is a genuine insight — most document formats (PDF internals, DOCX XML, HTML) require a conversion step before an LLM can use them. Format X eliminates that step entirely.

### 3. Incremental re-embedding via content hashing
The `hash` design (SHA-256 of `type + \n + md`, truncated to 16 hex) means that when a document is re-processed, only elements whose content actually changed need new vector embeddings. At scale (millions of documents re-ingested periodically), this saves **substantial compute cost**. This is the kind of design decision that separates a production-ready format from an academic exercise.

### 4. Comprehensive element taxonomy (19 types)
The type system is surprisingly thorough. It covers:
- **Standard document parts**: heading, paragraph, list, table, code, formula, image, caption, footnote, quote, toc, citation
- **Enterprise/legal**: form_field, redaction, annotation
- **Noise**: page headers, footers, watermarks, page numbers (captured but excluded from search)
- **Non-document content**: message (email/chat), utterance (transcripts), record (CSV/JSON rows)

This means the format can represent PDFs, emails, chat logs, call transcripts, spreadsheets, and forms — not just traditional documents.

### 5. Element-level access control
The `access` field exists on both the header (default) and individual elements (override). This means a single document can have sections restricted to different groups. For enterprise RAG where HR documents, financial reports, and legal contracts coexist, this is **essential** and almost no other format considers it.

### 6. Confidence scores for OCR/AI content
Elements extracted via OCR or AI models carry a `confidence` score (0–1). The retrieval rules (Section 9) specify that low-confidence answers should show the original page region. This is honest engineering — the format acknowledges its own uncertainty rather than pretending everything is perfect.

### 7. Forward-compatibility rules (Section 10)
Three rules borrowed from mature protocols:
1. *Readers ignore unknown fields* — new fields don't break old readers
2. *Unknown types are treated as `paragraph`* — new types degrade gracefully
3. *Any 0.x reader can read any 0.x file* — minor versions are backward-compatible

These are exactly the right rules for a format that will evolve. Many formats get this wrong.

### 8. Formal JSON Schema embedded in the spec
A complete JSON Schema (draft 2020-12) is part of the rulebook itself (Section 11). Validation is machine-checkable from day one, not just prose that humans must interpret. The schema also includes bidirectional field constraints (`heading → requires level` AND `level → requires heading type`), which prevents nonsensical combinations.

### 9. Non-destructive by design
The storage layout mandates keeping the original file in an `original/` folder. The format never claims to replace the source document — it's a structured index alongside it. This means nothing is ever lost, and the original can always be consulted.

### 10. Self-dogfooding
The rulebook itself is stored in Format X format. The spec describes itself using its own format. This is a good confidence signal — the authors eat their own cooking, and it proves the format can represent a real-world document.

### 11. Normalized bounding boxes
`bbox` uses integer coordinates from 0 to 1000 (page-relative). No floating-point precision issues, no page-size dependency, and simple enough to compute intersection/containment with integer math.

### 12. Simplicity
The entire format spec fits in 64 elements / ~31KB. A developer can read and understand the full specification in 20–30 minutes. Compare this to PDF (1,310 pages), OOXML (6,546 pages), or even ALTO XML (dozens of pages). Simplicity is a feature.

---

## ❌ CONS

### 1. Pre-alpha maturity (Critical)
The spec says *"Status: draft"*, the name "Format X" is a placeholder, and the license is undecided. There is no stability guarantee. Building production systems on v0.2 of a format that hasn't even decided its own name is risky. There's no commitment to backward compatibility beyond the 0.x family.

### 2. Markdown dialect is unspecified (Serious)
The spec says "Markdown" but doesn't specify which flavor: CommonMark, GFM (GitHub Flavored Markdown), original Markdown, or something else. The example uses GFM pipe tables, but this is never stated. **Practical impact**: two different converters could produce different Markdown for the same table, causing different hashes and duplicate embeddings. The hash design's value is undermined if the Markdown normalization isn't standardized.

### 3. LaTeX–Markdown collision risk (Moderate)
Inline math uses `$...$` inside the `md` field. But financial and business documents contain literal dollar signs: *"The price is $50 and the total is $100"*. The spec doesn't define escaping rules for this collision. A converter must decide: is `$50 and the total is $` a math expression or two dollar amounts? This is a known problem in every Markdown+LaTeX system, and the spec punts on it.

### 4. Extreme line lengths (Moderate)
A single element = a single line. The JSON Schema example (element e53) produces an `md` field of 8,170 characters — all on one line. A large table with 200 rows could produce lines of 50,000+ characters. Consequences:
- `git diff` becomes unreadable (one changed character shows the entire line as modified)
- Many text editors wrap or choke on extremely long lines
- `grep` output is unusable
- Code review tools truncate long lines

### 5. Flat hierarchy loses nesting (Moderate)
`parent` only points to the nearest heading. But real documents have:
- Lists inside table cells
- Blockquotes containing lists
- Footnotes referenced from specific list items
- Nested lists (sub-items)

The flat model forces a choice: either merge nested structures into one large element (losing granularity) or split them into separate elements (losing the nesting relationship). There's no way to represent "this list is inside this table cell."

### 6. No chunking strategy for large elements (Moderate)
The spec says *"A whole list is one element"* and tables are *"never split."* But a list with 100 items or a table with 500 rows creates a single massive element. For embedding, this can:
- Exceed model context windows
- Produce poor vector representations (too much semantic content in one vector)
- Cause uneven retrieval quality (small elements match better than large ones)

The format provides no sub-element mechanism or chunking guidance.

### 7. Dual representation ambiguity for tables (Minor-Moderate)
When a table has merged cells, it gets both `md` (Markdown table) and `html` (HTML table). But:
- Which is the canonical representation?
- If they disagree, which wins?
- Should embeddings use `md`, `html`, or both?

The spec doesn't answer these questions. Different RAG systems will make different choices, reducing interoperability.

### 8. Image format restriction (Minor-Moderate)
The schema enforces `^images/[^/]+\.(png|webp)$` — only PNG and WebP. No JPEG (the most common photograph format), no SVG (ideal for diagrams and charts), no TIFF (common in scanned documents). This seems unnecessarily restrictive and will force lossy format conversions.

### 9. No extension/metadata mechanism (Minor-Moderate)
There's no `meta`, `extra`, or `custom` field for converter-specific or domain-specific metadata. Enterprise deployments often need to attach:
- Document classification (confidential, public, internal)
- Review/approval status
- Department or project codes
- Custom NLP annotations

Adding these would violate the spirit of the schema (even though JSON Schema allows additional properties by default).

### 10. Header rewrite prevents streaming (Minor)
The header (line 1) contains `"elements": 64` — the total count. Adding an element requires updating this count, which means rewriting line 1. For streaming/real-time scenarios (live transcription, chat archival), you can't append elements without modifying the header. A trailer or separate manifest would solve this.

### 11. Hash truncation and collision risk (Minor)
16 hex chars = 64 bits of hash space. By the birthday paradox:
- At **1 million** elements: ~0.003% collision probability
- At **10 million** elements: collision becomes likely (~1 in 37)
- At **100 million** elements: near-certain collisions

For a single document, this is fine. For a large corpus using hashes as change-detection keys across all documents, 64 bits may be insufficient. Full SHA-256 (or at least 128 bits) would be safer.

### 12. Retrieval rules mixed with format spec (Design Concern)
Section 9 ("Retrieval Rules") tells systems *how* to search, what to embed, and how to cite. This mixes **data format** (what the file looks like) with **application behavior** (what to do with it). These are separate concerns. A retrieval system might have good reasons to embed `noise` elements or use a different citation format. Baking application logic into the format spec reduces flexibility.

### 13. Validity defined by tool, not spec (Design Concern)
Section 13 states: *"A file is valid only if `check` passes, whatever any person or AI says."* This means validity is defined by a specific Python implementation (`fmjl.py`), not by the spec. If the tool has bugs, buggy behavior becomes the "correct" interpretation. Standard practice is the opposite: the spec is authoritative, and tools are implementations that may have bugs.

### 14. No version negotiation or migration path
The spec says a 0.x reader can read any 0.x file, but there's no mechanism for:
- A converter to declare "I can output versions 0.1 and 0.2"
- A reader to signal which version it prefers
- Migrating a v0.1 file to v0.2

When 1.0 arrives, there's no defined upgrade path from 0.x files.

### 15. No diff/merge strategy for version control
Element IDs are sequential (`#e1`, `#e2`, ...). Inserting one element in the middle renumbers every subsequent element, changing every line. Combined with extreme line lengths (Con #4), this makes `git diff` and merge operations essentially useless. Two people cannot collaborate on the same Format X file using standard VCS workflows.

---

## Comparison to Alternatives

| Aspect | Format X | Docling JSON | Unstructured.io | ALTO XML | Plain Markdown |
|--------|----------|-------------|-----------------|----------|---------------|
| RAG-optimized | ✅ Primary goal | ⚠️ Secondary | ✅ Primary goal | ❌ OCR-focused | ❌ No metadata |
| Streamable | ✅ Line-by-line | ❌ Full JSON | ❌ Python objects | ❌ Full XML | ✅ |
| LLM-friendly content | ✅ Native Markdown | ⚠️ Needs conversion | ⚠️ Plain text | ❌ XML fragments | ✅ |
| Access control | ✅ Element-level | ❌ | ❌ | ❌ | ❌ |
| Page positions | ✅ bbox | ✅ | ✅ | ✅ Detailed | ❌ |
| Nested structure | ❌ Flat | ✅ Tree | ⚠️ Limited | ✅ | ❌ |
| Schema validation | ✅ JSON Schema | ⚠️ Pydantic | ❌ | ✅ XML Schema | ❌ |
| Tooling ecosystem | ❌ One tool | ⚠️ Growing | ✅ Mature | ✅ Mature | ✅ Ubiquitous |
| Maturity | ❌ v0.2 draft | ⚠️ Young | ✅ Production | ✅ Established | ✅ Decades |

---

## Summary Verdict

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Design philosophy** | 🟢 Strong | Right problem, right primitives, right constraints |
| **RAG fitness** | 🟢 Strong | Hash-based re-embedding, access control, confidence scores |
| **Simplicity** | 🟢 Strong | Full spec in 30 minutes; no custom parser needed |
| **Robustness** | 🟡 Mixed | Good schema, but Markdown dialect and LaTeX escaping are gaps |
| **Scalability** | 🟡 Mixed | Streaming limited by header rewrite; hash collisions at scale |
| **Interoperability** | 🟡 Mixed | Good forward-compat rules, but no extension mechanism |
| **Maturity** | 🔴 Weak | v0.2 draft, unnamed, unlicensed, single reference tool |
| **Collaboration** | 🔴 Weak | Sequential IDs + long lines make VCS workflows impractical |

**Bottom line**: Format X solves a real problem (RAG-ready document representation) with a genuinely clever design (JSONL + Markdown + content hashing). The 4-language combination is pragmatic, not over-engineered. The access control and confidence features show enterprise awareness. But it's a v0.2 draft with real gaps: unspecified Markdown dialect, no nesting, no extension mechanism, and VCS-hostile sequential IDs. It's a promising *design* that isn't yet a reliable *standard*.
