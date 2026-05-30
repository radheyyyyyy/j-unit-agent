"""
Tool: analyze_class — extract structural metadata from Java source.

Lightweight regex-based parsing (no JVM needed). Gives the agent enough
information to decide whether a class is testable and what its surface is.
"""

import re

from tools.registry import Tool

_PACKAGE_RE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
_TYPE_RE = re.compile(
    r'(?:public\s+|final\s+|abstract\s+)*'
    r'(class|interface|enum|@interface|record)\s+([A-Z]\w*)'
)
_ANNOTATION_RE = re.compile(r'^\s*@(\w+)', re.MULTILINE)
# public/protected methods (skip private + constructors handled separately)
_METHOD_RE = re.compile(
    r'(?:public|protected)\s+'
    r'(?:static\s+|final\s+|synchronized\s+|<[^>]+>\s+)*'
    r'([\w<>\[\],.\s?]+?)\s+'      # return type
    r'(\w+)\s*\('                   # method name
    r'([^)]*)\)',                   # params
)


def analyze_class(source: str) -> dict:
    package_m = _PACKAGE_RE.search(source)
    package = package_m.group(1) if package_m else ""

    type_m = _TYPE_RE.search(source)
    if not type_m:
        return {"error": "could_not_detect_type", "testable": False}

    kind = type_m.group(1)        # class | interface | enum | @interface | record
    class_name = type_m.group(2)

    annotations = sorted(set(_ANNOTATION_RE.findall(source)))

    is_abstract = bool(re.search(r'\babstract\s+class\b', source))
    is_test = bool(re.search(r'class\s+\w+(Test|Tests|IT|Spec)\b', source))

    # Determine testability
    testable = True
    skip_reason = None
    if kind in ("interface", "enum", "@interface"):
        testable, skip_reason = False, f"{kind} (no behavior to test)"
    elif is_abstract:
        testable, skip_reason = False, "abstract class"
    elif is_test:
        testable, skip_reason = False, "already a test class"
    elif "SpringBootApplication" in annotations:
        testable, skip_reason = False, "Spring Boot entry point"

    methods = []
    for ret, name, params in _METHOD_RE.findall(source):
        ret = ret.strip()
        # Filter out false positives (e.g. matches inside generics)
        if name in ("if", "for", "while", "switch", "catch", "return"):
            continue
        methods.append({
            "name": name,
            "returns": ret,
            "params": params.strip(),
        })

    # Constructor dependencies (rough heuristic: constructor params)
    ctor_re = re.compile(rf'(?:public|protected)\s+{class_name}\s*\(([^)]*)\)')
    ctor_m = ctor_re.search(source)
    dependencies = []
    if ctor_m and ctor_m.group(1).strip():
        for param in ctor_m.group(1).split(","):
            parts = param.strip().split()
            if len(parts) >= 2:
                dependencies.append({"type": parts[-2], "name": parts[-1]})

    return {
        "package": package,
        "class_name": class_name,
        "kind": kind,
        "annotations": annotations,
        "testable": testable,
        "skip_reason": skip_reason,
        "public_method_count": len(methods),
        "methods": methods[:30],
        "dependencies": dependencies,
        "is_spring_component": any(
            a in annotations for a in ("Service", "Component", "Repository", "Controller", "RestController")
        ),
    }


TOOL = Tool(
    name="analyze_class",
    description=(
        "Analyze Java source code to extract its package, class name, kind "
        "(class/interface/enum), public methods, constructor dependencies, "
        "annotations, and whether it is worth testing. Use this to decide "
        "whether to generate a test and to inform the generation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "The full Java source code to analyze.",
            }
        },
        "required": ["source"],
    },
    func=analyze_class,
)
