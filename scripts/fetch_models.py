"""Provisioning-time model download. THE ONLY NETWORKED STEP IN THE SYSTEM.

Run once (``make models``) before the device goes dark. Stages every model
file the runtime needs into models/ so that all later execution works with
HF_HUB_OFFLINE=1 and no network of any kind. See models/README.md for the
exact staged layout and DESIGN.md §8 for the provenance decision.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_config  # noqa: E402

# Chat model: repo + filename pairs, quantized GGUF for llama.cpp.
# Dev model is downloaded by default; pass --target to also fetch the 14B.
CHAT_MODELS = {
    "dev": (
        "bartowski/microsoft_Phi-4-mini-instruct-GGUF",
        "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf",
    ),
    "target": ("bartowski/phi-4-GGUF", "phi-4-Q4_K_M.gguf"),
}

# HF-format repos staged into the offline cache (models/hf-cache).
# nomic-bert-2048 hosts the remote-code architecture that
# nomic-embed-text-v1.5 references; it must be cached for offline load.
HF_REPOS = [
    "nomic-ai/nomic-embed-text-v1.5",
    "nomic-ai/nomic-bert-2048",
    "mixedbread-ai/mxbai-rerank-base-v1",
]

# Weight/asset formats we do not use (we load safetensors via torch CPU).
IGNORE_PATTERNS = ["*.onnx", "onnx/*", "*.bin", "*.h5", "*.tflite", "*.msgpack", "openvino/*"]


def main() -> None:
    # HF_HOME must be set BEFORE huggingface_hub is imported — the library reads
    # it at import time to fix its cache constants. Setting it afterward silently
    # leaves downloads in the user's default ~/.cache/huggingface, which then
    # cannot be found by the offline runtime (enforce_offline points HF_HOME at
    # models/hf-cache). Set the env, then import, then also pass cache_dir
    # explicitly to snapshot_download as belt-and-suspenders.
    cfg = load_config()
    hub_cache = cfg.hf_cache_dir / "hub"
    os.environ["HF_HOME"] = str(cfg.hf_cache_dir)
    os.environ["HF_HUB_CACHE"] = str(hub_cache)

    from huggingface_hub import hf_hub_download, snapshot_download

    chat_dir = cfg.models_dir / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)

    variants = ["dev", "target"] if "--target" in sys.argv else ["dev"]
    for variant in variants:
        repo, filename = CHAT_MODELS[variant]
        print(f"[chat/{variant}] {repo} :: {filename}")
        hf_hub_download(repo_id=repo, filename=filename, local_dir=chat_dir)

    for repo in HF_REPOS:
        print(f"[hf-cache] {repo}")
        snapshot_download(repo_id=repo, ignore_patterns=IGNORE_PATTERNS, cache_dir=str(hub_cache))

    print("\nStaged models:")
    for path in sorted(cfg.models_dir.rglob("*")):
        if path.is_file() and path.stat().st_size > 50_000_000:
            print(f"  {path.relative_to(cfg.models_dir)}  {path.stat().st_size / 1e9:.2f} GB")
    print("\nDone. The runtime never needs the network again.")


if __name__ == "__main__":
    main()
