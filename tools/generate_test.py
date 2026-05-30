"""
Tool: generate_test — generate a JUnit 5 + Mockito test class.

This tool makes its OWN focused LLM call with a specialized test-generation
prompt. The agent decides WHICH class to test; this tool does the actual
writing. Because it needs the LLM provider, it is built via a factory that
injects the provider at registration time.
"""

import re

from providers.base import LLMProvider
from tools.registry import Tool

_SYSTEM = (
    "You are a senior Java test-automation engineer. You write clean, "
    "compilable JUnit 5 test classes using Mockito and AssertJ. Your output "
    "is ALWAYS valid Java source only — no markdown, no fences, no prose."
)

_PROMPT = """\
Write a complete, compilable JUnit 5 test class for the Java source below.

RULES
- JUnit 5 Jupiter only (@Test, @BeforeEach, @ExtendWith, @Nested, @DisplayName,
  @ParameterizedTest, @ValueSource, @CsvSource). Never JUnit 4.
- Mockito: @ExtendWith(MockitoExtension.class), @Mock for collaborators,
  @InjectMocks for the class under test, @Captor where useful.
- Assertions: AssertJ assertThat(...); assertThatThrownBy(...) for exceptions.
- Test names: methodName_scenario_expectedBehavior (snake_case).
- Cover: happy path, null/empty inputs, boundary values, exception paths,
  and each distinct branch.
- Spring components (@Service/@Component/@Repository): test in isolation,
  no Spring context.
- Skip plain getters/setters and Lombok boilerplate.
- Include the package declaration and all imports.

Package: {package}
Class:   {class_name}
Spring component: {is_spring}

--- SOURCE ---
{source}
--- END SOURCE ---

Respond with ONLY the Java test file content.
"""

_FIX_PROMPT = """\
The test you generated FAILED to compile or pass. Fix it.

Class under test: {class_name}  (package {package})

--- SOURCE UNDER TEST ---
{source}
--- END SOURCE ---

--- YOUR PREVIOUS TEST ATTEMPT ---
{previous_code}
--- END PREVIOUS ATTEMPT ---

--- BUILD / TEST ERRORS ---
{error_feedback}
--- END ERRORS ---

Produce a corrected, complete JUnit 5 + Mockito test class that compiles and
passes. Fix the specific errors above (wrong imports, bad mock setup, wrong
method signatures, missing dependencies, incorrect assertions). Keep the same
conventions. Respond with ONLY the Java test file content.
"""


def _strip_fences(text: str) -> str:
    text = re.sub(r'^```(?:java)?\s*\n?', '', text.strip())
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def make_generate_test_tool(provider: LLMProvider) -> Tool:
    """Factory: build the generate_test tool with an injected LLM provider."""

    def generate_test(
        source: str,
        package: str = "",
        class_name: str = "",
        is_spring=False,
        error_feedback: str = "",
        previous_code: str = "",
    ) -> dict:
        # Open models sometimes send booleans as strings ("true"/"false").
        # Coerce defensively so a sloppy type doesn't break generation.
        if isinstance(is_spring, str):
            is_spring = is_spring.strip().lower() in ("true", "1", "yes")
        # Self-correction mode: a previous attempt failed, fix it using the errors
        if error_feedback and previous_code:
            prompt = _FIX_PROMPT.format(
                class_name=class_name or "(unknown)",
                package=package or "(default package)",
                source=source,
                previous_code=previous_code,
                error_feedback=error_feedback,
            )
        else:
            prompt = _PROMPT.format(
                package=package or "(default package)",
                class_name=class_name or "(unknown)",
                is_spring=is_spring,
                source=source,
            )
        resp = provider.chat(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tools=None,  # plain generation, no tool use here
        )
        code = _strip_fences(resp.content or "")
        if not code:
            return {"error": "empty_generation", "class_name": class_name}

        return {
            "class_name": class_name,
            "test_class_name": f"{class_name}Test",
            "test_code": code,
            "char_count": len(code),
        }

    return Tool(
        name="generate_test",
        description=(
            "Generate a complete JUnit 5 + Mockito test class for the given "
            "Java source. Pass the source plus the package, class name, and "
            "whether it is a Spring component (from analyze_class). Returns the "
            "test code as a string — you must then write it with write_file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Full Java source of the class under test."},
                "package": {"type": "string", "description": "Package name (from analyze_class)."},
                "class_name": {"type": "string", "description": "Class name (from analyze_class)."},
                "is_spring": {"type": "boolean", "description": "Whether the class is a Spring component."},
                "error_feedback": {
                    "type": "string",
                    "description": "When fixing a failed test, paste the compile_errors / failures / raw_tail from validate_test here.",
                },
                "previous_code": {
                    "type": "string",
                    "description": "When fixing, the previous test_code that failed.",
                },
            },
            "required": ["source", "class_name"],
        },
        func=generate_test,
    )
