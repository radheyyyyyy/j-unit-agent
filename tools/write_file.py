"""Tool: write_file — write generated content to disk, creating directories."""

from pathlib import Path

from tools.registry import Tool


def write_file(path: str, content: str) -> dict:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(p),
            "bytes_written": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(p)}


TOOL = Tool(
    name="write_file",
    description="Write text content to a file, creating parent directories as needed. Use to save a generated test class.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Destination file path (e.g. the test_path from check_test_exists)."},
            "content": {"type": "string", "description": "The full file content to write."},
        },
        "required": ["path", "content"],
    },
    func=write_file,
)
