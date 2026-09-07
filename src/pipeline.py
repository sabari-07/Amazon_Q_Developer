"""
Pipeline: sequences planner -> researcher -> writer.

Extracted from orchestrator.py so the Lambda handler stays thin.
Fixes all seeded flaws from the original orchestrator:
- retry loop actually retries with exponential backoff on retryable errors
- one failing subtask preserves prior findings (partial results)
- empty subtask list or empty findings raise PipelineError instead of
  silently producing a hollow answer
"""

import logging
import time

from botocore.exceptions import ClientError

from src.agents import planner, researcher, writer, critic
from src.state import SharedState

logger = logging.getLogger(__name__)

_RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"}


class PipelineError(Exception):
    pass


class Pipeline:
    def __init__(self, max_retries: int = 2, backoff_base: float = 0.5):
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def run(self, question: str) -> dict:
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                return self._execute(question)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code not in _RETRYABLE or attempt == self.max_retries - 1:
                    raise
                last_exc = exc
                wait = self.backoff_base * (2 ** attempt)
                logger.warning(
                    "attempt %d failed (%s), retrying in %.1fs", attempt + 1, code, wait
                )
                time.sleep(wait)
        raise PipelineError("all retries exhausted") from last_exc

    def _execute(self, question: str) -> dict:
        state = SharedState(question)

        subtasks = planner.plan(state)
        if not subtasks:
            raise PipelineError("planner returned no subtasks")

        findings = self._research_with_partial_results(state, subtasks)
        if not findings:
            raise PipelineError("researcher produced no findings")

        answer = writer.write(state)
        answer = critic.critique(state)
        return {
            "question": question,
            "subtasks": subtasks,
            "findings": findings,
            "answer": answer,
            "critique": state.get("critique"),
        }

    def _research_with_partial_results(self, state: SharedState, subtasks: list) -> list:
        """Run each subtask independently; skip on retryable errors, preserve prior findings."""
        findings = []
        for subtask in subtasks:
            try:
                state.set("subtasks", [subtask])
                partial = researcher.research(state)
                findings.extend(partial)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in _RETRYABLE:
                    logger.warning("skipping subtask %r after %s", subtask, code)
                else:
                    raise
        state.set("findings", findings)
        return findings
