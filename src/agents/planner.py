"""
Planner agent: turns the user's question into a list of sub-tasks.

Seeded flaws:
- Parses the model output with a naive split; a differently-formatted
  response silently produces junk subtasks or an empty list.
- No guard for an empty question.
"""

from src import bedrock_client


def plan(state):
    question = state.get("question")

    prompt = (
        "Break the following research question into 3 to 5 concise, "
        "numbered sub-tasks. Question: " + question
    )
    raw = bedrock_client.invoke(prompt, max_tokens=300)

    # Naive parsing (seeded smell): assumes one subtask per line.
    subtasks = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        # strips a leading "1." / "2)" etc. crudely
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            subtasks.append(cleaned)

    state.set("subtasks", subtasks)
    return subtasks
