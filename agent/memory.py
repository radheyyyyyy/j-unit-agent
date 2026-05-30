"""
Agent memory.

Holds three things:
  - messages: the running conversation (system + user + assistant + tool results)
  - facts: structured discoveries (build tool, file list, etc.)
  - progress_log: an auditable record of what was done per file
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Memory:
    messages: list[dict] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    progress_log: list[dict] = field(default_factory=list)

    # --- conversation ---
    def add_message(self, message: dict) -> None:
        self.messages.append(message)

    # --- facts ---
    def remember(self, key: str, value: Any) -> None:
        self.facts[key] = value

    # --- progress ---
    def log_progress(self, status: str, file: str = "", detail: str = "") -> None:
        self.progress_log.append({"status": status, "file": file, "detail": detail})

    def totals(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for entry in self.progress_log:
            out[entry["status"]] = out.get(entry["status"], 0) + 1
        return out

    def summary(self) -> str:
        totals = self.totals()
        lines = ["Run summary:"]
        for status in ("generated", "exists", "skipped", "error"):
            if status in totals:
                lines.append(f"  {status:<10} {totals[status]}")
        if any(e["status"] == "error" for e in self.progress_log):
            lines.append("Errors:")
            for e in self.progress_log:
                if e["status"] == "error":
                    lines.append(f"  - {e['file']}: {e['detail']}")
        return "\n".join(lines)
