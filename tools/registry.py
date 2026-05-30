"""
Tool registry.

Holds Tool definitions, exposes their JSON schemas to the LLM, and dispatches
tool calls to the underlying Python functions. The agent loop talks only to
this registry — it never knows what any individual tool does internally.
"""

import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict      # JSON schema for the arguments
    func: Callable        # the actual Python function

    def to_schema(self) -> dict:
        """OpenAI-compatible function/tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """
        Run a tool by name. Always returns a STRING (JSON) so it can be fed
        straight back to the LLM as a tool-result message. Errors are caught
        and returned as structured data so the agent can reason about them.
        """
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            result = tool.func(**arguments)
            return json.dumps(result, default=str)
        except TypeError as e:
            return json.dumps({
                "error": "bad_arguments",
                "detail": str(e),
                "expected_schema": tool.parameters,
            })
        except Exception as e:
            return json.dumps({
                "error": "tool_execution_failed",
                "detail": str(e),
                "trace": traceback.format_exc()[-500:],
            })
