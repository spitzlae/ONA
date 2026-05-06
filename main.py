"""Multi-Agent Hello World Generator.

Uses three LangGraph agents (Architect, Developer, Tester) to collaboratively
produce a Hello World Python program via an iterative feedback loop.
"""

import os
import sys

from graph import build_graph


def main() -> None:
    # Check for Groq API key — supports both the Ona secret name and the standard env var
    api_key = os.environ.get("GROQ_Roche") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(
            "Error: Groq API key not found.\n"
            "Set it as an Ona secret (Settings > Secrets) named GROQ_Roche or GROQ_API_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)

    # langchain-groq reads GROQ_API_KEY from the environment
    os.environ["GROQ_API_KEY"] = api_key

    print("Starting Multi-Agent Hello World Generator...")
    print("Agents: Architect → Developer → Tester (iterative loop, max 5 retries)\n")

    app = build_graph()

    initial_state = {
        "request": "Create a Hello World program in Python",
        "design": "",
        "code": "",
        "test_result": "",
        "feedback": "",
        "iteration": 0,
    }

    result = app.invoke(initial_state)

    print(f"\n{'='*60}")
    print("FINAL RESULT")
    print(f"{'='*60}")
    print(f"Status: {result['test_result']}")
    print(f"Iterations: {result['iteration']}")
    print(f"\nGenerated Code:\n{result['code']}")


if __name__ == "__main__":
    main()
