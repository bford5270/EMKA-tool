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
defined as a dataclass in `core/schema.py` and documented here when Prompt 3 lands.
After that point the schema is FROZEN — changes require an explicit migration
proposal in this document.

> **Status: schema not yet frozen** — placeholder until the ingestion prompt (#3)
> is complete. Required fields per the playbook: `doc_id, title, pub_number,
> edition_date, authority_tier (T1–T5), shelf, distribution_stmt, category,
> rights_posture, source_sha256, page, char_start, char_end, breadcrumb` plus the
> chunk text itself.

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
- **Verbatim verification** (`generate/verify.py`): every span the model marks as a
  quote is checked character-for-character against the cited chunk at its stored
  offsets. Any failure triggers one regeneration; a second failure returns the raw
  retrieved passages with a flag instead of a synthesized answer. **Fail safe,
  never fabricate.**

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

(Exact staged file list is documented in `models/README.md` once Prompt 2 lands.)

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

`eval/` runs gold-standard question–answer–citation triples (seed set:
`eval/seed_cases.yaml`) and computes: retrieval recall@10, citation accuracy,
verbatim-quote integrity, grounded-answer rate, honest-abstention rate, latency.
It exits non-zero when any metric falls below its configured threshold, so it can
gate every corpus and software change. Metric definitions live in `eval/README.md`
and are elaborated here when the harness (Prompt 11) lands. **A confident wrong
answer is a critical failure; an honest "not in corpus" is a pass.**

## 11. Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-11 | Scaffold at repo root; run-in-place (uv, no packaging) | Matches playbook layout; avoids installing a top-level `eval` package |
| 2026-07-11 | Swap Qwen/bge stack for Phi-4/nomic/mxbai | US/allied-origin weights required for fielding; architecture unaffected |
| 2026-07-11 | Added `core/` shared-contract package | Chunk schema + config need one home that ingest/retrieval/generate can all import without cross-dependencies |
