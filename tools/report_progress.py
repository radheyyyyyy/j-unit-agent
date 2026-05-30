"""
Tool: report_progress — record a progress entry into the agent's memory.

Built via a factory so the live Memory object is injected at registration.
This is how the agent keeps a running, inspectable record of what it has done
across the whole run (used for the final summary).
"""

from tools.registry import Tool


def make_report_progress_tool(memory) -> Tool:
    def report_progress(status: str, file: str = "", detail: str = "") -> dict:
        memory.log_progress(status=status, file=file, detail=detail)
        return {
            "recorded": True,
            "totals": memory.totals(),
        }

    return Tool(
        name="report_progress",
        description=(
            "Record what you just did for one file so the run has an auditable "
            "log. Call after generating/skipping each file. status should be one "
            "of: generated, skipped, exists, error."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["generated", "skipped", "exists", "error"],
                    "description": "Outcome for this file.",
                },
                "file": {"type": "string", "description": "The source file this refers to."},
                "detail": {"type": "string", "description": "Short reason or note."},
            },
            "required": ["status"],
        },
        func=report_progress,
    )
