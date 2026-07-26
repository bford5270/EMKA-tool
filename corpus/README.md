# corpus/ (gitignored)

Source PDFs staged on the device, never committed.

- `authoritative/` — custodian-approved, manifest-tracked publications.
- `unit/` — unit-added material; always watermarked "not custodian-verified".

The ingest queue is driven by `docs/EMKA_Corpus_Manifest.xlsx`; the filename
convention that matches manifest rows to files here is documented by Prompt 4.

## Staging the official JTS bundles

Download the two zips from jts.health.mil (CPGs A–H and I–Z), then:

```
uv run python scripts/stage_corpus.py ~/Downloads/Zip_of_Current_JTS_CPGs_A-H.zip
uv run python scripts/stage_corpus.py ~/Downloads/Zip_of_Current_JTS_CPGs_I-Z.zip
```

The tool matches each PDF's filename against the manifest titles and stages
matches as `<RefID>__<original-name>.pdf`. Ambiguous or unrecognized files
are listed for manual placement — it never guesses. Use `--dry-run` to
preview. Then run `make ingest && make index && make eval`.
