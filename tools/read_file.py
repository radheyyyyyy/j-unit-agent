"""Tool: read_file — read a Java source file from disk."""

from pathlib import Path

from tools.registry import Tool

MAX_BYTES = 100_000


def read_file(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"error": f"File not found: {path}"}

    size = p.stat().st_size
    if size > MAX_BYTES:
        return {
            "error": "file_too_large",
            "size_bytes": size,
            "limit_bytes": MAX_BYTES,
            "hint": "Skip this file; it is likely generated code.",
        }

    content = p.read_text(encoding="utf-8", errors="ignore")
    return {
        "path": str(p),
        "line_count": content.count("\n") + 1,
        "content": content,
    }


TOOL = Tool(
    name="read_file",
    description="Read the full text content of a Java source file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the .java file.",
            }
        },
        "required": ["path"],
    },
    func=read_file,
)
