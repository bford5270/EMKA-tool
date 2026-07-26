# EMKA Corpus Acquisition Guide

Where to download every acquirable document in `EMKA_Corpus_Manifest.xlsx`,
grouped by source. URLs verified 2026-07 via web search; always cross-check
the edition you actually receive against the manifest's `Edition / Date`
column at ingest (the eval harness's `sme_verify` discipline applies to the
corpus itself).

Staging workflow for every download below:

```
uv run python scripts/stage_corpus.py <zip-or-folder-or-pdf>   # auto-match to Ref IDs
# anything reported "needs review": rename by hand to <RefID>__<name>.pdf
make ingest && make index && make eval
```

Rights column reminder: rows marked `©-LIC` or `VERIFY` are **rights-gated**
— the ingest queue lists and SKIPS them until the custodian clears the
license posture. Download them if you like; they will not be ingested.

---

## 1. Joint Trauma System (covers ~75 rows: CPG-*, FRM-*, PH cross-refs)

Landing page: https://jts.health.mil/index.cfm/CPGs/cpgs

| File | URL |
|---|---|
| CPG bundle A–H | https://jts.health.mil/assets/docs/cpgs/Zip_of_Current_JTS_CPGs_A-H.zip |
| CPG bundle I–Z | https://jts.health.mil/assets/docs/cpgs/Zip_of_Current_JTS_CPGs_I-Z.zip |
| Forms bundle (FRM-01..07) | linked from the CPGs page ("Complete Zip of Current JTS Forms") |
| CPG Index (edition control) | https://jts.health.mil/assets/docs/cpgs/CPG_Index.pdf |

Individual current CPGs are also directly linked (e.g.
`.../cpgs/Airway_Management_in_Trauma_28_Jan_2026_ID39.pdf`) — useful for
rows marked "JTS CPG page (new)" like CPG-29. Keep the Index PDF with the
corpus: it is the authoritative edition list for supersession checks.

## 2. TCCC / Deployed Medicine (CPG-01, PH-01, PH-02)

- TCCC guidelines PDF: https://www.deployedmedicine.com/market/11/content/475
- All TCCC materials: https://www.deployedmedicine.com/tccc (DHA/JTS partnership)
- CoTCCC page: https://jts.health.mil/index.cfm/committees/cotccc

## 3. VA/DoD Clinical Practice Guidelines (21 rows: PC-*, BH-*, MSK-09…)

Index: https://www.healthquality.va.gov/guidelines/ — every guideline page
offers the full CPG, provider summary, and pocket card as PDFs. Examples:

- Hypertension (PC-01): https://www.healthquality.va.gov/guidelines/cd/htn/
- Low Back Pain (PC-10/MSK-09): https://www.healthquality.va.gov/guidelines/Pain/lbp/
- PTSD & Acute Stress Disorder (BH-02): https://www.healthquality.va.gov/guidelines/mh/ptsd/
- Mental health index (BH-01…): https://www.healthquality.va.gov/guidelines/mh/

Manifest rows say "Current — VERIFY": record the edition year of the PDF you
download into your ingest notes.

## 4. Reference handbooks (REF-01..04)

| Ref | Title | Source |
|---|---|---|
| REF-01 | Emergency War Surgery, 5th US Revision | Borden Institute: https://medcoe.army.mil/borden-tb-ews/ (free PDF; also GPO bookstore) |
| REF-02 | Medical Mgmt of Chemical Casualties Handbook | USAMRICD / MedCoE CBRNE resources — locate current edition via medcoe.army.mil; verify edition |
| REF-03 | USAMRIID "Blue Book" (Biological), 10th ed. | https://usamriid.health.mil/assets/docs/training/Blue_Book_10th_Edition.pdf |
| REF-04 | Medical Mgmt of Radiological/Nuclear Casualties | AFRRI (usuhs.edu/afrri) — verify current edition |

## 5. Doctrine (DOC-01..05)

- JP 4-02 Joint Health Services (DOC-01): JCS Joint Electronic Library
  https://www.jcs.mil/Doctrine/Joint-Doctrine-Pubs/4-0-Logistics-Series/
  (mirror: https://irp.fas.org/doddir/dod/jp4_02.pdf — prefer the JEL copy
  and verify it is the current edition)
- MCTP 3-40A Health Service Support Operations (DOC-05):
  https://www.marines.mil/News/Publications/MCPEL/Electronic-Library-Display/Article/1129131/mctp-3-40a/
  (direct PDF hosted on marines.mil Portals)
- NTTP 4-02.2 Patient Movement (DOC-02) and NTTP 4-02 series (DOC-03):
  Navy Warfare Library (NWDC / Navy doctrine portal, may require CAC).
  Manifest flags these VERIFY — confirm the distribution statement permits
  loading on the device before ingest.

## 6. Environmental & dive medicine (EN-01..03)

- US Navy Diving Manual (EN-01):
  https://www.navsea.navy.mil/Portals/103/Documents/SUPSALV/Diving/US%20DIVING%20MANUAL_REV7.pdf
  (confirm latest revision; manifest says VERIFY distribution statement)
- TB MED 507 Heat (EN-02): https://armypubs.army.mil (search TB MED 507;
  direct: armypubs.army.mil/epubs/DR_pubs/DR_a/ARN35159-TB_MED_507-000-WEB-1.pdf)
- TB MED 508 Cold (EN-03): https://usariem.health.mil/assets/docs/partnering/tbmed508.pdf

## 7. CDC (ID-01, ID-02, PC-20, SP-07)

- Yellow Book (ID-01): online edition https://www.cdc.gov/yellow-book/hcp/contents/index.html
  and NCBI Bookshelf https://www.ncbi.nlm.nih.gov/books/NBK620896/ — the CDC
  web content is USG public; the Oxford print PDF is NOT (publisher ©).
  Ingest from the CDC/NCBI public content only.
- Malaria treatment (ID-02): https://www.cdc.gov/malaria (Treatment of
  Malaria: Guidelines for Clinicians PDF)
- STI Treatment Guidelines (SP-07): https://www.cdc.gov/std/treatment-guidelines/
- Antibiotic stewardship / ARI guidance (PC-20): https://www.cdc.gov/antibiotic-use/

## 8. FDA DailyMed (REF-09 / OR-09)

Bulk SPL download (subset to the deployed formulary before ingest):
https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
Full releases are large; the formulary-subset script decision is a Phase-1
item — for Phase 0, download individual labels for formulary drugs.

## 9. StatPearls (OR-01, MSK-10/11) — RIGHTS-GATED

NCBI Bookshelf hosts StatPearls under CC BY-NC-ND 4.0. The manifest marks it
VERIFY: distributable and non-commercial, but **no-derivatives** interacts
with chunking/excerpting — get counsel/custodian sign-off before ingest.
The ingest queue will keep skipping these rows until rights are cleared in
the manifest.

## 10. Command-provided (no download): UNT-*, CAP-*, INS-09/10

Unit SOPs, OPORD annexes, formulary/AMAL exports, blood posture, evac
factors come from your command channels. Capability data files use the
templates in `capability/templates/` and stage under
`corpus/unit/capability/`. These are unit-shelf items: watermarked in every
answer, never custodian-verified.

## 11. Licensed / deferred (Phase 2 decisions)

Rows citing "Publisher license" (10 rows) and the DHA enterprise-library
items stay out of the prototype. The eval harness's abstention cases cover
the gap honestly — EMKA says "not in corpus" rather than pretending.
