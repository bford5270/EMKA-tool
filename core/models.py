"""Model backend abstraction: chat, embeddings, reranker.

Three interfaces, two implementations each:

- REAL backends (llama.cpp GGUF chat; sentence-transformers embedder/reranker)
  load from pre-staged local files only (models/README.md) and are the ONLY
  backends permitted on a fielded device.
- STUB backends are deterministic, dependency-light stand-ins for development
  environments where model weights cannot be staged (e.g. CI with no model
  volume). They are quarantined behind EMKA_ALLOW_STUB_MODELS=1, announce
  themselves loudly on stderr, and must never be enabled on a device.

Every consumer (retrieval, generation, eval) talks to these interfaces and
does not care which is behind them — which is also what makes the dev-model /
target-model swap a pure config change.
"""

from __future__ import annotations

import os
import sys
from typing import Protocol

from core.config import EmkaConfig


class ModelsNotStagedError(RuntimeError):
    """Raised when real model files are missing and stubs are not allowed."""


class ChatModel(Protocol):
    backend: str

    def complete(
        self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.1
    ) -> str: ...


class Embedder(Protocol):
    backend: str

    def embed_queries(self, texts: list[str]) -> list[list[float]]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    backend: str

    def score(self, query: str, passages: list[str]) -> list[float]: ...


# --------------------------------------------------------------------------
# Real backends — local files only
# --------------------------------------------------------------------------


class LlamaCppChatModel:
    backend = "llama.cpp"

    def __init__(self, cfg: EmkaConfig, n_ctx: int | None = None):
        import llama_cpp

        if not cfg.chat_model_path.exists():
            raise ModelsNotStagedError(f"chat model not staged: {cfg.chat_model_path}")
        self._llm = llama_cpp.Llama(
            model_path=str(cfg.chat_model_path),
            n_ctx=n_ctx or cfg.chat_n_ctx,
            n_threads=cfg.chat_n_threads,
            verbose=False,
        )
        self.model_path = cfg.chat_model_path

    def complete(
        self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.1
    ) -> str:
        out = self._llm.create_chat_completion(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        return out["choices"][0]["message"]["content"]


class SentenceTransformerEmbedder:
    backend = "sentence-transformers"

    def __init__(self, cfg: EmkaConfig):
        cfg.enforce_offline()
        import sentence_transformers

        self._query_prefix = cfg.embed_query_prefix
        self._doc_prefix = cfg.embed_document_prefix
        self._model = sentence_transformers.SentenceTransformer(
            cfg.embed_model_id, trust_remote_code=True
        )

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._query_prefix + t for t in texts])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._doc_prefix + t for t in texts])


class CrossEncoderReranker:
    backend = "sentence-transformers"

    def __init__(self, cfg: EmkaConfig):
        cfg.enforce_offline()
        import sentence_transformers

        self._model = sentence_transformers.CrossEncoder(cfg.rerank_model_id)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict([(query, p) for p in passages])]


# ---------------------------------------------------------------------------
# Stub backends — dev/CI only, deterministic, never fielded
# ---------------------------------------------------------------------------

_STUB_BANNER_SHOWN = False


def _stub_banner() -> None:
    global _STUB_BANNER_SHOWN
    if not _STUB_BANNER_SHOWN:
        print(
            "\n*** EMKA STUB MODELS ACTIVE — deterministic stand-ins, NOT clinical-grade. "
            "Dev/CI only; never field a device in this mode. ***\n",
            file=sys.stderr,
        )
        _STUB_BANNER_SHOWN = True


def _token_set(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t}


_STUB_STOPWORDS = frozenset(
    "a an and are as at be but by do does for from how i if in is it its me my "
    "need of on or so soon that the their there this to we what when where "
    "which who will with you your".split()
)


def _stem(token: str) -> str:
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _content_tokens(text: str) -> set[str]:
    return {_stem(t) for t in _token_set(text) if t not in _STUB_STOPWORDS}


class StubEmbedder:
    """Deterministic hashed bag-of-words embeddings. Lexical overlap produces
    real cosine geometry, which is enough to exercise retrieval mechanics."""

    backend = "stub"
    DIM = 512

    def _embed(self, text: str) -> list[float]:
        import hashlib
        import math

        vec = [0.0] * self.DIM
        for tok in _token_set(text):
            h = int.from_bytes(hashlib.sha256(tok.encode()).digest()[:8], "big")
            vec[h % self.DIM] += 1.0 + (h >> 32) % 3 * 0.1
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        _stub_banner()
        return [self._embed(t) for t in texts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        _stub_banner()
        return [self._embed(t) for t in texts]


class StubReranker:
    """Query-term coverage relevance over stopword-filtered, crudely stemmed
    content tokens: |query ∩ passage| / |query|. Deterministic; scores in
    [0, 1]; long passages are not penalized."""

    backend = "stub"

    def score(self, query: str, passages: list[str]) -> list[float]:
        _stub_banner()
        q = _content_tokens(query)
        if not q:
            return [0.0] * len(passages)
        return [len(q & _content_tokens(p)) / len(q) for p in passages]


class StubChatModel:
    """Emits a grounded, quote-bearing answer by parsing the [PASSAGE] blocks
    of the synthesis prompt (generate/prompt_format.py). The quote is an exact
    slice of the top-precedence passage, so verification passes genuinely and
    the synthesize->verify->assemble pipeline is exercised deterministically
    without weights."""

    backend = "stub"

    def complete(
        self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.1
    ) -> str:
        _stub_banner()
        # lazy import: core must not import generate at module load time
        from generate.prompt_format import PASSAGE_RE

        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        match = PASSAGE_RE.search(user)
        if match is None:
            return "The loaded corpus does not answer this question."
        chunk_id, body = match.group("chunk_id"), match.group("body")
        end = body.find(". ")
        sentence = body[: end + 1] if end != -1 else body
        answer = f'<quote src="{chunk_id}">{sentence}</quote>'
        if "NOT in loadout" in user:
            answer += (
                "\nAvailability note (command-provided): a recommended item is not in "
                "the current loadout; see the availability data and cited sources for "
                "any source-stated alternative."
            )
        return answer


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def stubs_allowed() -> bool:
    return os.environ.get("EMKA_ALLOW_STUB_MODELS") == "1"


def _real_models_staged(cfg: EmkaConfig) -> bool:
    return cfg.chat_model_path.exists() and cfg.hf_cache_dir.exists()


def load_chat_model(cfg: EmkaConfig) -> ChatModel:
    if cfg.chat_model_path.exists():
        return LlamaCppChatModel(cfg)
    if stubs_allowed():
        return StubChatModel()
    raise ModelsNotStagedError(
        f"chat model not staged at {cfg.chat_model_path}; run `make models` "
        "(or set EMKA_ALLOW_STUB_MODELS=1 in dev only)"
    )


def load_embedder(cfg: EmkaConfig) -> Embedder:
    if cfg.hf_cache_dir.exists():
        return SentenceTransformerEmbedder(cfg)
    if stubs_allowed():
        return StubEmbedder()
    raise ModelsNotStagedError(
        f"embedding model cache not staged at {cfg.hf_cache_dir}; run `make models` "
        "(or set EMKA_ALLOW_STUB_MODELS=1 in dev only)"
    )


def load_reranker(cfg: EmkaConfig) -> Reranker:
    if cfg.hf_cache_dir.exists():
        return CrossEncoderReranker(cfg)
    if stubs_allowed():
        return StubReranker()
    raise ModelsNotStagedError(
        f"reranker cache not staged at {cfg.hf_cache_dir}; run `make models` "
        "(or set EMKA_ALLOW_STUB_MODELS=1 in dev only)"
    )
