from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


SYSTEM_PROMPT = (
    "You are a Software Architect. Your job is to produce a short, clear design "
    "document for a Python program based on the user's request.\n\n"
    "The design document should include:\n"
    "- Purpose of the program\n"
    "- Expected behavior and output\n"
    "- Any modules, functions, or classes needed\n\n"
    "Keep it concise — a few paragraphs at most. Output ONLY the design document, "
    "no code."
)

def _get_llm():
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0)


def architect_node(state: dict) -> dict:
    """Produce or revise a design document based on the request and any feedback."""
    llm = _get_llm()
    iteration = state.get("iteration", 0)
    request = state["request"]
    feedback = state.get("feedback", "")

    if iteration == 0:
        user_content = f"Design a program for the following request:\n\n{request}"
    else:
        user_content = (
            f"Original request:\n{request}\n\n"
            f"The Tester rejected the previous iteration. Here is their feedback:\n"
            f"{feedback}\n\n"
            f"Please revise the design to address this feedback."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    print(f"\n{'='*60}")
    print(f"ARCHITECT (iteration {iteration + 1})")
    print(f"{'='*60}")
    print(f"\n--- SYSTEM PROMPT ---")
    print(SYSTEM_PROMPT)
    print(f"\n--- INPUT (from User/Tester) ---")
    print(user_content)

    response = llm.invoke(messages)
    design = response.content

    print(f"\n--- OUTPUT (to Developer) ---")
    print(design)

    return {"design": design}
