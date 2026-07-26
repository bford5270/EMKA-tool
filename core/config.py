"""Runtime configuration for EMKA.

All model paths, thresholds, and data locations are config values so the same
code runs the dev model on the dev box and the larger model on the x86 target.
Overridable via EMKA_* environment variables; no network-derived defaults, ever.

Model staging layout (see models/README.md):

    models/
      chat/<model>.gguf          llama.cpp chat model (dev: Phi-4-mini Q4_K_M)
      hf-cache/                  HF-format cache holding the embedding model,
                                 reranker, and their code repos, so everything
                                 resolves offline with HF_HUB_OFFLINE=1
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


@dataclass(frozen=True)
class EmkaConfig:
    # --- locations -----------------------------------------------------
    models_dir: Path = field(
        default_factory=lambda: _env_path("EMKA_MODELS_DIR", REPO_ROOT / "models")
    )
    corpus_dir: Path = field(
        default_factory=lambda: _env_path("EMKA_CORPUS_DIR", REPO_ROOT / "corpus")
    )
    data_dir: Path = field(default_factory=lambda: _env_path("EMKA_DATA_DIR", REPO_ROOT / "data"))

    # --- chat model (llama.cpp / GGUF) ---------------------------------
    # Dev default: Phi-4-mini-instruct (3.8B, Microsoft, MIT). On the x86
    # target, point EMKA_CHAT_MODEL at a Phi-4 14B (or larger) Q4_K_M GGUF.
    chat_model_file: str = os.environ.get(
        "EMKA_CHAT_MODEL", "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf"
    )
    chat_n_ctx: int = int(os.environ.get("EMKA_CHAT_N_CTX", "8192"))
    chat_n_threads: int | None = (
        int(os.environ["EMKA_CHAT_THREADS"]) if os.environ.get("EMKA_CHAT_THREADS") else None
    )

    # --- embeddings ------------------------------------------------------
    # nomic-embed-text (Nomic AI, US, Apache-2.0). Requires task prefixes.
    embed_model_id: str = os.environ.get("EMKA_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
    embed_query_prefix: str = "search_query: "
    embed_document_prefix: str = "search_document: "

    # --- reranker --------------------------------------------------------
    # mxbai-rerank (Mixedbread, DE, Apache-2.0). Target may use -large-v1.
    rerank_model_id: str = os.environ.get("EMKA_RERANK_MODEL", "mixedbread-ai/mxbai-rerank-base-v1")

    # --- retrieval thresholds (used from Prompt 5 on) --------------------
    abstention_threshold: float = float(os.environ.get("EMKA_ABSTENTION_THRESHOLD", "0.25"))
    retrieval_top_k: int = int(os.environ.get("EMKA_RETRIEVAL_TOP_K", "8"))
    rerank_candidates: int = int(os.environ.get("EMKA_RERANK_CANDIDATES", "30"))

    @property
    def chat_model_path(self) -> Path:
        return self.models_dir / "chat" / self.chat_model_file

    @property
    def hf_cache_dir(self) -> Path:
        return self.models_dir / "hf-cache"

    def enforce_offline(self) -> None:
        """Force all model libraries into offline mode, resolving models only
        from the pre-staged local cache. Call BEFORE importing torch/
        transformers/sentence-transformers."""
        os.environ["HF_HOME"] = str(self.hf_cache_dir)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def load_config() -> EmkaConfig:
    return EmkaConfig()
