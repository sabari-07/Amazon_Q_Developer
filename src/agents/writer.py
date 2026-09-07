"""
Writer agent: composes the final answer from the researcher's findings.

Seeded flaws:
- Assumes findings is non-empty; with zero findings it still calls the
  model with an empty context and returns a hollow answer.
- Concatenates findings without any length budget (can blow past the
  model's context window on large inputs).
"""

from src import bedrock_client


def write(state):
    question = state.get("question")
    findings = state.get("findings") or []

    context = "\n".join(f"- {f['subtask']}: {f['finding']}" for f in findings)
    prompt = (
        "Using only the notes below, write a clear 1-paragraph answer to "
        f"the question '{question}'.\n\nNotes:\n{context}"
    )
    answer = bedrock_client.invoke(prompt, max_tokens=500)

    state.set("answer", answer)
    return answer
