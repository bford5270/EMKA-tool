"""FastAPI service — localhost / isolated LAN only, no external calls.

POST /query, POST /corpus/refresh, GET /source/{doc_id}/page/{n}, GET /health.
Query log is local and never contains patient data. Implemented in Prompt 9.
"""
