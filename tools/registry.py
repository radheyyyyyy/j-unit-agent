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

    def _coerce_arguments(self, tool: "Tool", arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Open models sometimes send wrong JSON types (boolean as "true",
        number as "5"). Coerce arguments to the types declared in the tool's
        schema so a sloppy type doesn't crash the call.
        """
        props = tool.parameters.get("properties", {})
        out = dict(arguments)
        for key, spec in props.items():
            if key not in out or out[key] is None:
                continue
            expected = spec.get("type")
            val = out[key]
            if expected == "boolean" and isinstance(val, str):
                out[key] = val.strip().lower() in ("true", "1", "yes")
            elif expected == "integer" and isinstance(val, str):
                try:
                    out[key] = int(val.strip())
                except ValueError:
                    pass
            elif expected == "number" and isinstance(val, str):
                try:
                    out[key] = float(val.strip())
                except ValueError:
                    pass
        return out

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
            args = self._coerce_arguments(tool, arguments)
            result = tool.func(**args)
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
