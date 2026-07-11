# EMKA Evaluation

Gold-standard question–answer–citation triples that gate every corpus and software change. The harness (built in `docs/EMKA_Build_Prompts.md`, Prompt 11) runs these cases and exits non-zero if any metric falls below the thresholds in `seed_cases.yaml`.

## Why this exists

A reference system earns clinical trust only if a skeptical provider can verify it. These cases operationalize that: each one pins a real question to the source that should answer it, the section that should be cited, and the elements a grounded answer must contain. A **confident wrong answer is a critical failure**; an honest "not in corpus" is a pass.

## Metrics

| Metric | What it measures | Seed threshold |
|---|---|---|
| `retrieval_recall_at_10` | Does the source in `expected_source_ref` appear in the top 10 retrieved chunks? | ≥ 0.95 |
| `citation_accuracy` | Does the displayed citation point to the correct pub / paragraph / page? | ≥ 0.99 |
| `verbatim_quote_integrity` | Do displayed quotes string-match the source exactly (post-verifier)? | 1.00 (enforced) |
| `grounded_answer_rate` | Are the `answer_must_include` elements present and supported by a retrieved passage? | ≥ 0.98 |
| `honest_abstention_rate` | On `expected_behavior: abstain` cases, does the system decline rather than improvise? | ≥ 0.95 |
| `latency_seconds_max` | Query-to-answer time on target hardware | ≤ 30 s |

## Case schema

See the header comment in `seed_cases.yaml` for the full field list. Key ones:

- `expected_source_ref` — manifest Ref IDs (e.g. `CPG-01`, `PC-10`) that should be retrieved. Ties the eval directly to the corpus manifest.
- `answer_must_include` — concept-level rubric elements, **not** verbatim text. The grader checks these are present and grounded.
- `exercises` — which behaviors the case tests: `retrieval`, `citation`, `grounded_answer`, `abstention`, `conflict_handling`, `resource_matching`, `capability_limit`.
- `sme_verify` — **the most important governance field.** Precise doses, thresholds, and time windows live here, not in the rubric, because an unverified numeric "expected answer" is worse than none. A case is not authoritative until its `sme_verify` items are confirmed against the loaded source.
- `context` — for `resource_matching` / `capability_limit` cases: the availability/loadout facts (formulary present/absent, capability matrix) the system must reason over.

## Coverage (seed set, 30 cases)

- Roles: IDC (6), Role 2 (9), Planner (5), DNBI/primary care (10)
- Behaviors: answer (27), abstain (3)
- Special behaviors exercised: abstention (3), conflict handling (1), resource matching (2), capability limit (1)

The seed set is intentionally small and honest about what it doesn't yet pin down. The clinical SME panel expands it toward the ~200-case target defined in the concept paper and validates every `sme_verify` item.

## Adding a case

1. Copy an existing case block; give it the next `EMKA-EVAL-###` id.
2. Reference a real manifest Ref ID in `expected_source_ref`.
3. Put concept-level elements in `answer_must_include`; put any exact figure in `sme_verify`.
4. Tag `exercises` so the metric roll-up is correct.
5. Run `make eval` — it should surface the new case immediately.

## A note on clinical accuracy

These cases are drafted to have the right *structure* and *provenance*. Exact clinical values (doses, thresholds, timing) are deliberately deferred to `sme_verify` for confirmation against the loaded edition — the same discipline the concept paper requires of the corpus itself. Do not treat an unverified case as a source of clinical truth.
