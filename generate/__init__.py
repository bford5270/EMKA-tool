"""Grounded synthesis + verbatim verification.

retrieve -> synthesize -> verify -> assemble. Answers come ONLY from retrieved
passages; every displayed quote is character-verified against its source chunk
(verify.py). Fail safe, never fabricate. Implemented in Prompts 6-7.
"""
