from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


SYSTEM_PROMPT = (
    "You are a Software Tester. Your job is to review Python code against "
    "a design document and determine if it is correct.\n\n"
    "Evaluate:\n"
    "- Does the code match the design document?\n"
    "- Is the code syntactically valid Python?\n"
    "- Will it produce the expected output when run?\n"
    "- Are there any bugs or issues?\n\n"
    "Respond in EXACTLY this format:\n"
    "RESULT: PASS\n"
    "(or)\n"
    "RESULT: FAIL\n"
    "FEEDBACK: <your detailed feedback here>\n\n"
    "Be strict but fair. Only PASS if the code is correct and complete."
)

def _get_llm():
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0)


def tester_node(state: dict) -> dict:
    """Evaluate the Developer's code against the Architect's design."""
    llm = _get_llm()
    iteration = state.get("iteration", 0)
    design = state["design"]
    code = state["code"]

    user_content = (
        f"Design document:\n{design}\n\n"
        f"Code to review:\n{code}\n\n"
        f"Does this code correctly implement the design? "
        f"Respond with RESULT: PASS or RESULT: FAIL with FEEDBACK."
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    print(f"\n{'='*60}")
    print(f"TESTER (iteration {iteration + 1})")
    print(f"{'='*60}")
    print(f"\n--- SYSTEM PROMPT ---")
    print(SYSTEM_PROMPT)
    print(f"\n--- INPUT (from Developer + Architect) ---")
    print(user_content)

    response = llm.invoke(messages)
    result_text = response.content

    print(f"\n--- OUTPUT (verdict) ---")
    print(result_text)

    # Parse the result
    passed = "RESULT: PASS" in result_text.upper()

    feedback = ""
    if not passed:
        # Extract feedback after "FEEDBACK:" if present
        upper = result_text.upper()
        idx = upper.find("FEEDBACK:")
        if idx != -1:
            feedback = result_text[idx + len("FEEDBACK:"):].strip()
        else:
            feedback = result_text

    return {
        "test_result": "PASS" if passed else "FAIL",
        "feedback": feedback,
        "iteration": iteration + 1,
    }
