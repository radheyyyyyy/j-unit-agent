"""
Orchestrator.

The top-level controller. It:
  - builds the LLM provider from config
  - builds the tool registry and registers all 7 tools
  - builds memory
  - composes the system prompt (the agent's operating instructions)
  - runs the ReAct loop toward the goal
  - prints the final summary
"""

from providers.openai_compatible import OpenAICompatibleProvider
from tools.registry import ToolRegistry
from tools import scan_project, read_file, analyze_class, check_test_exists, write_file, validate_test
from tools.generate_test import make_generate_test_tool
from tools.report_progress import make_report_progress_tool
from agent.memory import Memory
from agent.react_loop import ReActLoop


SYSTEM_PROMPT = """\
You are an autonomous Java test-generation agent. Your job is to generate
comprehensive JUnit 5 + Mockito test classes for every testable class in a
Java project, fully autonomously, by calling tools.

You operate in a ReAct loop: reason about the next step, call a tool, observe
the result, then continue. Work methodically, one file at a time.

WORKFLOW
1. Call scan_project FIRST to learn the build tool, src_root, test_root, and
   the list of .java files. Remember build_tool, src_root and test_root.
   If scan_project returns an "error" (e.g. source root not found, or
   build_tool "unknown"), DO NOT keep calling tools. Stop immediately and
   tell the user the project root looks wrong and they should pass the correct
   --project path (the folder containing pom.xml or build.gradle).
2. For EACH source file, in order:
   a. read_file to get its content.
   b. analyze_class on that content. If "testable" is false, call
      report_progress(status="skipped", ...) and move to the next file.
   c. check_test_exists. If it exists and you were not told to overwrite,
      call report_progress(status="exists", ...) and move on.
   d. generate_test using the source, package, class_name, and is_spring.
   e. write_file to the test_path from check_test_exists, using the test_code.
   f. validate_test with the test's fully-qualified name (package + class +
      "Test"), the project_root, and build_tool. THIS IS MANDATORY.
   g. If validate_test reports compiled=false or passed=false:
        - Read compile_errors / failures / raw_tail.
        - Call generate_test AGAIN, passing error_feedback (the errors) and
          previous_code (your last attempt) so it produces a fixed version.
        - write_file the corrected code, then validate_test again.
        - Repeat up to 3 fix attempts. If still failing after 3, call
          report_progress(status="error", ...) with the last error and move on.
   h. On success, report_progress(status="generated", ...).
3. When EVERY file has been handled, stop calling tools and write a short final
   summary in plain text (counts of generated/skipped/existing/errors).

RULES
- One file at a time. Do not batch many files into a single tool call.
- A test is only "generated" once validate_test confirms it compiles and passes.
- Never exceed 3 fix attempts per file — report it as an error and continue.
- If validate_test returns error="maven_not_installed" or "gradle_not_installed",
  the environment can't compile. Stop validating, write tests anyway, and note
  this clearly in your final summary.
- Never overwrite an existing test unless explicitly instructed.
- Do not invent file paths — use the paths returned by the tools.
- Finish only when all files are accounted for in the progress log.
"""


class Orchestrator:
    def __init__(self, config: dict):
        self.config = config

        prov = config["provider"]
        self.provider = OpenAICompatibleProvider(
            api_key=prov["api_key"],
            base_url=prov["base_url"],
            model=prov["model"],
            temperature=prov.get("temperature", 0.3),
            max_tokens=prov.get("max_tokens", 2048),
            max_retries=prov.get("max_retries", 4),
        )

        self.memory = Memory()
        self.registry = self._build_registry()

    def _build_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        # Stateless tools
        reg.register(scan_project.TOOL)
        reg.register(read_file.TOOL)
        reg.register(analyze_class.TOOL)
        reg.register(check_test_exists.TOOL)
        reg.register(write_file.TOOL)
        reg.register(validate_test.TOOL)
        # Tools that need injected dependencies
        reg.register(make_generate_test_tool(self.provider))
        reg.register(make_report_progress_tool(self.memory))
        return reg

    def _auto_max_steps(self, root: str) -> int:
        """
        Budget the loop automatically from the project size so the developer
        never has to set max_steps. A cheap filesystem pre-scan (no API call)
        counts the source files; we allow ~12 steps per file to leave room for
        the read/analyze/generate/validate/fix cycle, with a sensible floor.
        """
        try:
            from tools import scan_project
            scan = scan_project.scan_project(root)
            n = scan.get("java_file_count", 0) if "error" not in scan else 0
        except Exception:
            n = 0
        return max(40, n * 12)

    def run(self) -> str:
        proj = self.config["project"]
        agent_cfg = self.config["agent"]

        overwrite = proj.get("overwrite_existing", False)
        goal = (
            f"Generate JUnit 5 + Mockito tests for the Java project at "
            f"'{proj['root']}'. "
            + ("Overwrite existing test files. " if overwrite else
               "Do NOT overwrite tests that already exist. ")
            + "Begin by scanning the project."
        )

        # max_steps: "auto" (default) computes a budget from the file count.
        # A power user can still pin an explicit integer in config.
        configured = agent_cfg.get("max_steps", "auto")
        if isinstance(configured, int):
            max_steps = configured
        else:
            max_steps = self._auto_max_steps(proj["root"])
            if agent_cfg.get("verbose", True):
                print(f"  Auto step budget: {max_steps} "
                      f"(scales with project size)\n")

        loop = ReActLoop(
            provider=self.provider,
            registry=self.registry,
            memory=self.memory,
            max_steps=max_steps,
            verbose=agent_cfg.get("verbose", True),
            keep_recent=agent_cfg.get("keep_recent", 6),
            max_old_tool_chars=agent_cfg.get("max_old_tool_chars", 600),
        )

        final = loop.run(system_prompt=SYSTEM_PROMPT, goal=goal)

        print("\n" + "=" * 56)
        print(self.memory.summary())
        print("=" * 56)
        print("\nAgent's final word:\n" + final)
        return final
