# Spec: Multi-Agent "Hello World" Generator

## Problem Statement

Build a Python program that uses three LangGraph-based AI agents — Architect, Developer, and Tester — to collaboratively produce a working "Hello World" Python program. The agents communicate in an iterative loop: the Tester can reject output and send it back for fixes, up to 5 retries.

## Requirements

### Agents

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Architect** | Designs the structure/spec for the Hello World program | User request or Tester feedback | A short design document (plain text) describing what the program should do |
| **Developer** | Writes Python code based on the Architect's design | Architect's design document | Python source code as a string |
| **Tester** | Reviews and validates the Developer's code | Developer's code + Architect's design | `PASS` or `FAIL` with feedback |

### Framework & LLM

- **Agent orchestration**: LangGraph (from the `langgraph` package)
- **LLM provider**: Groq with Llama 3.1 8B Instant (via `langchain-groq`)
- **API key**: Read from `GROQ_API_KEY` environment variable

### Workflow

```
User Request
     │
     ▼
 ┌──────────┐
 │ Architect │──── design ────┐
 └──────────┘                 │
      ▲                       ▼
      │                 ┌───────────┐
  feedback              │ Developer │── code ──┐
  (on FAIL)             └───────────┘          │
      │                       ▲                ▼
      │                   feedback        ┌────────┐
      │                   (on FAIL)       │ Tester │
      │                       │           └────────┘
      │                       │                │
      └───────────────────────┴── FAIL ────────┘
                                               │
                                            PASS
                                               │
                                               ▼
                                        Print result
                                        to console
```

1. **Architect** receives the request ("create a Hello World program in Python") and produces a design.
2. **Developer** receives the design and writes Python code.
3. **Tester** receives the code and design, then either:
   - Returns `PASS` → workflow ends, final code is printed to console.
   - Returns `FAIL` with feedback → loop back. Feedback is sent to both Architect and Developer for the next iteration.
4. Maximum **5 retry cycles**. If the Tester still fails after 5 iterations, print the last code attempt with a warning.

### Output

- All agent interactions and the final generated code are printed to **console (stdout)**.
- No files are written to disk by the agents.

### Dev Container

- Update `.devcontainer/devcontainer.json` to add the Python dev container feature so Python is available in the environment.

## Project Structure

```
ONA/
├── .devcontainer/
│   └── devcontainer.json        # Updated with Python feature
├── requirements.txt             # langgraph, langchain-groq, langchain-core
├── main.py                      # Entry point — builds and runs the LangGraph workflow
├── agents/
│   ├── __init__.py
│   ├── architect.py             # Architect agent node
│   ├── developer.py             # Developer agent node
│   └── tester.py                # Tester agent node
├── graph.py                     # LangGraph graph definition and state schema
└── spec.md
```

## Acceptance Criteria

1. Running `python main.py` starts the multi-agent workflow and prints output to the console.
2. The Architect produces a design document for a Hello World program.
3. The Developer produces valid Python code based on the design.
4. The Tester evaluates the code and returns PASS or FAIL with feedback.
5. On FAIL, the loop retries (max 5 times) with feedback passed back to Architect and Developer.
6. On PASS (or after 5 retries), the final generated code is printed to stdout.
7. The program uses LangGraph for orchestration and Groq (Llama 3.1 8B Instant) as the LLM.
8. `GROQ_API_KEY` is read from the environment — the program exits with a clear error if it is missing.
9. Python is available in the dev container after rebuilding.

## Implementation Steps

1. Update `.devcontainer/devcontainer.json` to add the Python feature.
2. Install Python in the current environment (manual install for immediate use).
3. Create `requirements.txt` with dependencies: `langgraph`, `langchain-anthropic`, `langchain-core`.
4. Install dependencies via `pip install -r requirements.txt`.
5. Create `agents/` package with `__init__.py`.
6. Implement `agents/architect.py` — Architect agent node function.
7. Implement `agents/developer.py` — Developer agent node function.
8. Implement `agents/tester.py` — Tester agent node function.
9. Implement `graph.py` — define the LangGraph state schema, graph, nodes, edges, and conditional routing.
10. Implement `main.py` — entry point that builds the graph and invokes it.
11. Test the program end-to-end with `python main.py`.
