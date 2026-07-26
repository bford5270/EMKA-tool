"""Hybrid retrieval over the chunk store.

Dense (LanceDB) + keyword (SQLite FTS5), reciprocal-rank fusion, local
cross-encoder rerank, abstention gate below a confidence threshold.
Results always carry full citation metadata, authority tier, edition date.
Implemented in Prompt 5.
"""
