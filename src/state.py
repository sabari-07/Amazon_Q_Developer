"""
Shared state passed between agents in the pipeline.

Seeded flaw: this is a single mutable dict shared across all agents with
no isolation. Agents both read and overwrite the same keys, so ordering
bugs and accidental clobbering are easy. A refactor should introduce
clearer boundaries (e.g., an immutable record per step, or explicit
inputs/outputs per agent).
"""


class SharedState:
    def __init__(self, question: str):
        self.data = {
            "question": question,
            "subtasks": [],
            "findings": [],
            "answer": None,
            "critique": None,
            "errors": [],
        }

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        # No validation, no copy: callers can mutate nested structures in place.
        self.data[key] = value

    def append(self, key, value):
        self.data.setdefault(key, []).append(value)
