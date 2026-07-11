"""The chunk schema — the contract every downstream component binds to.

Defined and FROZEN by Prompt 3 (ingestion). After freezing, changes require a
migration proposal in DESIGN.md §5. Required fields per the playbook:

    doc_id, title, pub_number, edition_date, authority_tier (T1-T5),
    shelf (authoritative|unit), distribution_stmt, category, rights_posture,
    source_sha256, page, char_start, char_end, breadcrumb, text
"""
