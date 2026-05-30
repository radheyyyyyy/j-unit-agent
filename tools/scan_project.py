"""Tool: scan_project — discover project layout and list Java source files."""

from pathlib import Path

from tools.registry import Tool


def scan_project(root: str = ".") -> dict:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        return {"error": f"Not a directory: {root_path}"}

    # Detect build tool + source/test roots
    standard_src = root_path / "src" / "main" / "java"
    standard_test = root_path / "src" / "test" / "java"

    if (root_path / "pom.xml").exists():
        build_tool = "maven"
        src_root, test_root = standard_src, standard_test
    elif (root_path / "build.gradle").exists() or (root_path / "build.gradle.kts").exists():
        build_tool = "gradle"
        src_root, test_root = standard_src, standard_test
    else:
        build_tool = "unknown"
        src_root, test_root = standard_src, standard_test

    if not src_root.is_dir():
        return {
            "error": f"Source root not found: {src_root}",
            "build_tool": build_tool,
            "hint": "Confirm this is a standard Maven/Gradle project root.",
        }

    java_files = sorted(str(p) for p in src_root.rglob("*.java"))

    return {
        "build_tool": build_tool,
        "project_root": str(root_path),
        "src_root": str(src_root),
        "test_root": str(test_root),
        "java_file_count": len(java_files),
        "java_files": java_files,
    }


TOOL = Tool(
    name="scan_project",
    description=(
        "Scan a Java project root. Detects the build tool (Maven/Gradle), "
        "locates the source and test directories, and lists every .java "
        "source file. ALWAYS call this first."
    ),
    parameters={
        "type": "object",
        "properties": {
            "root": {
                "type": "string",
                "description": "Path to the Java project root. Defaults to '.'",
            }
        },
        "required": [],
    },
    func=scan_project,
)
