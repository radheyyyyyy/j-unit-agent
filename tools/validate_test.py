"""
Tool: validate_test — compile and run a generated test, return structured results.

This is what makes the agent self-correcting. After writing a test, the agent
calls this to actually compile + run it. If it fails, the parsed errors are fed
back so the agent can regenerate a fixed version.

Supports Maven and Gradle. Targets the single test class so runs stay fast.
Network/JDK are the user's environment — the first Maven run downloads
dependencies and needs internet.
"""

import re
import shutil
import subprocess
from pathlib import Path

from tools.registry import Tool

DEFAULT_TIMEOUT = 300  # seconds


def _maven_cmd(test_fqn: str) -> list[str]:
    # test-compile + run only this test class; don't fail the run if no tests match
    return [
        "mvn", "-q", "-DfailIfNoTests=false",
        f"-Dtest={test_fqn}", "test",
    ]


def _gradle_cmd(test_fqn: str, root: Path) -> list[str]:
    wrapper = root / ("gradlew.bat" if shutil.which("cmd") and (root / "gradlew.bat").exists() else "gradlew")
    gradle = str(wrapper) if wrapper.exists() else "gradle"
    return [gradle, "test", "--tests", test_fqn, "--console=plain"]


def _parse_maven(output: str) -> dict:
    compiled = "COMPILATION ERROR" not in output and "BUILD FAILURE" not in output or "Tests run" in output
    compile_errors = re.findall(r'\[ERROR\].*?\.java:\[\d+,\d+\].*', output)
    # Surefire summary line: "Tests run: 5, Failures: 1, Errors: 0, Skipped: 0"
    summary = re.search(
        r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)',
        output,
    )
    build_success = "BUILD SUCCESS" in output
    has_compile_error = "COMPILATION ERROR" in output or bool(compile_errors)

    result = {
        "compiled": not has_compile_error,
        "passed": build_success and not has_compile_error,
        "build_success": build_success,
    }
    if summary:
        result["tests_run"] = int(summary.group(1))
        result["failures"] = int(summary.group(2))
        result["errors"] = int(summary.group(3))
        result["skipped"] = int(summary.group(4))
    if has_compile_error:
        result["compile_errors"] = compile_errors[:15] or ["See raw output for compilation error."]
    return result


def _parse_gradle(output: str) -> dict:
    build_success = "BUILD SUCCESSFUL" in output
    has_compile_error = "error:" in output or "Compilation failed" in output
    compile_errors = re.findall(r'.*\.java:\d+:\s*error:.*', output)
    failure_block = re.findall(r'.*FAILED\s*$', output, re.MULTILINE)
    return {
        "compiled": not has_compile_error,
        "passed": build_success and not has_compile_error,
        "build_success": build_success,
        "compile_errors": compile_errors[:15] if has_compile_error else [],
        "test_failures": failure_block[:15],
    }


def validate_test(
    test_fqn: str,
    project_root: str,
    build_tool: str,
) -> dict:
    """
    test_fqn:     fully-qualified test class, e.g. com.example.service.UserServiceTest
    project_root: the project root (where pom.xml / build.gradle lives)
    build_tool:   "maven" or "gradle"
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        return {"error": f"project_root not found: {root}"}

    if build_tool == "maven":
        if not shutil.which("mvn"):
            return {"error": "maven_not_installed",
                    "hint": "Install Maven, or set build_tool appropriately."}
        cmd = _maven_cmd(test_fqn)
    elif build_tool == "gradle":
        cmd = _gradle_cmd(test_fqn, root)
        if not (shutil.which("gradle") or (root / "gradlew").exists()):
            return {"error": "gradle_not_installed",
                    "hint": "Install Gradle or ensure ./gradlew exists."}
    else:
        return {"error": f"unsupported_build_tool: {build_tool}"}

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "seconds": DEFAULT_TIMEOUT,
                "hint": "The build took too long; the project may be large or offline."}
    except Exception as e:
        return {"error": "execution_failed", "detail": str(e)}

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = _parse_maven(output) if build_tool == "maven" else _parse_gradle(output)

    # Give the agent the tail of the log (where errors live) without flooding it
    parsed["raw_tail"] = output[-2500:]
    parsed["exit_code"] = proc.returncode
    return parsed


TOOL = Tool(
    name="validate_test",
    description=(
        "Compile and run a generated test class using the project's build tool "
        "(Maven or Gradle). Returns whether it compiled and passed, plus any "
        "compilation errors or test failures. If 'compiled' is false or 'passed' "
        "is false, read the errors and compile_errors/raw_tail, then call "
        "generate_test again WITH the error_feedback to fix it, rewrite, and "
        "re-validate. Always validate after writing a test."
    ),
    parameters={
        "type": "object",
        "properties": {
            "test_fqn": {
                "type": "string",
                "description": "Fully-qualified test class name, e.g. com.example.UserServiceTest",
            },
            "project_root": {
                "type": "string",
                "description": "Project root containing pom.xml or build.gradle.",
            },
            "build_tool": {
                "type": "string",
                "enum": ["maven", "gradle"],
                "description": "Build tool from scan_project.",
            },
        },
        "required": ["test_fqn", "project_root", "build_tool"],
    },
    func=validate_test,
)
