# EMKA — System Design

Living architecture document. **Read this before writing code; update it when the
architecture changes.** The concept paper (`docs/EMKA_Framework_HSOAG.md`) is the
"why"; this document is the "how".

## 1. Mission and hard constraints

EMKA is an air-gapped, retrieval-augmented medical reference for deployed use. A
corpsman, IDC, provider, or planner asks a plain-language question; the system
retrieves passages from an authoritative corpus, quotes them verbatim with pinpoint
citations, and synthesizes a subordinate answer.

Non-negotiable constraints (every component inherits these):

1. **Fully offline at runtime.** No network calls, telemetry, update checks, or
   cloud APIs. Libraries that phone home are excluded. Network is permitted only
   at provisioning time (`make setup`, `make models`).
2. **Hardware-portable.** Dev happens on macOS (Apple Silicon) or Linux; the fielded
   target is x86 Linux. Inference is llama.cpp/GGUF — no MLX, no CUDA-only or
   OS-specific dependencies.
3. **No PHI, ever.** The system indexes reference documents only. There are no
   patient-data fields, storage, or code paths anywhere in this repo.
4. **Citation fidelity is the point.** Every answer traces to specific source chunks
   with pub/edition/paragraph/page and character offsets into the extracted source
   text. Displayed quotes are machine-verified before display.
5. **The corpus manifest is the source of truth** for what gets ingested
   (`docs/EMKA_Corpus_Manifest.xlsx`). Code never invents a corpus.

## 2. Why RAG, not fine-tuning

- **Verbatim citation requires retrieval.** A fine-tuned model recalls from weights
  and cannot point at the paragraph it is paraphrasing. Retrieval keeps the source
  text in hand, so quotes can be checked character-for-character (§6).
- **Corpus updates are file operations, not training runs.** Doctrine and CPGs change
  on their own schedule; swapping a PDF and re-indexing takes minutes on-device.
  Fine-tuning would require a training pipeline the field does not have.
- **Auditability.** A skeptical provider can open the cited PDF at the cited page.
  The trust model is "verify me", not "believe me".
- **Failure is visible.** When retrieval finds nothing, the system abstains
  ("insufficient corpus support") instead of hallucinating from weights.

## 3. Authority-tier precedence

Every document carries an authority tier assigned at ingestion, plus an effective
(edition) date. Precedence, highest first:

| Tier | Meaning | Examples |
|------|---------|----------|
| T1 | Command order / command SOP | MEF/unit orders, command-approved SOPs |
| T2 | Service / DHA policy | BUMED instructions, DHA policy memos |
| T3 | Current clinical practice guideline | JTS CPGs, TCCC guidelines |
| T4 | Doctrinal publication | NTTP 4-02, MCTP series |
| T5 | Reference text | Open clinical references, textbooks |

Rules:

- **Surface, don't arbitrate.** When retrieved passages materially disagree, present
  both verbatim, side by side, with edition and date, under an explicit "these
  sources differ" flag. Presentation may be ordered by precedence and recency;
  neither passage may be suppressed.
- **Conflicts are logged** to the maintainer/custodian queue — a conflict either
  reflects a deliberate local deviation (fine) or a superseded document that
  survived an update cycle (a corpus defect to fix).

## 4. The two-shelf model

The corpus has exactly two shelves, physically separated on disk and in metadata:

- `corpus/authoritative/` — custodian-approved, manifest-tracked publications.
- `corpus/unit/` — unit-added material (local SOPs, command guidance) that has NOT
  passed custodian review.

Every chunk carries `shelf: authoritative | unit`. Unit-shelf content is **always
watermarked** in results and in the UI: "unit-added, not custodian-verified",
rendered in a distinct color. The invariant the two-shelf model protects: *an
unwatermarked citation always means machine-verified text from a custodian-approved
source.* Capability/formulary data (§7) is governed as unit-shelf content.

## 5. Ingestion and the chunk contract

`ingest/` turns manifest-listed PDFs into cited chunks:

- Layout-aware text extraction (PyMuPDF) with local OCR fallback for image-only pages.
- Doctrine numbering parsed into a heading breadcrumb
  (e.g. `NTTP 4-02 > Ch 3 > 3.2.1 > p.3-7`).
- Paragraph-level chunks (~200–500 tokens) with breadcrumb prepended and overlap.
  **Tables and dosing/algorithm blocks are never split.**
- Chunks persist as JSONL plus an ingest manifest (doc id, sha256, status).

**The chunk schema is the contract every downstream component binds to.** It is
defined as `core.schema.Chunk` and is **FROZEN as of Prompt 3 (v1.0)** — changes
require an explicit migration proposal in this document.

```
Chunk v1.0
  chunk_id: str            f"{doc_id}:{seq:05d}"
  doc_id: str              manifest Ref ID (e.g. "CPG-03")
  seq: int                 0-based position within the document
  title, pub_number, edition_date: str
  authority_tier: str      T1..T5          shelf: str  authoritative|unit
  distribution_stmt, category, rights_posture: str
  source_sha256: str       sha256 of the source PDF file
  page: int                1-based PDF page where the chunk starts
  char_start, char_end: int   offsets into the CANONICAL EXTRACTED TEXT
  breadcrumb: str          e.g. "NTTP 4-02 > Ch 3 > 3.2.1 > p.37"
  text: str                exact canonical-text slice (verbatim)
  is_atomic: bool          table/dosing/algorithm block, never split
  token_est: int
  schema_version: str      "1.0"
```

Contract details:

- **Canonical text**: `ingest.extract.extract_document` emits each page's
  layout-sorted text joined by form feeds. The invariant every verifier relies
  on: `canonical_text[char_start:char_end] == chunk.text`, byte-for-byte.
- **Deliberate deviation from the playbook**: offsets are *character* offsets
  into the canonical extracted text, not byte offsets into the raw PDF —
  Python-native, deterministic, and UTF-8 byte offsets remain derivable.
- **Section alignment beats target size**: a recognized heading always starts
  a new chunk, so breadcrumbs are exact even when that yields chunks under
  200 tokens. One-paragraph overlap applies only within a section.
- **Atomic blocks**: dosing/column/step patterns (including tables whose rows
  extract as separate one-line blocks) are merged and never split, even when
  oversized.
- **Retrieval indexes `chunk.embed_text`** (breadcrumb + text); **verification
  always checks `chunk.text`**.
- OCR: image-only pages use local `tesseract` when installed (a device
  provisioning requirement); otherwise the page is flagged in
  `ingest_manifest.json:ocr_missing_pages` — a visible defect, never silent.

## 6. Retrieval, generation, and the verification layer

Pipeline: **retrieve → synthesize → verify → assemble**.

- **Hybrid retrieval** (`retrieval/`): dense vectors (LanceDB) + keyword FTS
  (SQLite FTS5), fused with reciprocal rank fusion, reranked by a local
  cross-encoder. Returns top 6–12 chunks with full citation metadata and a
  `retrieval_confidence` score.
- **Abstention gate**: if the top reranker score is below a configurable threshold,
  retrieval flags "insufficient corpus support" and generation must refuse rather
  than improvise.
- **Grounded synthesis** (`generate/`): the model answers ONLY from provided
  passages, quotes exactly, cites pub/edition/paragraph/page, and presents conflicts
  per §3. Prompts are versioned files, not inline strings.
- **Verbatim verification** (`generate/verify.py`): the synthesis prompt requires
  every verbatim quotation to be tagged `<quote src="CHUNK_ID">…</quote>`. Every
  tagged span is then verified against the cited chunk, and — when the corpus
  canonical text is available — re-confirmed at its absolute stored offsets.
  Pass modes: `exact` (character-for-character) or `ws_normalized` (identical
  after collapsing whitespace runs; PDF extraction breaks lines mid-sentence, so
  this documented relaxation still requires every non-whitespace character to
  match exactly, in order, contiguously). Any other difference fails. Any failure
  triggers one regeneration; a second failure returns the raw retrieved passages
  with a flag instead of a synthesized answer. **Fail safe, never fabricate.**

## 7. Resource-aware inference

`capability/` loads the non-PHI "what's on hand" picture: unit formulary (drug →
stocked, by role), AMAL/ADAL equipment, Role 1/2/3 capability matrix, blood
posture, and evac-timeline factors — each with an as-of date and source. When a
retrieved recommendation's first-line item is not in the loadout, the system
surfaces the **source's own stated alternative** alongside both the clinical
passage and the availability datum. It never invents a substitution or a dose.
A stale as-of date is a defect and is warned about loudly.

## 8. Model stack

All models run from local files staged in `models/` at provisioning time. Model
paths and parameters are config values (`core/config.py`), never hard-coded, so the
same code runs the dev model on the dev box and the larger model on the target.

**Provenance decision (2026-07):** the original playbook suggested Qwen 2.5
(Alibaba) and the BAAI bge family (Beijing Academy of AI). Project direction is to
field US/allied-origin open-weights models instead. Architecture is unchanged —
llama.cpp/GGUF and sentence-transformers are model-agnostic — only the configured
weights differ.

| Role | Dev (this repo's default) | Fielded target (x86) | Origin / license |
|------|---------------------------|----------------------|------------------|
| Chat model | Phi-4-mini-instruct, Q4_K_M GGUF (3.8B) | Phi-4 (14B) Q4_K_M GGUF; Tier-2 devices may run larger | Microsoft (US), MIT |
| Embeddings | nomic-embed-text-v1.5 | same | Nomic AI (US), Apache-2.0 |
| Reranker | mxbai-rerank-base-v1 | mxbai-rerank-large-v1 | Mixedbread (DE), Apache-2.0 |

Exact staged file list: `models/README.md`. Provisioning is `make models`
(the only networked step); `make smoke` then proves chat, embedding, and
reranking all run with a socket-level network kill switch installed.

**Backend abstraction (`core/models.py`).** Retrieval/generation/eval consume
`ChatModel` / `Embedder` / `Reranker` interfaces. Real backends (llama.cpp,
sentence-transformers) load from staged local files only. Deterministic STUB
backends exist for development environments where weights cannot be staged
(CI, restricted-egress cloud sessions); they are gated behind
`EMKA_ALLOW_STUB_MODELS=1`, announce themselves on stderr, and are never
acceptable on a fielded device — `make smoke` accepts only real backends.

## 9. Repository layout

```
core/         shared contracts: config, chunk schema, authority tiers
ingest/       PDF -> structured, cited chunks
retrieval/    hybrid BM25 + dense + reranker, abstention gate
generate/     grounded synthesis + verbatim verification
capability/   formulary/AMAL/capability data for resource-aware inference
api/          FastAPI service (localhost / isolated LAN only)
web/          React front end (Vite + Tailwind)
eval/         gold-standard question harness + seed cases
scripts/      provisioning + smoke-test entry points
corpus/       (gitignored) source PDFs: authoritative/ and unit/
models/       (gitignored) GGUF weights + embedding/reranker models
docs/         concept paper, build playbook, corpus manifest
tests/        pytest suite (mirrors package layout)
```

`core/` exists so downstream packages depend on one shared contract module instead
of importing each other; it holds no business logic.

## 10. Evaluation gate

`eval/run.py` (`make eval`) runs every case in `eval/seed_cases.yaml` through the
full answer pipeline and exits non-zero on any threshold breach (thresholds live
in the YAML metadata; `--report-only` disables gating). **A confident wrong
answer is a critical failure; an honest "not in corpus" is a pass.**

Metric definitions (as implemented):

| Metric | Definition | Population |
|---|---|---|
| `retrieval_recall_at_10` | any `expected_source_ref` doc id appears among the doc ids of the top-10 returned sources | cases with a non-empty `expected_source_ref` |
| `citation_accuracy` | the answer displays ≥1 verifier-passed citation AND every passed citation's doc id is in `expected_source_ref` | `expected_behavior: answer` |
| `verbatim_quote_integrity` | displayed quotes passed the verifier — synthesized mode requires `integrity=true`; `raw_passages`/`abstained` display no quotes (the verifier caught the failure), so they count as intact | `expected_behavior: answer` |
| `grounded_answer_rate` | `answer_must_include` rubric satisfied. Default grader is deterministic keyword coverage (≥50 % of an element's content words present; case passes at ≥60 % of elements) — an approximation flagged in the report. `--grader=model` uses the local chat model per element (device use) | `expected_behavior: answer`, synthesized mode (non-synthesized = not grounded) |
| `honest_abstention_rate` | the system abstained rather than improvising | `expected_behavior: abstain` |
| `latency_seconds_max` | max query-to-answer wall time | all cases |

Cases with a `context` block (resource-matching / capability-limit) run against
an ephemeral loadout built from that context, so availability logic is
exercised without touching staged unit files. The JSON report lands at
`data/eval_report.json`; stub-model runs are watermarked in the report and
console output — their numbers exercise mechanics, never quality gates.

## 11. Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-11 | Scaffold at repo root; run-in-place (uv, no packaging) | Matches playbook layout; avoids installing a top-level `eval` package |
| 2026-07-11 | Swap Qwen/bge stack for Phi-4/nomic/mxbai | US/allied-origin weights required for fielding; architecture unaffected |
| 2026-07-11 | Added `core/` shared-contract package | Chunk schema + config need one home that ingest/retrieval/generate can all import without cross-dependencies |
