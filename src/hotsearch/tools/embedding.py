"""Embedding tool: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 for semantic similarity. Disk cache at data/embeddings/."""

import hashlib
import json
import os
from typing import cast

import numpy as np

from hotsearch import EMBEDDINGS_DIR

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_Model = None


def _get_model():
    global _Model
    if _Model is None:
        from sentence_transformers import SentenceTransformer

        _Model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _Model


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


def _load_cache(key: str) -> list[float] | None:
    path = EMBEDDINGS_DIR / f"{key}.json"
    if path.exists():
        try:
            return cast(list[float], json.loads(path.read_text()))
        except Exception:
            pass
    return None


def _save_cache(key: str, vec: list[float]) -> None:
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = EMBEDDINGS_DIR / f"{key}.json"
    path.write_text(json.dumps(vec, ensure_ascii=False))


def embed(texts: list[str]) -> list[list[float]]:
    """Return 1024-dim embedding vectors for a list of texts. Cache to disk."""
    model = _get_model()
    results: list[list[float]] = []
    to_compute: list[str] = []
    to_compute_idx: list[int] = []

    for i, text in enumerate(texts):
        key = _cache_key(text)
        cached = _load_cache(key)
        if cached is not None:
            results.append(cached)
        else:
            results.append([])  # placeholder
            to_compute.append(text)
            to_compute_idx.append(i)

    if to_compute:
        vectors = model.encode(to_compute, normalize_embeddings=True)
        for idx, text, vec in zip(to_compute_idx, to_compute, vectors):
            key = _cache_key(text)
            vector_list = cast(list[float], [round(float(v), 6) for v in vec])
            _save_cache(key, vector_list)
            results[idx] = vector_list

    return results


def similarity(vec1: list[float], vec2: list[float]) -> float:
    """Cosine similarity between two vectors (already normalized by embed)."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
