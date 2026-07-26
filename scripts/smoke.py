"""Offline inference smoke test (``make smoke``) — the provisioned-device check.

Verifies, with the network hard-disabled at the socket level, that the three
REAL model roles all run from pre-staged local files (stub backends are not
accepted here):

  1. chat model (llama.cpp/GGUF) generates a 20-token completion,
  2. embedding model embeds two strings and prints cosine similarity,
  3. reranker orders 3 candidate passages against a query sensibly.

Exits non-zero on any failure. Prints model paths + library versions so a
provisioning check can be pasted into a report.
"""

from __future__ import annotations

import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_config  # noqa: E402
from core.models import (  # noqa: E402
    CrossEncoderReranker,
    LlamaCppChatModel,
    ModelsNotStagedError,
    SentenceTransformerEmbedder,
)


def install_network_kill_switch() -> None:
    """Make any non-loopback connection attempt raise. This is the assertion
    that 'fully offline' is real, not aspirational."""
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *args, **kwargs):  # noqa: ANN001
        host = address[0] if isinstance(address, tuple) else str(address)
        if host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise RuntimeError(f"OFFLINE VIOLATION: attempted network connection to {host!r}")

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]


def check(label: str, ok: bool, detail: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    return ok


def main() -> int:
    cfg = load_config()
    cfg.enforce_offline()
    install_network_kill_switch()

    print("EMKA offline smoke test (real backends only)")
    print(f"  models_dir     : {cfg.models_dir}")
    print(f"  chat model     : {cfg.chat_model_path}")
    print(f"  embed model    : {cfg.embed_model_id} (cache: {cfg.hf_cache_dir})")
    print(f"  rerank model   : {cfg.rerank_model_id}")

    ok = True
    try:
        # -- 1. chat completion ---------------------------------------------
        import llama_cpp

        print(f"  llama-cpp-python {llama_cpp.__version__}")
        llm = LlamaCppChatModel(cfg, n_ctx=2048)
        text = llm.complete(
            [{"role": "user", "content": "State the ABCDE trauma mnemonic, briefly."}],
            max_tokens=20,
        ).strip()
        ok &= check("chat", bool(text), f"20-token completion: {text!r}")

        # -- 2. embeddings ----------------------------------------------------
        import sentence_transformers
        import torch

        print(
            f"  sentence-transformers {sentence_transformers.__version__}, "
            f"torch {torch.__version__}"
        )
        embedder = SentenceTransformerEmbedder(cfg)
        q = "tourniquet application for extremity hemorrhage"
        docs = [
            "Apply a tourniquet proximal to the bleeding site.",
            "Rotate supply pallets before the monsoon season.",
        ]
        qv = embedder.embed_queries([q])[0]
        dv = embedder.embed_documents(docs)
        sim_rel = sum(a * b for a, b in zip(qv, dv[0], strict=True))
        sim_unrel = sum(a * b for a, b in zip(qv, dv[1], strict=True))
        ok &= check(
            "embed",
            sim_rel > sim_unrel,
            f"cosine(query, relevant)={sim_rel:.3f} > cosine(query, unrelated)={sim_unrel:.3f}",
        )

        # -- 3. reranker --------------------------------------------------------
        reranker = CrossEncoderReranker(cfg)
        query = "What is the first-line treatment for severe extremity bleeding?"
        passages = [
            "Direct pressure and a windlass tourniquet are first-line for "
            "life-threatening extremity hemorrhage.",
            "Water purification tablets should be used when boiling is impractical.",
            "Rotary-wing evacuation request procedures are covered in chapter 9.",
        ]
        scores = reranker.score(query, passages)
        best = max(range(len(scores)), key=lambda i: scores[i])
        ok &= check(
            "rerank",
            best == 0,
            f"scores={[round(s, 3) for s in scores]} (top: passage {best})",
        )
    except ModelsNotStagedError as e:
        print(f"  [FAIL] models not staged: {e}")
        print("\nRun `make models` on a networked provisioning box first.")
        return 1

    print("\nSmoke test:", "ALL PASS (network disabled throughout)" if ok else "FAILURES above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
