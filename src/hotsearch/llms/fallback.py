import sys

from .base import LLMClient
from .tool import Tool


class FallbackClient(LLMClient):
    """Chain fallback across multiple LLM clients."""

    def __init__(self, clients: list[LLMClient] | None = None):
        # Avoid circular import by importing here
        from .deepseek import DeepseekClient
        from .kimi import KimiClient
        from .minimax import MinimaxClient

        if clients is None:
            clients = [MinimaxClient(), KimiClient(), DeepseekClient()]
        self.clients = clients

    def chat(
        self,
        messages: list[dict],
        tools: list["Tool"] | None = None,
        max_rounds: int = 5,
        **kwargs,
    ) -> str:
        for i, client in enumerate(self.clients):
            name = client.__class__.__name__.replace("Client", "").lower()
            try:
                return client.chat(
                    messages, tools=tools, max_rounds=max_rounds, **kwargs
                )
            except Exception as e:
                print(f"{name} failed: {e}", file=sys.stderr)
                if i < len(self.clients) - 1:
                    next_name = (
                        self.clients[i + 1]
                        .__class__.__name__.replace("Client", "")
                        .lower()
                    )
                    print(f"Falling back to {next_name}...", file=sys.stderr)
                else:
                    raise
        return ""
