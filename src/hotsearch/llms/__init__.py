from .base import LLMClient
from .deepseek import DeepseekClient
from .fallback import FallbackClient
from .kimi import KimiClient
from .minimax import MinimaxClient
from .tool import Tool

__all__ = [
    "LLMClient",
    "DeepseekClient",
    "FallbackClient",
    "KimiClient",
    "MinimaxClient",
    "Tool",
    "get_client",
    "llm_for_agent",
]

_CLIENT_MAP: dict[str, type[LLMClient]] = {
    "minimax": MinimaxClient,
    "kimi": KimiClient,
    "deepseek": DeepseekClient,
}


def get_client(provider: str, model: str | None = None) -> LLMClient:
    """Create a single LLM client for a given provider and optional model."""
    cls = _CLIENT_MAP[provider]
    return cls(model=model)


def llm_for_agent(name: str) -> LLMClient:
    """Get the LLM client configured for a specific agent.

    Reads ``llm.agents.<name>`` from ``model_config.yaml``.

    - If ``chain`` is set, build a ``FallbackClient`` with that sequence.
    - If ``provider`` (+ ``model``) is set, return a single client.
    - If neither is set, fall back to the global ``fallback_chain``.

    Chain entries use ``provider/model`` syntax, e.g. ``deepseek/deepseek-v4-pro``.
    """
    from hotsearch.config import model_config

    cfg = model_config()
    agent_cfg = cfg.get("agents", {}).get(name, {})

    chain = agent_cfg.get("chain")
    if chain:
        clients = []
        for entry in chain:
            provider, _, model = str(entry).partition("/")
            clients.append(get_client(provider, model or None))
        return FallbackClient(clients=clients)

    provider = agent_cfg.get("provider")
    model = agent_cfg.get("model")
    if not provider:
        # Fall back to global fallback_chain
        chain = cfg.get("fallback_chain", ["minimax", "kimi", "deepseek"])
        clients = []
        for entry in chain:
            provider, _, model = str(entry).partition("/")
            clients.append(get_client(provider, model or None))
        return FallbackClient(clients=clients)

    return get_client(provider, model)
