# EMKA — Build Prompt Playbook

Copy-paste prompts for **Claude Code (`cc`)** to build the Expeditionary Medical Knowledge Assistant prototype. Sequenced so each step hands a clean interface to the next. Dev happens on the Mac mini; the fielded target is x86, so every prompt keeps the stack **hardware-portable** (llama.cpp/GGUF, no MLX-only or Mac-only dependencies).

**Ground rules to give `cc` once, up front (paste at the start of any session):**

```
Project: EMKA — air-gapped, retrieval-augmented medical reference for deployed use.
Hard constraints for everything you build:
- FULLY OFFLINE at runtime. No network calls, no telemetry, no update checks, no cloud APIs. If a library phones home, don't use it.
- HARDWARE-PORTABLE. Dev is macOS (Apple Silicon) but the target is x86 Linux. Use llama.cpp/GGUF, not MLX. No OS-specific paths or deps.
- NO PHI EVER. This system indexes reference documents only. No patient-data fields, storage, or code paths.
- CITATION FIDELITY IS THE POINT. Every answer traces to specific source chunks with pub/edition/paragraph/page and byte offsets into the source PDF.
- Source of truth for what to ingest is EMKA_Corpus_Manifest.xlsx. Read it; don't invent a corpus.
- Read DESIGN.md before writing code. Keep it updated as the architecture evolves.
Ask before adding any dependency that isn't pure-Python or a well-known offline package.
```

---

## Phase A — Scaffold (dispatchable; do #1 first, then #2)

### Prompt 1 — Repo scaffold + DESIGN.md
```
Scaffold a monorepo for EMKA with these packages:
  ingest/       PDF -> structured, cited chunks
  retrieval/    hybrid BM25 + dense + reranker
  generate/     grounded synthesis + verification
  capability/   formulary/AMAL/capability data for resource-aware inference
  api/          FastAPI service
  web/          React front end (Vite)
  eval/         gold-standard question harness
  corpus/       (gitignored) source PDFs, two subdirs: authoritative/ and unit/
  models/       (gitignored) GGUF weights + embedding/reranker models
Use Python 3.11+ with uv for env management, pyproject.toml, ruff + pytest.
Create a Makefile with targets: setup, ingest, index, serve, web, eval, smoke.
Write DESIGN.md capturing: the RAG-not-fine-tune rationale, the authority-tier
precedence (T1 command > T2 service/DHA > T3 CPG > T4 doctrine > T5 reference),
the two-shelf model (authoritative vs unit, with watermarking), the verification
layer, and resource-aware inference. Add a .gitignore that excludes corpus/ and models/.
Do NOT implement components yet — just the skeleton, interfaces, and DESIGN.md.
```

### Prompt 2 — Local model + embeddings smoke test (needs #1)
```
Set up fully-offline inference and verify it. Use llama.cpp (via llama-cpp-python)
with a GGUF chat model (default: Qwen2.5-14B-Instruct Q4_K_M for dev; make the
model path a config value so we can swap to a 70B Q4 on the x86 target).
Add local embeddings (bge-m3) and a local reranker (bge-reranker-v2-m3) via
sentence-transformers with local model files only.
Write a `make smoke` target and scripts/smoke.py that:
  1) loads the chat model and generates a 20-token completion,
  2) embeds two strings and prints cosine similarity,
  3) reranks 3 candidate passages against a query,
and asserts all three run with the network disabled. Print model paths + versions.
Document in DESIGN.md exactly which model files must be pre-staged on the device.
```

---

## Phase B — Ingestion (checkpoint after #3: lock the chunk schema)

### Prompt 3 — Ingestion pipeline with citation metadata
```
Build ingest/ : a manifest-driven pipeline that turns a source PDF into cited chunks.
For each PDF:
  - extract text with layout awareness (pymupdf); OCR fallback (ocrmypdf/tesseract)
    for image-only pages, all local.
  - parse doctrine numbering into a heading breadcrumb (e.g. "NTTP 4-02 > Ch 3 > 3.2.1 > p.3-7").
  - chunk at paragraph level, ~200-500 tokens, with breadcrumb prepended and overlap;
    NEVER split a table or a dosing/algorithm block — keep those intact.
  - attach metadata to every chunk: doc_id, title, pub_number, edition_date,
    authority_tier (T1-T5), shelf (authoritative|unit), distribution_stmt, category,
    rights_posture, source_sha256, page, char_start, char_end (byte offsets into the PDF text),
    breadcrumb.
Persist chunks as JSONL plus a manifest of ingested docs (id, hash, status).
Write a golden test on 1-2 sample JTS CPG PDFs asserting breadcrumb + offsets are correct.
Output the finalized chunk schema as a dataclass and document it in DESIGN.md — this is the
contract every later component depends on, so make it explicit.
```

### Prompt 4 — Manifest loader + ingest queue (needs #3)
```
Build a loader that reads EMKA_Corpus_Manifest.xlsx (openpyxl) and produces the ingest
work queue. For each row: capture Ref ID, title, tier, shelf, rights, phase, status.
Filter to Phase "0 - Core" and shelf=authoritative for the first build.
Match manifest rows to PDFs in corpus/authoritative/ by a filename convention you define
and document. Report: matched, missing-file, and rights-gated (©-LIC / VERIFY) rows —
the last group should be listed and SKIPPED, not ingested. Set each ingested row's status
and record its sha256 back to a local ingest-log (CSV or SQLite), never to the xlsx itself.
```

---

## Phase C — Retrieval & verification (dispatch #5 and #6 in parallel after schema is locked)

### Prompt 5 — Hybrid retrieval + abstention
```
Build retrieval/ over the chunk store. Index chunks two ways:
  - dense vectors in LanceDB (bge-m3 embeddings),
  - keyword full-text (SQLite FTS5 or tantivy).
Implement hybrid search: run both, fuse (reciprocal rank fusion), rerank top ~30 with
bge-reranker, return top 6-12 chunks WITH full citation metadata and a retrieval_confidence
score. Add an abstention gate: if top reranker score < configurable threshold, flag
"insufficient corpus support" so generation can refuse. Include authority-tier and
edition_date in results so downstream can order by precedence/recency.
Write tests: exact-term doctrine query (should favor BM25) and a semantic clinical query.
```

### Prompt 6 — Verbatim verification layer
```
Build generate/verify.py : after synthesis, extract every quoted span from the answer
(spans the model marked as verbatim quotes) and verify each one character-for-character
against the cited source chunk, using the stored byte offsets to confirm location.
Return a per-quote pass/fail plus overall integrity. On any failure: trigger one
regeneration; if it still fails, return the raw retrieved passages WITH a flag instead
of a synthesized answer (fail safe, never fabricate). Unit-test with a deliberately
altered quote (must fail) and an exact quote (must pass).
```

---

## Phase D — Generation & resource-aware inference (needs #5, #6)

### Prompt 7 — Grounded synthesis + capability matching
```
Build generate/answer.py orchestrating: retrieve -> synthesize -> verify -> assemble.
Synthesis prompt rules (put in a versioned prompt file):
  - Answer ONLY from the provided passages. Quote exactly and cite pub/edition/paragraph/page.
  - If passages conflict, present both with dates and flag the conflict; order by authority tier.
  - If retrieval abstained or corpus lacks it, say so plainly — do NOT improvise.
Wire in capability/: load the unit formulary + Role1/2/3 capability matrix (see Prompt 8).
When a recommended first-line drug/procedure isn't in the loadout, surface the SOURCE'S OWN
stated alternative and show BOTH the clinical passage and the availability datum. Never invent
a substitution or a dose. Return a structured result: {synthesis, sources[], citations[],
conflicts[], capability_notes[], verification, abstained}.
```

---

## Phase E — Serve & UI (needs #7)

### Prompt 8 — Capability/formulary loader (dispatchable earlier if you want)
```
Build capability/ : loaders for the non-PHI "what's on hand" data from the manifest's
Capability & Formulary tab and unit files — formulary (drug -> stocked? by role),
AMAL/ADAL equipment, Role 1/2/3 capability matrix, blood posture, evac-timeline factors.
Store as simple queryable structures with an as-of date and source. Expose a
`match(recommendation, context)` helper the generator uses. Add tests for the core case:
first-line item absent -> returns availability=false so a cited alternative can be surfaced.
Treat a stale as-of date as a defect (warn loudly).
```

### Prompt 9 — FastAPI backend
```
Build api/ : FastAPI service, localhost/isolated-LAN only, no external calls.
Endpoints:
  POST /query {question} -> full structured result from generate/answer.py
  POST /corpus/refresh -> re-run manifest loader + reindex (maintainer action)
  GET  /source/{doc_id}/page/{n} -> serve the source PDF at a page for tap-to-open
  GET  /health
Log every query (question, retrieved source ids, answer, verification result, latency) to
a local store — NEVER any patient data. Add a persistent no-PHI notice in responses.
```

### Prompt 10 — React front end
```
Build web/ (Vite + React, Tailwind). Query box + results view where SOURCES ARE PRIMARY:
show verbatim passages with citations (pub/edition/paragraph/page) FIRST, synthesized answer
SECOND and visibly subordinate. Every citation is tap-to-open the PDF at that page.
Requirements: persistent no-PHI banner; corpus edition/date shown on every citation;
unit-shelf sources visually WATERMARKED "unit-added, not custodian-verified" in a distinct
color; conflicting sources rendered side-by-side under a "these sources differ" flag;
an in-UI "flag this answer" control that logs to the maintainer queue. No browser storage
of anything sensitive; keep state in memory.
```

---

## Phase F — Eval & governance (dispatchable; build #11 early, run continuously)

### Prompt 11 — Gold-standard eval harness
```
Build eval/ : a harness that runs a set of question–answer–citation triples (start with a
YAML/CSV of ~30 seed cases across IDC / Role 2 / planner / DNBI, including deliberately
out-of-corpus and ambiguous questions). For each case compute: retrieval recall@10,
citation accuracy, verbatim-quote integrity, grounded-answer rate (needs a rubric field),
honest-abstention rate, and latency. Emit a scored report and a non-zero exit code if any
metric falls below configurable thresholds — so it can gate every corpus/software change.
Make it trivial to add cases. Document the metric definitions in DESIGN.md.
```

---

## Running these "on dispatch" (parallel agent runs)

If you're using background/agent dispatch rather than an interactive session:

- **Safe to dispatch in parallel from the start:** Prompt 1 (scaffold), then after it lands, Prompt 11 (eval harness — it only needs the interfaces) and Prompt 8 (capability loader) can run alongside Phase B/C work.
- **Must be sequential / checkpoint first:**
  - #2 needs #1's structure.
  - #3 defines the **chunk schema** — stop and review it before dispatching #4, #5, #6, since they all bind to it. This is the one human checkpoint that saves the most rework.
  - #7 needs #5 and #6 merged and green.
  - #9/#10 need #7's result contract.
- **Give each dispatched run the "Ground rules" block above** plus "read DESIGN.md first" — background agents drift without the shared contract.
- **One task per PR-sized unit.** Each prompt above is roughly one reviewable change; don't dispatch two schema-touching prompts against the same files at once (merge conflicts + last-write-wins on the chunk contract).

## `cc`-specific tips

- Keep `corpus/` and `models/` out of context — they're huge and gitignored. Point `cc` at the **manifest** and a couple of sample PDFs, not the whole library.
- After #3, tell `cc`: "the chunk schema in DESIGN.md is frozen; propose a migration if you need to change it" — prevents silent contract drift.
- Start each session with the Ground rules block; end each with "update DESIGN.md and the Makefile if anything changed."
- First milestone to aim for: **#1 → #2 → #3 → #4 → #5 → #7 (minimal) → #9 → #10** gives an end-to-end demo on the ~40 Phase-0 PDFs. Add #6 verification and #11 eval before anyone trusts an answer.
