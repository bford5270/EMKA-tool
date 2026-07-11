# Capability Concept Paper

# Expeditionary Medical Knowledge Assistant (EMKA)

**An Air-Gapped, Retrieval-Augmented Reference System for Doctrine and Clinical Decision Support in Denied, Degraded, Intermittent, and Limited-Bandwidth (DDIL) Environments**

*Prepared for:* Health Services Operational Advisory Group (HSOAG)
*Prepared by:* CDR Brian S. Ford, MC, USN — Chief Medical Officer, 1st Medical Battalion, 1st Marine Logistics Group, I MEF
*July 2026 — Working Draft for Discussion*

> Working title; final nomenclature subject to sponsor guidance. This paper contains no classified information, no PHI/PII, and no proprietary vendor data.

> **Note:** This Markdown version exists so the paper renders inline on GitHub. The authoritative formatted version is `EMKA_Framework_HSOAG.docx` in this same directory.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement and Operational Need](#2-problem-statement-and-operational-need)
3. [Concept of Employment](#3-concept-of-employment)
4. [System Concept: Retrieval-Augmented Generation, Not Fine-Tuning](#4-system-concept-retrieval-augmented-generation-not-fine-tuning)
5. [Hardware Options Analysis](#5-hardware-options-analysis)
6. [Software Architecture](#6-software-architecture)
7. [Corpus Definition and Governance](#7-corpus-definition-and-governance)
8. [Ingestion Pipeline and Citation-Fidelity Design](#8-ingestion-pipeline-and-citation-fidelity-design)
9. [Security and Accreditation Pathway](#9-security-and-accreditation-pathway)
10. [Clinical Governance and Scope of Use](#10-clinical-governance-and-scope-of-use)
11. [Test and Evaluation Plan](#11-test-and-evaluation-plan)
12. [Sustainment and Update Concept](#12-sustainment-and-update-concept)
13. [Phased Implementation Roadmap](#13-phased-implementation-roadmap)
14. [Risks and Mitigations](#14-risks-and-mitigations)
15. [Recommendation and Request to HSOAG](#15-recommendation-and-request-to-hsoag)
- [Appendix A: Phase 0 Bill of Materials](#appendix-a-phase-0-bill-of-materials-representative)
- [Appendix B: Glossary](#appendix-b-glossary)

---

## 1. Executive Summary

Deployed medical personnel operate in environments where reach-back to clinical and doctrinal references is unreliable or impossible. Satellite bandwidth is contested, prioritized for command and control, and emissions-controlled. Yet the questions that arise at Role 1 and Role 2 — triage category definitions under a specific NTTP, walking blood bank activation criteria, antibiotic selection for a contaminated blast wound at 96 hours from evacuation — are answerable from documents the Navy already owns. The gap is not knowledge; it is access.

This paper proposes the Expeditionary Medical Knowledge Assistant (EMKA): a small, low-power, fully air-gapped computer that hosts a large language model coupled to a curated library of doctrine and clinical references through retrieval-augmented generation (RAG). A corpsman, Independent Duty Corpsman (IDC), provider, or medical planner types a plain-language question; the system retrieves the relevant passages from the authoritative library, quotes them verbatim with pinpoint citations (publication, chapter, paragraph, page), and synthesizes a direct answer. Every quoted passage is machine-verified against the source before display. The device requires no network connection of any kind after initial provisioning.

Three design decisions define the concept. First, the system retrieves and cites rather than recalls: the model is a reasoning and language layer over an auditable document library, not a repository of memorized facts. Second, the system is PHI-free by design: it stores and processes reference documents only, never patient data, which dramatically simplifies the security accreditation pathway. Third, the hardware is commodity, small-form-factor, and battery-operable, drawing 10–140 watts depending on tier — comparable to a laptop, not a server rack.

The paper recommends a three-phase path: a 90-day garrison prototype built on commercial hardware and government-owned publications (~$5–15K); a supervised field pilot with one Role 2 element and one battalion aid station during a major exercise; and a transition decision informed by measured retrieval accuracy, citation fidelity, and user trust. The prototype requires no new program of record, no network connectivity, and no PHI authority to operate.

---

## 2. Problem Statement and Operational Need

### 2.1 The Reference-Access Gap in DDIL Environments

Modern military medicine assumes connectivity. Clinical decision support, drug references, clinical practice guidelines, and doctrinal publications increasingly live on networked portals (JTS, MHS GENESIS knowledge resources, Navy Medicine SharePoint, NLL). In a contested Indo-Pacific scenario — the pacing environment for I MEF and the Marine Littoral Regiment construct — these assumptions fail in four ways:

- **Bandwidth denial and prioritization.** Available SATCOM is allocated to fires, C2, and logistics; medical reference queries will not compete successfully for kilobits.
- **Emissions control (EMCON).** Distributed maritime and stand-in force operations impose deliberate RF silence; any transmit-dependent tool is unusable for extended windows.
- **Latency and intermittency.** Even when links exist, retrieving a 40 MB PDF over a degraded link is impractical during a MASCAL.
- **Cognitive load under stress.** Static PDF libraries on a hard drive technically solve offline access but fail in practice: a provider at 0300 during a mass casualty event cannot page through NTTP 4-02 to find one paragraph. Search must be semantic, fast, and answer-oriented.

### 2.2 Who Feels the Gap

Three user populations, in ascending order of clinical depth and descending order of doctrinal depth:

- **Role 1 — IDCs and battalion aid station corpsmen.** Operate at the far edge of their scope with the least reach-back. Highest-value queries: TCCC and prolonged casualty care protocols, drug dosing, when-to-evacuate criteria.
- **Role 2 — physicians, PAs, nurses, and surgical teams at FRSS/ERSS and Role 2 LM.** Queries span clinical practice guidelines (JTS CPGs), emergency war surgery, blood product doctrine, and holding policy.
- **Medical planners and HSS leaders.** Doctrinal and planning queries: capability definitions, T/O and AMAL structures, patient movement planning factors, command relationships across NTTP 4-02 series, JP 4-02, and MEF-level orders.

A critical scope note: while combat casualty care draws the most attention, Disease and Non-Battle Injury (DNBI) historically accounts for the large majority of deployed medical encounters — sick call, primary care, environmental illness, infectious disease, behavioral health, and the specialty complaints that fill an aid station's day. A system built only for trauma would fail its most frequent use. EMKA's corpus is therefore deliberately dual: the Joint Trauma System clinical practice guidelines for casualty care, and an equally deep DNBI library built on VA/DoD Clinical Practice Guidelines, CDC field references, and open-licensed clinical references. Nearly all of this DNBI content is government-owned or openly licensed, so breadth of care adds capability without adding proportionate licensing burden.

### 2.3 Why Now

Two curves have crossed. Open-weight language models in the 8–70 billion parameter class now perform at a level suitable for grounded question-answering, and small-form-factor hardware capable of running them locally has become commodity — including embedded modules drawing under 60 watts and x86 mini-workstations with unified memory architectures. The entire software stack required (inference runtimes, embedding models, vector databases) is mature, open-source, and runs without any network connection. What was a research project in 2023 is an integration effort in 2026.

---

## 3. Concept of Employment

### 3.1 Operating Concept

EMKA is a self-contained appliance: a small computer (see Section 5) pre-loaded with the model, the retrieval stack, and the authoritative document corpus. It boots to a local web interface reachable from the device itself or from any laptop, tablet, or end-user device on the same isolated local network segment (or via direct Ethernet/USB tether where local Wi-Fi is prohibited under EMCON). It has no WAN interface. Radios and cellular hardware are physically absent or disabled at the firmware level.

A user types a question in plain language. The system returns, in under 30 seconds: (a) a direct answer synthesized from retrieved passages; (b) the verbatim source passages, visually primary in the interface; and (c) pinpoint citations — publication number, edition/date, chapter, paragraph, and page. The user can tap any citation to open the full source PDF at that page. The synthesized answer is explicitly framed as a pointer to the sources, not a replacement for them.

### 3.2 Representative Queries

| User | Representative query |
|---|---|
| IDC, Role 1 | "What are the TXA administration criteria and dosing under current TCCC guidelines, and what are the contraindications?" |
| Role 2 physician | "Summarize the JTS CPG on burn resuscitation for a 40% TBSA casualty when I have no burn flow sheet, and quote the fluid rate formula exactly." |
| Role 2 surgeon | "What does Emergency War Surgery say about damage-control laparotomy temporary closure options at a Role 2 with expected 48-hour holding?" |
| Medical planner | "Per NTTP 4-02 series doctrine, what are the capability differences between an FRSS and a Role 2 Light Maneuver, and what are the doctrinal holding capacities of each?" |
| HSS leader | "What are the walking blood bank activation authorities and pre-screening requirements, with citations?" |

### 3.3 Explicit Non-Goals

- EMKA does not touch patient data. It is a reference system. No PHI enters the device; the interface carries a persistent banner stating so, and the concept of employment prohibits entering patient identifiers into queries.
- EMKA does not make clinical decisions. It is decision support in the same category as a textbook with a very good index. The clinician remains the decision-maker; the interface design (sources primary, synthesis secondary) reinforces this.
- EMKA does not replace training. It assumes a trained user asking questions within their scope of practice.
- EMKA does not connect to any network beyond an isolated local segment, ever, in the deployed configuration.

---

## 4. System Concept: Retrieval-Augmented Generation, Not Fine-Tuning

A common intuition is to "train a model on Navy doctrine." This paper deliberately rejects fine-tuning as the primary mechanism, for five reasons:

- **Citation fidelity.** A fine-tuned model recalls from weights; it cannot reliably quote a paragraph verbatim or tell you which page it came from. RAG retrieves the actual text and hands it to the model, so verbatim quotation with pinpoint citation is the default behavior, and it is machine-checkable (Section 8).
- **Auditability.** With RAG, every answer traces to specific chunks of specific documents. A reviewer can verify any answer in seconds. Fine-tuned knowledge is unauditable by construction.
- **Currency.** Doctrine and CPGs change. Updating a RAG corpus is a file drop and a re-index measured in minutes; updating a fine-tune is a training run measured in days and dollars, with regression-testing burden each time.
- **Hallucination containment.** Grounding the model in retrieved text, instructing it to answer only from that text, and verifying quotes post-hoc bounds the hallucination problem in a way that pure generation cannot.
- **Cost and reproducibility.** RAG uses off-the-shelf open-weight models with no training infrastructure. The entire system can be rebuilt from a documented recipe.

Fine-tuning retains one legitimate future role: a light instruction-tune to teach the model the answer format, citation style, and military register (a "style tune," not a "knowledge tune"). This is a Phase 3 optimization, not a prerequisite.

---

## 5. Hardware Options Analysis

Requirements derived from the concept: small enough to move in a medical equipment case; operable from tactical power (vehicle DC, small inverter, battery bank); silent or near-silent; no network dependency; sufficient memory to host a capable quantized model plus the retrieval stack; and preferably x86 or a well-supported embedded platform for DoD software compatibility. Three viable classes exist, plus a fallback.

### 5.1 Option Comparison

| Class / example | Model class it runs well | Power draw | Size / weight | Notes |
|---|---|---|---|---|
| **A. Embedded AI module** — NVIDIA Jetson AGX Orin 64 GB (industrial variants available) | 8–14B quantized; 32B marginal | 15–60 W (configurable) | ~11×11×7 cm; <1 kg board | Palm-sized, battery-friendly, industrial temperature variants, mature CUDA stack. Best fit for Role 1 kit. |
| **B. x86 unified-memory mini-workstation** — AMD Ryzen AI Max ("Strix Halo") class, 128 GB unified memory (e.g., HP Z2 Mini G1a and equivalents) | 70B quantized (Q4); 32B fast | ~30–140 W | Mini-PC chassis, ~2–3 kg | The strongest overall fit: x86 (standard DoD imaging/STIG baselines), no discrete GPU, runs the largest useful models, single-box appliance. Best fit for Role 2 and planning cells. |
| **C. SFF workstation + low-power GPU** — mini-tower with NVIDIA RTX 4000 SFF Ada (20 GB, 70 W) | 14B fast in VRAM; 32B with offload | ~150–250 W total | SFF tower, ~5–8 kg | Conventional and easy to procure/image, but heavier, higher draw, and VRAM-bound. Acceptable garrison/prototype platform. |
| **D. Ruggedized tactical edge server** (Klas Voyager-class, Crystal Group, Systel) with GPU module | Varies with config | Varies | MIL-STD packaged | The eventual fielding form factor if the capability transitions: MIL-STD-810/461, tactical power native, existing procurement vehicles. Costly for prototyping; identified here as the Phase 3 target, not the Phase 0 platform. |

### 5.2 Recommendation: A Two-Tier Fielding Concept

**Tier 1 (Role 1 / BAS):** Jetson AGX Orin 64 GB (or industrial equivalent) running a 8–14B-class model. Rationale: an IDC's query profile (protocols, dosing, procedures) is well served by a smaller model with excellent retrieval; the payoff is a sub-1-kg compute element that runs for hours on a standard battery bank at 15–30 W.

**Tier 2 (Role 2 / planning cell):** Strix Halo-class 128 GB unified-memory mini-PC running a 70B-class quantized model. Rationale: clinical synthesis questions (CPG reconciliation, surgical judgment support, doctrinal comparison) measurably benefit from the larger model; the platform is still a single small box on ordinary power, and its x86 architecture keeps it inside normal DoD software and STIG baselines.

**Prototype (Phase 0):** one Tier 2 box. It can emulate both tiers (run the small model to benchmark Tier 1 behavior), and it is procurable today as a commercial off-the-shelf purchase under micro-purchase or GPC-adjacent thresholds with unit funds.

### 5.3 Power and Environmental Notes

- Tier 1 at 30 W runs ~10 hours on a common 300 Wh battery bank; Tier 2 at a 100 W average runs ~3 hours on the same bank or indefinitely on a 150 W vehicle inverter.
- Neither tier requires active cooling beyond internal fans; the Tier 3 (ruggedized) path addresses temperature, humidity, shock, and EMI formally under MIL-STD-810/461 if the capability transitions.
- All radios (Wi-Fi/Bluetooth) are removed or firmware-disabled for the deployed configuration; client access is wired Ethernet to an isolated switch. A garrison configuration may permit an isolated local Wi-Fi segment where the ATO allows.

---

## 6. Software Architecture

### 6.1 Component Stack

| Layer | Component (all open-source / open-weight) | Function |
|---|---|---|
| Inference runtime | llama.cpp (GGUF) or vLLM | Runs the quantized language model entirely on-device |
| Language model | Tier 1: 8–14B class (e.g., Llama 3.1 8B, Qwen 2.5 14B). Tier 2: 70B class (e.g., Llama 3.3 70B) at Q4 quantization | Reads retrieved passages, synthesizes the answer, formats citations. License review required before fielding (Section 6.4) |
| Embedding model | bge-m3 or equivalent local embedding model | Converts corpus chunks and user queries to vectors for semantic search |
| Vector / search store | LanceDB or SQLite-based store with FTS5 | File-based (no database server process); holds vectors, keyword index, and chunk metadata |
| Retrieval | Hybrid: BM25 keyword + dense vector, fused, then locally re-ranked (bge-reranker class) | Doctrine queries are often exact-term; clinical queries are semantic. Hybrid covers both |
| Verification layer | Custom string/spans checker (Section 8) | Confirms every quoted span exists verbatim in the cited source before display |
| Application layer | FastAPI backend, React front end, embedded PDF viewer | Query interface, source-primary display, tap-to-open-page, query log |
| Platform | Hardened Linux (STIG-baseline), full-disk encryption, local accounts only | No WAN stack; USB provisioning; signed corpus update packages |

### 6.2 Query Flow

1. User submits a question via the local web interface.
2. Query is embedded and simultaneously run against the keyword index; results are fused and re-ranked; top 6–12 chunks (with full citation metadata) are selected.
3. The model receives the chunks and a fixed instruction: answer only from the provided passages; quote exactly; cite every claim; state explicitly when the corpus does not answer the question.
4. The verification layer checks every quoted span character-for-character against the source chunk. Failures trigger automatic regeneration; persistent failure returns the raw passages with a flag instead of a synthesized answer.
5. The interface renders sources first (verbatim passages with citations), synthesis second, and a one-tap path to the full PDF at the cited page.

### 6.3 The "I Don't Know" Requirement

The single most important behavioral specification: when retrieval returns nothing relevant, the system must say so plainly — "The loaded corpus does not address this; the closest passages are…" — rather than improvise. This is enforced three ways: a retrieval-confidence threshold below which synthesis is disabled; the fixed instruction set; and the verification layer, which cannot pass a quote that does not exist. Test and evaluation (Section 12) treats a confident wrong answer as a critical failure and an honest "not in corpus" as a pass.

### 6.4 Model Licensing and Provenance

Open-weight does not mean unencumbered. Before fielding, the selected model's license (e.g., Llama Community License, Apache-2.0 for some Qwen variants) requires review by counsel for government-use terms. Model weights, like the corpus, are hash-verified at provisioning; the deployed system runs only signed, known artifacts. No component phones home; the build process documents and pins every dependency for reproducibility.

### 6.5 Resource-Aware Recommendation (Capability Matching)

A reference system that only recites the ideal answer is of limited use to an element that does not hold the ideal resources. EMKA's design therefore adds a bounded inference step: the system reasons over what the querying element actually has on hand and tailors its answer accordingly. When a guideline names a first-line drug, device, or procedure the unit does not stock or cannot perform at its role, the system surfaces the guideline's own stated alternative and flags the constraint — rather than returning a recommendation the user cannot execute.

This is enabled by a dedicated capability layer in the corpus (a companion dataset to the clinical library) holding structured, non-PHI facts about the deployed context: the unit formulary, AMAL/ADAL equipment loadout, Role 1/2/3 capability matrix, blood posture, and evacuation-timeline planning factors. At query time these facts are retrieved alongside the clinical passages, and the model is instructed to match the recommendation to the available resources. Three guardrails keep this safe:

- **Cited substitution only.** The system may only offer an alternative that is itself stated in a retrieved, cited source (e.g., the CPG's own second-line agent). It never invents a substitution or improvises a dose. If no sourced alternative exists, it says so and returns the standard recommendation with the constraint noted.
- **Both facts shown.** The interface displays the clinical source passage and the availability datum it matched against ("formulary shows X not stocked; this CPG lists Y as alternative"), so the clinician sees the reasoning, not just the conclusion.
- **Capability data is governed like any corpus content.** Formulary and loadout facts are command-owned Unit-Shelf items (§7.5), watermarked and custodian-reviewed; a stale formulary is a defined defect, because a wrong availability assumption is as dangerous as a wrong clinical fact.

The payoff is a consultant that answers the question the user actually faces — "what do I do with what I have" — while never crossing from retrieval into unsupported clinical invention. The capability layer is a Phase 1 addition; the Phase 0 prototype demonstrates it on a single unit's formulary and a Role 1/2 capability matrix.

---

## 7. Corpus Definition and Governance

### 7.1 Candidate Corpus — Phase 0/1 (Government-Owned or Openly Licensed Only)

| Category | Publications (representative) | Rights posture |
|---|---|---|
| Joint / Navy / USMC doctrine | JP 4-02; NTTP 4-02 series; MCTP 3-40A; NAVMED P-series; relevant MCRPs/MCWPs | U.S. Government works; verify distribution statements (A vs. C/D) drive who may use the device, not whether it may exist |
| Clinical practice guidelines | Joint Trauma System CPGs (complete set); CoTCCC guidelines and skill cards; THOR/armed services blood program guidance | Government works; freely distributable within DoD |
| Military clinical references | Emergency War Surgery (Borden Institute); Pharmacology for the Prehospital Professional equivalents from government sources; USAMRICD/USAMRIID handbooks (chemical/biological casualty care) | Borden Institute and service publications: government works |
| Drug reference | FDA structured product labels (DailyMed extract); service formulary documents | Public domain / government |
| Unit-generated | MEF and MSC orders, SOPs, OPORD medical annexes (unclassified), AMAL listings | Command-owned; the device's biggest quick win — this content exists nowhere searchable today |

*The full 227-item curated corpus is tracked in `EMKA_Corpus_Manifest.xlsx`.*

### 7.2 Commercial Texts: A Deliberate Phase 2+ Decision

Standard clinical texts (e.g., major emergency medicine and surgery references, commercial drug databases) are copyrighted and cannot simply be indexed into a fielded government device. Options, in ascending order of cost and effort: (a) rely on the government-owned corpus above, which covers the deployed scope surprisingly well; (b) negotiate an enterprise offline license through existing DHA/Navy Medicine library channels (precedent exists for offline UpToDate-class licensing on hospital ships); (c) substitute openly licensed references where quality permits. The framework treats commercial content as a corpus-governance decision that must not delay the prototype, which proceeds on government content alone.

### 7.3 Corpus Governance Model

- A designated corpus custodian (proposed: the sponsoring command's clinical SME panel) approves every document before ingestion — correct edition, current change transmittal, distribution statement recorded.
- Every document carries metadata: title, publication number, edition/date, distribution statement, ingestion date, SHA-256 hash. The system displays edition and date with every citation so a user always knows what version answered them.
- Updates ship as signed corpus packages on physical media (write-once optical or hash-verified USB under two-person control), applied by a trained maintainer. Target cycle: quarterly, with out-of-cycle pushes for safety-relevant CPG changes.
- A superseded document is removed, not merely supplemented; the index is rebuilt; the change is logged. Stale doctrine presented as current is a defined critical defect.

### 7.4 Conflict Handling Between Sources

Authoritative sources will disagree — a recently updated CPG against an older reference chapter, or a command SOP that deliberately deviates from service doctrine. The system must never silently arbitrate. Three mechanisms govern conflict handling:

- **Surface, don't arbitrate.** When retrieved passages materially disagree, the interface presents both verbatim, side by side, each with edition and date, under an explicit flag: "These sources differ." The clinician or planner resolves the conflict, exactly as they would with two disagreeing texts on a shelf.
- **Precedence metadata.** Every document carries an authority tier assigned at ingestion (command order › service policy › current CPG › doctrinal publication › reference text) and an effective date. The model may order its presentation by precedence and recency — "the more current and authoritative source states X; an older source states Y" — but may not suppress either passage.
- **Conflict logging as corpus quality assurance.** Every detected conflict routes to the corpus custodian. Some conflicts are legitimate (deliberate SOP deviations); others reveal that a superseded document survived an update cycle — precisely the defect §7.3's supersession discipline exists to catch. As a side effect, the system functions as a doctrine-consistency auditor across the loaded library.

### 7.5 Field Additions: The Two-Shelf Model

Deployed medical officers will need to add documents after provisioning — a CPG updated en route, a fragmentary order's medical annex, a newly signed command SOP. The air gap does not prevent local ingestion; what must be protected is the trust boundary. The design separates the corpus into two shelves:

- **Authoritative shelf.** The signed, custodian-approved corpus described in §§7.1–7.3. End users cannot modify it; changes arrive only as signed update packages.
- **Unit shelf.** A designated medical officer (a named role, not all users) may load documents locally via hash-logged USB or the isolated web interface. Unit-shelf documents index and become queryable immediately, but every answer drawing on them is visibly watermarked — "Source: unit-added, not custodian-verified" — with citations rendered in a distinct style. The submitter's identity, the file hash, and the timestamp are logged. Responsibility for the rights posture of unit-added content rests with the submitter, per the command policy letter (Section 10).
- **Promotion path.** The custodian periodically reviews unit-shelf additions and either promotes them to the authoritative shelf with full metadata, or removes them. Promotion and removal are logged corpus events subject to the §8.1 regression harness.

The two-shelf model buys field agility without corrupting the system's central property: an unwatermarked citation always means machine-verified text from a custodian-approved source.

---

## 8. Ingestion Pipeline and Citation-Fidelity Design

### 8.1 Ingestion Pipeline Specification

- **Extraction:** PDF text extraction with layout awareness; OCR pass (Tesseract-class, local) for scanned legacy pubs; tables extracted to structured form where feasible, otherwise preserved as page-image references so the user is sent to the table rather than shown a mangled version of it.
- **Structural parsing:** doctrine follows predictable numbering (chapter, section, numbered paragraph). The parser captures the full breadcrumb — e.g., "NTTP 4-02 › Ch 3 › 3.2.1 › p. 3-7" — as metadata on every chunk.
- **Chunking:** paragraph-level chunks with heading breadcrumbs prepended, sized ~200–500 tokens, with overlap across boundaries; CPG algorithms and dosing tables chunked as intact units, never split.
- **Indexing:** each chunk stored with its vector, keyword index entry, citation metadata, source hash, and byte offsets back into the source PDF (enabling exact-page opening and the verification layer).
- **Validation:** after each build, an automated harness runs a fixed regression set of ~200 known question-answer-citation triples (Section 11) and blocks release on failure.

### 8.2 Why Citation Fidelity Is the Differentiator

The user's stated priority order — verbatim fidelity first — drives the architecture. Three mechanisms deliver it: retrieval hands the model the actual text (so quoting is transcription, not recall); the fixed instruction requires exact quotation with pinpoint citation; and the post-generation verifier string-matches every quoted span against the indexed source, with byte-offset traceability into the PDF itself. The result is a property no fine-tuned or cloud chatbot offers: every quotation on screen is machine-guaranteed to exist, verbatim, at the cited location. That guarantee — not conversational fluency — is what earns clinical trust at 0300.

---

## 9. Security and Accreditation Pathway

### 9.1 Design-for-Accreditation Posture

The accreditation problem, not the engineering problem, is the schedule driver for any capability like this. EMKA's design choices are made to shrink it:

- **No PHI, by design and by policy.** The device is a reference library. This keeps it outside HIPAA-driven system categorization and removes the single largest source of accreditation friction for medical IT.
- **No network connectivity.** A standalone, air-gapped system with no WAN interface presents a categorically smaller attack surface. The applicable pathway is an assess-and-authorize action for a standalone/closed system — potentially as a Platform IT (PIT) determination or a standalone-network ATO, at the Authorizing Official's discretion.
- **Standard baselines.** x86 hardware running a STIG-hardened Linux image, full-disk encryption at rest, local authentication, physical-media-only updates under two-person integrity, and complete audit logging of queries and corpus changes.
- **Unclassified only, initially.** Phase 0–2 corpora are unclassified with appropriate distribution statements; the classified-annex variant (loading distribution D or classified planning documents on an appropriately housed device) is a defined future increment, not a prototype requirement.

### 9.2 Supply Chain and Model Integrity

All software components are open-source, pinned, and hash-verified at build; model weights are obtained from primary sources and hash-verified; the complete system image is built reproducibly and signed. The device runs only what the build manifest declares. There is no telemetry, no update check, and no external dependency at runtime — verifiable by inspection because no network stack is exposed.

### 9.3 Early Engagements

- **Command ISSM/cyber staff:** frame the system accurately as "a search engine over publications the command already owns, on a computer with no network connection."
- **Servicing Authorizing Official's office:** pre-coordinate the standalone/PIT pathway before hardware purchase.
- **BUMED/DHA clinical informatics:** ensure alignment with any emerging enterprise policy on locally hosted AI, and register the effort so it informs (rather than collides with) enterprise initiatives.

---

## 10. Clinical Governance and Scope of Use

- EMKA is clinical decision support of the reference class — the electronic equivalent of a well-indexed bookshelf. It issues no orders, calculates no patient-specific doses against patient data, and connects to no clinical system.
- A local instruction (proposed: command policy letter signed by the medical department head or surgeon) defines authorized users, prohibits PHI entry, requires source verification before clinical action, and assigns the corpus custodian role. This paper's author has drafted analogous CO policy letters and can supply a template.
- The interface enforces the hierarchy: retrieved doctrine/CPG text is the primary display element; the synthesized answer is visibly secondary; every screen carries the corpus edition date and the no-PHI banner.
- Query logs (question, retrieved sources, answer, verification result — never patient data) are retained for quality review, both to improve retrieval and to give clinical leadership visibility into how the tool is actually used.
- A defined adverse-feedback channel: any user who believes the system returned wrong or unsafe content flags it in-interface; flags route to the custodian; confirmed defects trigger corpus or configuration corrections and are logged.

---

## 11. Test and Evaluation Plan

### 11.1 Metrics

| Metric | Definition | Phase 1 target |
|---|---|---|
| Retrieval recall@10 | Fraction of test questions for which the passage containing the answer appears in the top 10 retrieved chunks | ≥ 95% |
| Citation accuracy | Fraction of displayed citations that point to the correct publication, paragraph, and page | ≥ 99% |
| Verbatim-quote integrity | Fraction of displayed quotations that string-match the source exactly (post-verifier) | 100% (enforced) |
| Grounded-answer rate | Fraction of synthesized claims supported by a retrieved passage, per blinded SME review | ≥ 98% |
| Honest-abstention rate | Fraction of deliberately out-of-corpus questions answered with "not in corpus" rather than improvisation | ≥ 95% |
| Latency | Query-to-answer time on target hardware | ≤ 30 s (Tier 2); ≤ 45 s (Tier 1) |
| Critical failure rate | Confident, wrong, cited-looking answers per 1,000 queries (SME-adjudicated) | 0 tolerated without corrective action |

### 11.2 Method

- **Gold-standard question set:** ~200 question-answer-citation triples authored by SMEs across the three user populations (IDC, Role 2 provider, planner), including deliberately unanswerable and adversarially ambiguous questions. This set runs automatically on every corpus or software change. *(A 30-case seed is in `eval/seed_cases.yaml`.)*
- **Blinded clinical review:** a panel of providers scores a sample of live answers for accuracy, completeness, and safety without seeing the metric dashboard.
- **Field pilot measures of effectiveness:** time-to-answer versus PDF-library baseline for the same questions; user trust survey; frequency of use during exercise injects (including a MASCAL inject); qualitative debriefs.
- **Publication opportunity:** the evaluation itself is a publishable study — offline retrieval-augmented reference systems evaluated in an operational military medical exercise would suit *Military Medicine* and complements the sponsoring command's readiness research portfolio.

---

## 12. Sustainment and Update Concept

- **Corpus updates:** quarterly signed packages on physical media; a trained maintainer (proposed: the unit's IDC or medical logistics staff, ~2 hours of training) applies them in minutes; the regression harness runs automatically before the device returns to service.
- **Model updates:** annually at most, treated as a configuration change with full regression testing — the corpus, not the model, is where currency lives.
- **Hardware:** commodity replacement; a cold-spare device with an identical image is the availability strategy (two-is-one). Provisioning a replacement from the signed image and corpus package takes under one hour.
- **Training:** a one-hour user orientation (how to ask, how to read citations, what the tool is not) plus the maintainer course. Draft curricula fold naturally into existing OPMED/SMO training pipelines.

---

## 13. Phased Implementation Roadmap

| Phase | Duration | Activities and exit criteria | Order-of-magnitude cost |
|---|---|---|---|
| **0 — Prototype** | 90 days | Procure one Tier 2 device; ingest JTS CPGs, CoTCCC, Emergency War Surgery, NTTP 4-02 series, unit SOPs; build pipeline, verifier, and interface; author gold-standard question set; hit Phase 1 metric targets on the bench. Exit: working demo + measured results briefed to HSOAG. | $5–15K (hardware + incidentals; labor in-house) |
| **1 — Garrison validation** | 90 days | SME panel review; blinded clinical evaluation; ISSM/AO engagement on standalone pathway; corpus governance charter signed; command policy letter issued. Exit: authorization to operate in exercise conditions. | $10–25K |
| **2 — Field pilot** | One MEF-level exercise cycle | One Tier 2 device with a Role 2 element; one Tier 1 device with a BAS; measure MOEs under field conditions incl. MASCAL inject; collect defect and trust data. Exit: go/no-go transition recommendation with data. | $15–30K |
| **3 — Transition decision** | — | If warranted: ruggedized (Class D) hardware selection, formal requirement documentation, enterprise corpus licensing decision, classified-annex variant scoping, alignment with DHA/BUMED enterprise AI policy. | Program decision |

---

## 14. Risks and Mitigations

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Confident wrong answer influences care (hallucination) | Low / High | Grounded-only generation, retrieval-confidence gating, machine quote verification, source-primary UI, SME red-team question set, zero-tolerance critical-failure metric, user training that the source — not the synthesis — is authoritative |
| Accreditation stalls the effort | Medium / High | PHI-free and air-gapped by design; early AO engagement; standalone/PIT pathway; prototype operates as a research demonstration on unclassified government publications while the pathway matures |
| Stale doctrine presented as current | Medium / Medium | Edition/date shown with every citation; supersession discipline in corpus governance; quarterly update cycle; regression harness |
| Copyright exposure from commercial texts | Low / Medium | Government-owned corpus only through Phase 2; commercial content gated on enterprise licensing (§7.2) |
| Scope creep toward patient data | Medium / High | No-PHI policy in the command instruction, persistent UI banner, no clinical-system interfaces in the architecture, custodian audit of query logs |
| Over-reliance / skill atrophy | Low / Medium | Framed and trained as a reference accelerator; the field pilot explicitly measures whether users verify sources; training reinforces scope of practice |
| Enterprise policy overtakes local effort | Medium / Low | Early registration with BUMED/DHA informatics; the prototype's value is precisely to generate the field data enterprise programs lack |
| Key-person dependency (solo builder) | High / Medium | Full DESIGN.md, reproducible build manifest, documented corpus pipeline, and maintainer training from day one |

---

## 15. Recommendation and Request to HSOAG

The request is deliberately modest: endorsement of a 90-day, ~$5–15K Phase 0 prototype on government-owned publications and commercial hardware, with a report-back of measured results against the Section 11 metrics; designation of a clinical SME panel to author the gold-standard question set and serve as corpus custodians; and sponsorship of early engagement with the servicing Authorizing Official on the standalone accreditation pathway.

The strategic argument is the same one that runs through the Military Health System's readiness literature: expeditionary medicine cannot depend on connectivity it will not have. The knowledge our corpsmen and providers need already exists in publications we already own. This capability closes the last tactical mile between the library and the litter — with an auditable, citation-guaranteed system small enough to carry and honest enough to trust.

---

## Appendix A: Phase 0 Bill of Materials (Representative)

| Item | Est. cost | Notes |
|---|---|---|
| Tier 2 compute: 128 GB unified-memory x86 mini-workstation (Strix Halo class) | $3,500–5,000 | Single-box appliance; emulates both tiers for prototyping |
| Storage: 4 TB NVMe (internal) + write-once media for corpus packages | $400 | Corpus, models, and image with room to grow |
| Isolated network kit: unmanaged switch, cables; ruggedized transit case | $600 | No WAN hardware procured |
| UPS / battery bank (300 Wh class) for power testing | $400 | Validates tactical-power operation |
| Client device (ruggedized tablet or reuse of existing EUD) | $0–1,500 | Existing unit laptops suffice for Phase 0 |
| Software | $0 | Entire stack open-source / open-weight |
| Contingency | $1,000 | — |

---

## Appendix B: Glossary

| Term | Definition |
|---|---|
| RAG | Retrieval-Augmented Generation: the model answers from documents retrieved at query time rather than from memorized training data |
| Quantization (Q4) | Compressing model weights to ~4 bits per parameter, cutting memory needs roughly 4× with modest quality loss; what makes 70B-class models runnable on small hardware |
| Embedding model | A small model that converts text to numeric vectors so semantically similar passages can be found mathematically |
| Hybrid retrieval | Combining exact keyword search (BM25) with vector similarity search; covers both "find paragraph 3.2.1" and "what do I do about X" query styles |
| Reranker | A second-stage model that re-orders retrieved candidates by true relevance to the question |
| Chunk | The unit of indexed text — here, a paragraph with its heading breadcrumb and citation metadata attached |
| Hallucination | A fluent, plausible, unsupported model statement; the failure mode the verification layer and abstention behavior are built to eliminate |
| DDIL | Denied, Degraded, Intermittent, and Limited-bandwidth communications environment |
| PIT | Platform Information Technology: a DoD designation for IT integral to a platform/system, with a tailored authorization pathway |
| Air-gapped | Physically isolated from any external network; here, no WAN interface exists on the device at all |
