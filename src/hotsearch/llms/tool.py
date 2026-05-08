from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    execute: Callable[[dict], str] | None = None

    def run(self, arguments: dict) -> str:
        if self.execute:
            return self.execute(arguments)
        raise NotImplementedError(f"Tool {self.name} has no execute function")
