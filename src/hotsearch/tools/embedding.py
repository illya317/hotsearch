"""Embedding tool. Config at config/embedding.json. Disk cache at data/embeddings/."""

import hashlib
import json
import os
from typing import cast

import numpy as np

from hotsearch import CONFIG_DIR, EMBEDDINGS_DIR

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_Model = None
_Config: dict | None = None


def _load_config() -> dict:
    global _Config
    if _Config is None:
        path = CONFIG_DIR / "embedding.json"
        if path.exists():
            _Config = json.loads(path.read_text(encoding="utf-8"))
        else:
            _Config = {}
    return _Config


def _model_type(model_name: str) -> str:
    name = model_name.lower()
    if "embedding" in name and ("mlx" in name or "qwen" in name):
        return "mlx_embeddings"
    if "mlx" in name:
        return "mlx_lm"
    return "sentence_transformers"


def _get_model():
    global _Model
    if _Model is None:
        cfg = _load_config()
        model_name = cfg.get("model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        mtype = _model_type(model_name)

        if mtype == "mlx_embeddings":
            from mlx_embeddings import load

            _Model = load(model_name)
        elif mtype == "mlx_lm":
            import mlx.core as mx
            from mlx_lm import load

            device = cfg.get("device", "mps")
            if device in ("mps", "gpu", "metal"):
                mx.set_default_device(mx.gpu)
            else:
                mx.set_default_device(mx.cpu)
            _Model = load(model_name)
        else:
            from sentence_transformers import SentenceTransformer

            kwargs = {}
            if cfg.get("use_fp16"):
                kwargs["model_kwargs"] = {"torch_dtype": "float16"}
            _Model = SentenceTransformer(model_name, **kwargs)
            _Model.max_seq_length = cfg.get("max_seq_length", 512)
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


def _apply_instruction(texts: list[str], instruction: str | None) -> list[str]:
    """Prepend instruction for query texts."""
    if not instruction:
        return texts
    return [f"Instruct: {instruction}\nQuery: {t}" for t in texts]


def _embed_mlx_embeddings(texts: list[str], instruction: str | None = None) -> list[list[float]]:
    """Embed texts using mlx-embeddings (Qwen3-Embedding, etc.)."""
    from mlx_embeddings import generate

    model, processor = _get_model()
    cfg = _load_config()
    max_len = cfg.get("max_seq_length", 8192)
    batch_size = cfg.get("batch_size", 32)

    prepared = _apply_instruction(texts, instruction)
    results = []
    for i in range(0, len(prepared), batch_size):
        batch = prepared[i : i + batch_size]
        output = generate(
            model,
            processor,
            texts=batch,
            max_length=max_len,
            padding=True,
            truncation=True,
        )
        for vec in output.text_embeds:
            results.append([round(float(v), 6) for v in vec.tolist()])

    return results


def _embed_mlx_lm(texts: list[str]) -> list[list[float]]:
    """Embed texts using mlx-lm (Qwen3 chat, etc.)."""
    import mlx.core as mx

    model, tokenizer = _get_model()
    cfg = _load_config()
    max_len = cfg.get("max_seq_length", 2048)
    batch_size = cfg.get("batch_size", 8)

    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for text in batch:
            tokens = tokenizer.encode(text, add_special_tokens=True)
            if len(tokens) > max_len:
                tokens = tokens[:max_len]
            input_ids = mx.array([tokens])

            hidden = model.model(input_ids)
            mx.eval(hidden)

            h = hidden[0]
            embedding = h.mean(axis=0).tolist()

            norm = sum(x * x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]

            results.append(embedding)

    return results


def _embed(texts: list[str], instruction: str | None = None) -> list[list[float]]:
    """Core embed with optional instruction."""
    cfg = _load_config()
    results: list[list[float]] = []
    to_compute: list[str] = []
    to_compute_idx: list[int] = []

    for i, text in enumerate(texts):
        key = _cache_key(text)
        cached = _load_cache(key)
        if cached is not None:
            results.append(cached)
        else:
            results.append([])
            to_compute.append(text)
            to_compute_idx.append(i)

    if to_compute:
        model_name = cfg.get("model", "")
        mtype = _model_type(model_name)

        if mtype == "mlx_embeddings":
            vectors = _embed_mlx_embeddings(to_compute, instruction)
        elif mtype == "mlx_lm":
            vectors = _embed_mlx_lm(to_compute)
        else:
            model = _get_model()
            raw = model.encode(to_compute, normalize_embeddings=True)
            vectors = [v.tolist() for v in raw]

        for idx, text, vec in zip(to_compute_idx, to_compute, vectors):
            key = _cache_key(text)
            _save_cache(key, vec)
            results[idx] = vec

    return results


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts (document mode, no instruction). Cache to disk."""
    return _embed(texts, instruction=None)


def embed_query(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for queries (with instruction if configured)."""
    cfg = _load_config()
    instruction = cfg.get("query_instruction")
    return _embed(texts, instruction=instruction)


def embed_doc(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for documents (no instruction)."""
    cfg = _load_config()
    instruction = cfg.get("doc_instruction")
    return _embed(texts, instruction=instruction)


def similarity(vec1: list[float], vec2: list[float]) -> float:
    """Cosine similarity between two vectors (already normalized by embed)."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
