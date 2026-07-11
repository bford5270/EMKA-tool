"""PDF -> structured, cited chunks.

Manifest-driven (docs/EMKA_Corpus_Manifest.xlsx is the source of truth).
Layout-aware extraction (PyMuPDF), local OCR fallback, doctrine-numbering
breadcrumbs, paragraph chunks that never split tables or dosing blocks.
Implemented in Prompts 3-4.
"""
