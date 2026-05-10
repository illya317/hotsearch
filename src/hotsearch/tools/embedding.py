"""Embedding tool: BAAI/bge-m3 for semantic similarity."""

import hashlib
from typing import cast

import numpy as np

_Model = None
_Cache: dict[str, list[float]] = {}


def _get_model():
    """Lazy-load the BGE-M3 model."""
    global _Model
    if _Model is None:
        from sentence_transformers import SentenceTransformer

        _Model = SentenceTransformer("BAAI/bge-m3")
    return _Model


def embed(texts: list[str]) -> list[list[float]]:
    """Return 1024-dim embedding vectors for a list of texts."""
    model = _get_model()
    results: list[list[float]] = []
    to_compute: list[str] = []
    to_compute_idx: list[int] = []

    for i, text in enumerate(texts):
        key = hashlib.md5(text.encode()).hexdigest()
        if key in _Cache:
            results.append(_Cache[key])
        else:
            results.append([])  # placeholder
            to_compute.append(text)
            to_compute_idx.append(i)

    if to_compute:
        vectors = model.encode(to_compute, normalize_embeddings=True)
        for idx, text, vec in zip(to_compute_idx, to_compute, vectors):
            key = hashlib.md5(text.encode()).hexdigest()
            vector_list = cast(list[float], vec.tolist())
            _Cache[key] = vector_list
            results[idx] = vector_list

    return results


def similarity(vec1: list[float], vec2: list[float]) -> float:
    """Cosine similarity between two vectors (already normalized by embed)."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
