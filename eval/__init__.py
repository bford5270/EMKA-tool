"""Gold-standard eval harness.

Runs question-answer-citation triples (seed_cases.yaml), scores retrieval
recall@10, citation accuracy, quote integrity, grounded-answer rate,
honest-abstention rate, latency; exits non-zero below thresholds so it gates
every corpus/software change. Implemented in Prompt 11.
"""
