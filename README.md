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
## Getting Started

An autonomous agent that generates and self-validates JUnit 5 + Mockito tests
for any Java project. Follow these steps to use it on your own project.

### Prerequisites

- Python 3.10 or newer
- A Groq API key (free at https://console.groq.com/keys)
- Your Java project must use a standard Maven or Gradle layout (`src/main/java/...`)
- For test validation: Maven (`mvn`) or Gradle (`gradle` / `./gradlew`) installed.
  Without it, tests are still generated but not compiled/checked.

### 1. Clone the repo

```bash
git clone https://github.com/radheyyyyyy/j-unit-agent.git
cd j-unit-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your API key

```bash
cp config.example.yaml config.yaml
```

Then open `config.yaml` and paste your Groq key into `provider.api_key`:

```yaml
provider:
  api_key: "gsk_your_real_key_here"
  base_url: "https://api.groq.com/openai/v1"
  model: "openai/gpt-oss-120b"
```

> `config.yaml` is gitignored, so your key is never committed.

### 4. Verify the setup

```bash
python -c "from agent.orchestrator import Orchestrator; print('structure OK')"
```

If it prints `structure OK`, you're ready.

### 5. Run it on your Java project

```bash
python main.py --project /full/path/to/your/java-project
```

Point `--project` at the folder containing your `pom.xml` or `build.gradle`.

The agent will scan the project, generate a test for each testable class,
compile and run each test, fix any that fail, and print a summary. Generated
tests are written into your project's `src/test/java/...`.

### Reviewing the results

Generated tests land in your project's test directory. If your project is under
git, review them before keeping:

```bash
cd /path/to/your/java-project
git status      # see the new test files
git diff        # review generated tests
```

### Switching models or providers

Edit `config.yaml` only -- no code changes needed. Any OpenAI-compatible
endpoint works (Groq, OpenAI, OpenRouter, Together, Ollama). See the
Configuration section for base URLs.

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

## Config reference (config.yaml)

| Field | Meaning |
|---|---|
| provider.api_key | Your API key |
| provider.base_url | OpenAI-compatible endpoint |
| provider.model | Model name |
| provider.temperature | Lower = more deterministic (0.3 default) |
| agent.max_steps | Safety cap on loop iterations |
| agent.verbose | Print reasoning + tool calls |
| project.root | Default project to target |
| project.overwrite_existing | Regenerate tests that already exist |

---

## Requirements

- Python 3.10+
- An API key for any OpenAI-compatible provider
- For validation: Maven or Gradle installed, standard project layout
