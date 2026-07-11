# EMKA — Expeditionary Medical Knowledge Assistant

An air-gapped, retrieval-augmented reference system for doctrine and clinical decision support in denied, degraded, intermittent, and limited-bandwidth (DDIL) environments.

A corpsman, IDC, provider, or medical planner asks a plain-language question; the system retrieves the relevant passages from an authoritative, government-owned/open corpus, quotes them verbatim with pinpoint citations (publication, edition, paragraph, page), and synthesizes a direct answer. Every quoted passage is machine-verified against its source before display. **The device requires no network connection of any kind after provisioning.**

## Design principles

- **Retrieval, not fine-tuning.** The model reasons over an auditable document library; it does not recall from weights. This is what makes verbatim citation and easy corpus updates possible.
- **PHI-free by design.** The system indexes reference documents only. No patient data enters the device.
- **Citation fidelity is the point.** Every answer traces to specific source chunks with byte-offset traceability into the source PDF. A post-generation verifier guarantees every displayed quote exists verbatim at its cited location.
- **Resource-aware.** The system reasons over the querying element's actual loadout (formulary, AMAL, capability tier) and surfaces a source's own cited alternative when first-line is unavailable — never an invented substitution.
- **Fully offline, hardware-portable.** Dev on Apple Silicon; target is x86 Linux. llama.cpp/GGUF throughout — nothing Mac-only.

## Repository layout

```
docs/
  EMKA_Framework_HSOAG.md      Capability concept paper — renders inline on GitHub (read this first)
  EMKA_Framework_HSOAG.docx    Same paper, formatted Word version (authoritative for briefing)
  EMKA_Build_Prompts.md        Sequenced Claude Code prompts to build the prototype
  EMKA_Corpus_Manifest.xlsx    Curated 227-item corpus ingestion tracker (source of truth for ingest)
eval/
  seed_cases.yaml              Gold-standard question–answer–citation triples
  README.md                    Eval schema, metrics, and SME governance
```

The build packages (`ingest/`, `retrieval/`, `generate/`, `capability/`, `api/`, `web/`, `eval/`) are created by working through `docs/EMKA_Build_Prompts.md`. `corpus/` and `models/` are gitignored — source PDFs and model weights are staged on the device, never committed.

## Getting started

1. Read `docs/EMKA_Framework_HSOAG.md` for the full concept and accreditation posture (or the `.docx` for the formatted version).
2. Open `docs/EMKA_Build_Prompts.md` and run the prompts in sequence in Claude Code (`cc`). Start with the ground-rules block, then Prompt 1.
3. The one human checkpoint that saves the most rework: **freeze the chunk schema after Prompt 3** before dispatching downstream work.
4. Wire the seed eval set (`eval/seed_cases.yaml`) into Prompt 11's harness so answers are scored from day one.

## Status

Prototype scaffold. Design docs and gold-standard eval seed complete; build in progress.

## Governance

Corpus curation, conflict handling, the two-shelf (authoritative vs. unit) model, and the SME custodian role are defined in the concept paper (§7) and the manifest README tab. The eval set is authored and validated by the clinical SME panel; entries marked `sme_verify` require confirmation against the cited source before the case is treated as authoritative.

*Contains no PHI/PII and no classified information.*
