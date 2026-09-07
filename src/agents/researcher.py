"""
Researcher agent: produces a finding for each sub-task.

Seeded flaws:
- Runs strictly sequentially; a single failing subtask aborts the whole
  loop (no per-item try/except, no partial results).
- No dedup or relevance check on findings.
"""

from src import bedrock_client


def research(state):
    subtasks = state.get("subtasks") or []
    findings = []

    for subtask in subtasks:
        prompt = "Provide 2-3 factual sentences addressing: " + subtask
        # If this raises (throttling, bad payload), the entire pipeline dies
        # and all prior findings are lost because we only set state at the end.
        text = bedrock_client.invoke(prompt, max_tokens=250)
        findings.append({"subtask": subtask, "finding": text})
        state.set("findings", findings)  # persist after every item

    return findings
