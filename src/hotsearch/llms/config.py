"""LLM configuration helpers: resolve provider/model params from model_config.yaml."""

from hotsearch.config import model_config


def get_model_params(provider: str, model: str | None = None) -> dict:
    """Resolve model-specific params (max_tokens, temperature, etc.).

    Args:
        provider: Provider name (minimax, kimi, deepseek).
        model: Specific model name. If None, use the first model in config.

    Returns:
        Dict with at least "model" key, plus any configured params.
    """
    cfg = model_config()
    models = cfg.get("providers", {}).get(provider, {}).get("models", {})
    if model and model in models:
        return {"model": model, **models[model]}
    if models:
        first = next(iter(models))
        return {"model": first, **models[first]}
    return {}
