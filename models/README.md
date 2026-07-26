# models/ (gitignored)

Model weights staged at provisioning time — **the only networked step in the
system**. Run `make models` (dev model) or
`uv run python scripts/fetch_models.py --target` (adds the 14B target model)
while the device still has network, then never again.

## Required staged files

```
models/
  chat/
    microsoft_Phi-4-mini-instruct-Q4_K_M.gguf   dev chat model (3.8B, ~2.5 GB)
    phi-4-Q4_K_M.gguf                           x86 target chat model (14B, ~9 GB, --target)
  hf-cache/                                      HF offline cache containing:
    nomic-ai/nomic-embed-text-v1.5              embeddings (safetensors + tokenizer)
    nomic-ai/nomic-bert-2048                    architecture code the embedder loads
    mixedbread-ai/mxbai-rerank-base-v1          reranker cross-encoder
```

All three roles are config-driven (`core/config.py`, `EMKA_*` env vars):
swapping the chat model on the target device is
`EMKA_CHAT_MODEL=phi-4-Q4_K_M.gguf` — no code change.

## Provenance / license

| Model | Origin | License |
|-------|--------|---------|
| Phi-4-mini-instruct / Phi-4 | Microsoft (US) | MIT |
| nomic-embed-text-v1.5 | Nomic AI (US) | Apache-2.0 |
| mxbai-rerank-base-v1 | Mixedbread (DE) | Apache-2.0 |

## Verifying a staged device

`make smoke` loads all three models and runs generation, embedding, and
reranking **with a socket-level network kill switch installed** — it fails
loudly if anything attempts a connection or a missing file forces a hub
lookup.
