"""Hybrid search: dense + keyword -> RRF fusion -> rerank -> abstention gate.

Results carry the full Chunk (citation metadata, authority tier, edition
date) plus per-stage scores, so downstream can order presentation by
precedence/recency and the UI can show its work. If the top reranker score
is below the abstention threshold the result is flagged
``abstained=True`` / reason "insufficient corpus support" — generation MUST
refuse rather than improvise (DESIGN.md §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.config import EmkaConfig, load_config
from core.models import Embedder, Reranker, load_embedder, load_reranker
from core.schema import Chunk
from retrieval.store import ChunkStore, DenseIndex

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk: Chunk
    rerank_score: float
    rrf_score: float
    dense_rank: int | None  # None = found only by the other path
    keyword_rank: int | None


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieval_confidence: float = 0.0  # top rerank score, 0..1
    abstained: bool = False
    abstain_reason: str = ""


def _rrf(ranks: dict[str, dict[str, int]]) -> dict[str, float]:
    """chunk_id -> sum over paths of 1/(RRF_K + rank)."""
    fused: dict[str, float] = {}
    for path_ranks in ranks.values():
        for chunk_id, rank in path_ranks.items():
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    return fused


class HybridRetriever:
    def __init__(
        self,
        cfg: EmkaConfig | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
    ):
        self.cfg = cfg or load_config()
        self._embedder = embedder or load_embedder(self.cfg)
        self._reranker = reranker or load_reranker(self.cfg)
        self._store = ChunkStore(self.cfg)
        self._dense = DenseIndex(self.cfg, self._embedder)

    def search(self, query: str, top_k: int | None = None) -> RetrievalResult:
        cfg = self.cfg
        top_k = top_k or cfg.retrieval_top_k
        candidates = max(cfg.rerank_candidates, top_k)

        dense_hits = self._dense.search(query, limit=candidates)
        keyword_hits = self._store.keyword_search(query, limit=candidates)

        dense_ranks = {cid: i + 1 for i, (cid, _) in enumerate(dense_hits)}
        keyword_ranks = {cid: i + 1 for i, (cid, _) in enumerate(keyword_hits)}
        fused = _rrf({"dense": dense_ranks, "keyword": keyword_ranks})
        if not fused:
            return RetrievalResult(
                query=query,
                abstained=True,
                abstain_reason="insufficient corpus support (no candidates)",
            )

        ranked_ids = sorted(fused, key=fused.get, reverse=True)[:candidates]
        chunks = [self._store.get(cid) for cid in ranked_ids]
        scores = self._reranker.score(query, [c.embed_text for c in chunks])

        order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [
            RetrievedChunk(
                chunk=chunks[i],
                rerank_score=float(scores[i]),
                rrf_score=fused[chunks[i].chunk_id],
                dense_rank=dense_ranks.get(chunks[i].chunk_id),
                keyword_rank=keyword_ranks.get(chunks[i].chunk_id),
            )
            for i in order
        ]
        confidence = results[0].rerank_score if results else 0.0
        abstained = confidence < cfg.abstention_threshold
        return RetrievalResult(
            query=query,
            chunks=results,
            retrieval_confidence=confidence,
            abstained=abstained,
            abstain_reason="insufficient corpus support" if abstained else "",
        )
