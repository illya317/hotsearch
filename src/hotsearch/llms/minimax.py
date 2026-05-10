import json
import os
import urllib.request

from .base import LLMClient
from .config import get_model_params
from .tool import Tool


class MinimaxClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        params = get_model_params("minimax", model)
        super().__init__(
            api_key=api_key,
            model=model or os.getenv("MINIMAX_MODEL") or params.get("model"),
            base_url=base_url,
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
        max_rounds: int = 5,
        **kwargs,
    ) -> str:
        key = self._get_key("MINIMAX_API_KEY")
        base_url = self._get_base_url("MINIMAX_BASE_URL")

        system_msg = None
        filtered = []
        for m in messages:
            if m.get("role") == "system":
                system_msg = m.get("content")
            else:
                filtered.append(m)

        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        params = get_model_params("minimax", self.model)

        for _ in range(max_rounds):
            payload = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", params.get("max_tokens", 1024)),
                "temperature": kwargs.get(
                    "temperature", params.get("temperature", 0.7)
                ),
                "messages": filtered,
            }
            if system_msg:
                payload["system"] = system_msg
            if anthropic_tools:
                payload["tools"] = anthropic_tools

            req = urllib.request.Request(
                f"{base_url}/v1/messages",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())

            content = data.get("content", [])
            text_parts = []
            tool_use_blocks = []

            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    tool_use_blocks.append(block)

            if not tool_use_blocks:
                return "".join(text_parts)

            assistant_content = []
            if text_parts:
                assistant_content.append({"type": "text", "text": "".join(text_parts)})
            for block in tool_use_blocks:
                assistant_content.append(block)

            filtered.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in tool_use_blocks:
                tool = next((t for t in (tools or []) if t.name == block["name"]), None)
                if not tool:
                    result = f"Tool {block['name']} not found"
                else:
                    try:
                        result = tool.run(block["input"])
                    except Exception as e:
                        result = f"Error: {e}"

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": str(result),
                    }
                )

            filtered.append({"role": "user", "content": tool_results})

        return ""
