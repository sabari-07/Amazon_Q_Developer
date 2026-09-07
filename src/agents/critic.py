"""
Critic agent: reviews the writer's answer and requests one revision if weak.

Call path:
  pipeline._execute()
    -> writer.write(state)        sets state["answer"]
    -> critic.critique(state)     reads state["answer"], may overwrite it

The critic makes one scoring invoke call. If the model's verdict begins
with "WEAK" (case-insensitive) it calls writer.write once more for a
revised answer and stores the verdict in state["critique"].
If the answer is acceptable the original answer is kept unchanged.
"""

from src import bedrock_client
from src.agents import writer


_SCORE_PROMPT = (
    "You are a strict quality reviewer. Read the answer below and reply with "
    "exactly one word on the first line: STRONG if it is clear, specific, and "
    "well-supported, or WEAK if it is vague, hollow, or unsupported. "
    "Optionally add a brief reason on a second line.\n\nAnswer:\n{answer}"
)


def critique(state) -> str:
    """
    Score the current answer. If weak, request one revision from the writer.
    Returns the final answer (original or revised).
    Stores the critic's verdict in state["critique"].
    """
    answer = state.get("answer") or ""
    verdict = bedrock_client.invoke(
        _SCORE_PROMPT.format(answer=answer), max_tokens=100
    )
    state.set("critique", verdict)

    if verdict.strip().upper().startswith("WEAK"):
        answer = writer.write(state)   # writer reads state["findings"] again

    return answer
