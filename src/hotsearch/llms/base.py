import os
from abc import ABC, abstractmethod

from .tool import Tool


class LLMClient(ABC):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list["Tool"] | None = None,
        max_rounds: int = 5,
        **kwargs,
    ) -> str:
        """Send messages, optionally with tools. Auto-execute tool calls up to max_rounds."""
        ...

    def _get_key(self, env_var: str) -> str:
        key = self.api_key or os.getenv(env_var)
        if not key:
            raise RuntimeError(f"{env_var} not set")
        return key

    def _get_base_url(self, env_var: str) -> str:
        url = self.base_url or os.getenv(env_var)
        if not url:
            raise RuntimeError(f"{env_var} not set")
        return url.rstrip("/")
