"""Tool: check_test_exists — determine the test path and whether it already exists."""

from pathlib import Path

from tools.registry import Tool


def check_test_exists(source_path: str, src_root: str, test_root: str) -> dict:
    src = Path(source_path)
    src_root_p = Path(src_root)
    test_root_p = Path(test_root)

    try:
        rel = src.relative_to(src_root_p)
    except ValueError:
        return {
            "error": "source_not_under_src_root",
            "source_path": source_path,
            "src_root": src_root,
        }

    test_path = test_root_p / rel.parent / (rel.stem + "Test" + rel.suffix)
    return {
        "test_path": str(test_path),
        "exists": test_path.exists(),
    }


TOOL = Tool(
    name="check_test_exists",
    description=(
        "Compute the conventional test file path for a given source file "
        "(mirrors the package under the test root, appends 'Test') and report "
        "whether that test already exists. Call before generating, to avoid "
        "overwriting work."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_path": {"type": "string", "description": "Path to the source .java file."},
            "src_root": {"type": "string", "description": "Source root (from scan_project)."},
            "test_root": {"type": "string", "description": "Test root (from scan_project)."},
        },
        "required": ["source_path", "src_root", "test_root"],
    },
    func=check_test_exists,
)
