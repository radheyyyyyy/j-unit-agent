"""
ReAct loop.

The engine: Reason -> Act (call a tool) -> Observe (read result) -> repeat.

Each iteration:
  1. Send the full message history + tool schemas to the LLM.
  2. If the LLM returns tool calls -> execute each, append results, loop.
  3. If the LLM returns plain text (no tool calls) -> it's done. Stop.
  4. If max_steps is hit -> stop defensively.
"""

import json

from providers.base import LLMProvider
from tools.registry import ToolRegistry
from agent.memory import Memory


# ANSI colors for readable terminal output
class C:
    DIM = "\033[2m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    END = "\033[0m"


class ReActLoop:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        memory: Memory,
        max_steps: int = 80,
        verbose: bool = True,
    ):
        self.provider = provider
        self.registry = registry
        self.memory = memory
        self.max_steps = max_steps
        self.verbose = verbose

    def _say(self, text: str) -> None:
        if self.verbose:
            print(text)

    def run(self, system_prompt: str, goal: str) -> str:
        self.memory.add_message({"role": "system", "content": system_prompt})
        self.memory.add_message({"role": "user", "content": goal})

        tools = self.registry.schemas()

        for step in range(1, self.max_steps + 1):
            self._say(f"{C.DIM}── step {step}/{self.max_steps} ──{C.END}")

            response = self.provider.chat(messages=self.memory.messages, tools=tools)

            # --- Case 1: agent is reasoning out loud (text, no tools) => done ---
            if not response.wants_tools:
                final = response.content or "(no final message)"
                self._say(f"{C.GREEN}{C.BOLD}✓ Agent finished.{C.END}")
                self.memory.add_message({"role": "assistant", "content": final})
                return final

            # --- Case 2: agent wants to call tools ---
            # Record the assistant turn (with its tool_calls) in OpenAI format
            assistant_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            self.memory.add_message(assistant_msg)

            if response.content:
                self._say(f"{C.BLUE}reason:{C.END} {response.content.strip()[:300]}")

            # Execute each requested tool, append results
            for tc in response.tool_calls:
                arg_preview = self._preview_args(tc.arguments)
                self._say(f"{C.YELLOW}→ {tc.name}{C.END}({arg_preview})")

                result = self.registry.execute(tc.name, tc.arguments)
                self._say(f"{C.DIM}  ← {self._preview_result(result)}{C.END}")

                self.memory.add_message({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # --- Case 3: ran out of steps ---
        self._say(f"{C.RED}⚠ Reached max_steps ({self.max_steps}). Stopping.{C.END}")
        return "Stopped: reached max_steps before the agent declared completion."

    # --- pretty-printing helpers ---
    @staticmethod
    def _preview_args(args: dict) -> str:
        parts = []
        for k, v in args.items():
            s = str(v)
            if len(s) > 60:
                s = s[:57] + "..."
            parts.append(f"{k}={s!r}")
        return ", ".join(parts)

    @staticmethod
    def _preview_result(result: str) -> str:
        return result[:160] + ("..." if len(result) > 160 else "")
