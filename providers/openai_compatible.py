"""
OpenAI-compatible provider.

Works with any endpoint that speaks the OpenAI chat-completions protocol:
Groq, OpenAI, OpenRouter, Together, Fireworks, local Ollama, etc.
Only the base_url + api_key + model change — never this code.
"""

import json
import re
import time
from typing import Optional

from openai import OpenAI, RateLimitError, APIStatusError, BadRequestError

from .base import LLMProvider, LLMResponse, ToolCall


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        max_retries: int = 4,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            completion = self._create_with_retry(kwargs)
        except BadRequestError as e:
            # Open models (Llama etc.) sometimes emit a tool call that fails
            # the API's schema validation (e.g. boolean sent as the string
            # "true"). Rather than crash, hand the error back to the model so
            # it can correct itself on the next turn.
            detail = str(e)
            if "tool_use_failed" in detail or "did not match schema" in detail:
                return LLMResponse(
                    content=(
                        "Your previous tool call was rejected because the "
                        "arguments did not match the tool's schema. Check the "
                        "parameter types carefully — booleans must be true/false "
                        "(not the strings \"true\"/\"false\"), numbers must be "
                        "unquoted — and call the tool again correctly."
                    ),
                    tool_calls=[],
                    finish_reason="invalid_tool_call",
                )
            raise

        choice = completion.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
        )

    def _create_with_retry(self, kwargs: dict):
        """
        Call the API, retrying on rate-limit errors with backoff.

        Groq returns 429 (RateLimitError) and sometimes 413 for TPM limits.
        The message often contains 'try again in 4.2s' — we honor that when
        present, otherwise use exponential backoff.
        """
        delay = 2.0
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.chat.completions.create(**kwargs)
            except (RateLimitError, APIStatusError) as e:
                last_err = e
                status = getattr(e, "status_code", None)
                # Only retry rate-limit style errors; re-raise everything else.
                if status not in (429, 413):
                    raise
                if attempt == self.max_retries:
                    break
                wait = self._suggested_wait(str(e)) or delay
                print(f"  ⏳ rate limited; waiting {wait:.1f}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
                delay = min(delay * 2, 30)
        raise last_err

    @staticmethod
    def _suggested_wait(message: str) -> Optional[float]:
        m = re.search(r'try again in ([\d.]+)\s*s', message)
        if m:
            return float(m.group(1)) + 0.5
        return None
