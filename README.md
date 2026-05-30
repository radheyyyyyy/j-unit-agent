# JUnit Agent

An autonomous agentic AI that generates **and self-validates** JUnit 5 + Mockito
tests for any Java project.

It runs a real ReAct loop (Reason -> Act -> Observe -> repeat): it reasons about
each class, generates a test, **compiles and runs it**, reads any failures, and
**rewrites the test until it passes** -- all on its own.

---

## What makes it agentic (not just a script)

- The LLM decides the next action each step from a tool registry
- After writing each test it calls `validate_test` to actually compile + run it
- On failure it reads the compiler/test errors and regenerates a fixed version
- It retries up to 3 times per file, then logs an error and moves on
- It keeps memory of progress and decides for itself when the whole job is done

---

## Architecture

```
config.yaml          <- you edit this (API key, model, base_url)
main.py              <- entry point: python main.py

providers/           <- knows about LLM APIs (nothing about Java)
  base.py              abstract LLMProvider interface
  openai_compatible.py one adapter: Groq / OpenAI / OpenRouter / Together / Ollama

tools/               <- knows about Java files (nothing about LLM APIs)
  registry.py          holds tools, exposes schemas, dispatches calls
  scan_project.py      detect build tool, list .java files
  read_file.py         read a source file
  analyze_class.py     extract package, class, methods, deps, testability
  check_test_exists.py compute test path, check if it exists
  generate_test.py     focused LLM call to write (or FIX) the test
  validate_test.py     compile + run the test, parse pass/fail + errors  <- the key one
  write_file.py        write the test to disk
  report_progress.py   record progress into memory

agent/               <- knows about neither -- just runs the loop
  orchestrator.py      builds everything, holds the system prompt
  react_loop.py        the Reason/Act/Observe engine
  memory.py            conversation + facts + progress log
```

---

## Setup & run (simple)

```bash
# 1. install the two dependencies
pip install -r requirements.txt

# 2. create your config from the template
cp config.example.yaml config.yaml

# 3. edit config.yaml -> paste your Groq key into provider.api_key
#    (get one free at https://console.groq.com/keys)

# 4. run it against any Java project
python main.py --project /path/to/your/java-project
```

That's it. The agent scans the project, generates tests, validates each one,
self-corrects failures, and prints a summary.

---

## Running on any project

Keep the `junit-agent` folder anywhere and point it at a project:

```bash
python main.py --project ~/code/my-spring-app
python main.py --project ../another-java-repo
python main.py --config config.yaml --project /abs/path/to/project
```

**Requirement for the validation loop:** the machine needs the project's build
tool installed (`mvn` for Maven, `gradle` or `./gradlew` for Gradle) and internet
on first run (to download dependencies). If neither is installed, the agent still
writes the tests but skips validation and says so in the summary.

---

## A real run looks like

```
step 1  -> scan_project        18 files (maven)
step 2  -> read_file           UserService.java
step 3  -> analyze_class       class, @Service, testable
step 4  -> check_test_exists   no existing test
step 5  -> generate_test       wrote UserServiceTest (v1)
step 6  -> write_file          saved
step 7  -> validate_test       compiled=false  <- cannot find symbol
step 8  -> generate_test       FIX using the error feedback
step 9  -> write_file          saved (v2)
step 10 -> validate_test       compiled=true passed=true  OK
step 11 -> report_progress     generated
step 12 -> read_file           next file...
...
        Agent finished         summary printed
```

---

## Switching models / providers (config only, no code change)

| Provider | base_url | example model |
|---|---|---|
| Groq | https://api.groq.com/openai/v1 | openai/gpt-oss-120b |
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| OpenRouter | https://openrouter.ai/api/v1 | meta-llama/llama-3.3-70b-instruct |
| Together | https://api.together.xyz/v1 | meta-llama/Llama-3.3-70B-Instruct-Turbo |
| Ollama (local) | http://localhost:11434/v1 | llama3.3 (api_key blank) |

All speak the OpenAI protocol, so the single `OpenAICompatibleProvider` handles
them. To add a non-OpenAI protocol (e.g. native Anthropic), add one new class in
`providers/` implementing `LLMProvider` -- nothing else changes.

---

## Putting it on GitHub

Safe to publish -- **as long as you never commit `config.yaml`** (it holds your
API key). The included `.gitignore` excludes it, and `config.example.yaml` is
committed in its place as a template.

```bash
cd junit-agent
git init
git add .
git commit -m "Initial commit: autonomous JUnit test-generation agent"
# create an empty repo on github.com first, then:
git remote add origin https://github.com/<you>/junit-agent.git
git branch -M main
git push -u origin main
```

Before your first push, confirm the key isn't staged:

```bash
git status                    # config.yaml should NOT appear
git ls-files | grep config    # should show only config.example.yaml
```

If you ever commit a key by accident: rotate it immediately in the Groq console
(removing it in a later commit does NOT remove it from git history).

---

## Config reference (config.yaml)

| Field | Meaning |
|---|---|
| provider.api_key | Your API key |
| provider.base_url | OpenAI-compatible endpoint |
| provider.model | Model name |
| provider.temperature | Lower = more deterministic (0.3 default) |
| agent.max_steps | `auto` (scales with project size) or pin an int |
| agent.verbose | Print reasoning + tool calls |
| project.root | Default project to target |
| project.overwrite_existing | Regenerate tests that already exist |

---

## Requirements

- Python 3.10+
- An API key for any OpenAI-compatible provider
- For validation: Maven or Gradle installed, standard project layout
