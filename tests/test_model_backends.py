"""Backend abstraction tests. Stub backends are deterministic, so these run
everywhere; real-backend loading is covered by tests/test_offline_models.py
on provisioned machines."""

import pytest

from core.config import load_config
from core.models import (
    ModelsNotStagedError,
    StubEmbedder,
    StubReranker,
    load_chat_model,
    load_embedder,
    load_reranker,
)


def test_stub_embedder_geometry():
    e = StubEmbedder()
    vecs = e.embed_documents(
        [
            "tourniquet for extremity hemorrhage control",
            "apply the tourniquet to control extremity hemorrhage",
            "monsoon season pallet rotation schedule",
        ]
    )

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert dot(vecs[0], vecs[1]) > dot(vecs[0], vecs[2])
    # normalized
    assert abs(dot(vecs[0], vecs[0]) - 1.0) < 1e-9
    # deterministic
    assert e.embed_documents(["tourniquet"]) == e.embed_documents(["tourniquet"])


def test_stub_reranker_orders_by_overlap():
    r = StubReranker()
    scores = r.score(
        "first-line treatment for extremity bleeding",
        [
            "tourniquet is the first-line treatment for life-threatening extremity bleeding",
            "water purification tablets",
        ],
    )
    assert scores[0] > scores[1]


def test_loaders_refuse_stubs_unless_opted_in(monkeypatch, tmp_path):
    monkeypatch.delenv("EMKA_ALLOW_STUB_MODELS", raising=False)
    monkeypatch.setenv("EMKA_MODELS_DIR", str(tmp_path / "empty-models"))
    cfg = load_config()
    for loader in (load_chat_model, load_embedder, load_reranker):
        with pytest.raises(ModelsNotStagedError):
            loader(cfg)


def test_loaders_allow_stubs_when_opted_in(monkeypatch, tmp_path):
    monkeypatch.setenv("EMKA_ALLOW_STUB_MODELS", "1")
    monkeypatch.setenv("EMKA_MODELS_DIR", str(tmp_path / "empty-models"))
    cfg = load_config()
    assert load_chat_model(cfg).backend == "stub"
    assert load_embedder(cfg).backend == "stub"
    assert load_reranker(cfg).backend == "stub"
