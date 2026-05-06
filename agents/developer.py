from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


SYSTEM_PROMPT = (
    "You are a Software Developer. Your job is to write Python code based on "
    "the design document provided by the Architect.\n\n"
    "Rules:\n"
    "- Output ONLY valid Python code, no markdown fences or explanations.\n"
    "- The code must be complete and runnable as-is.\n"
    "- Follow the design document exactly."
)

def _get_llm():
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0)


def developer_node(state: dict) -> dict:
    """Write or revise Python code based on the Architect's design and any feedback."""
    llm = _get_llm()
    iteration = state.get("iteration", 0)
    design = state["design"]
    feedback = state.get("feedback", "")

    if iteration == 0 or not feedback:
        user_content = (
            f"Write Python code based on this design document:\n\n{design}"
        )
    else:
        user_content = (
            f"Design document:\n{design}\n\n"
            f"The Tester rejected the previous code. Here is their feedback:\n"
            f"{feedback}\n\n"
            f"Please fix the code to address this feedback."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    print(f"\n{'='*60}")
    print(f"DEVELOPER (iteration {iteration + 1})")
    print(f"{'='*60}")
    print(f"\n--- SYSTEM PROMPT ---")
    print(SYSTEM_PROMPT)
    print(f"\n--- INPUT (from Architect) ---")
    print(user_content)

    response = llm.invoke(messages)
    code = response.content

    print(f"\n--- OUTPUT (to Tester) ---")
    print(code)

    return {"code": code}
