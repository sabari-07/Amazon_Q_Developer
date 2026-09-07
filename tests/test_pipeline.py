import json
import time
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

from src.state import SharedState
from src.agents import planner, researcher, writer, critic
from src import orchestrator
from src.pipeline import Pipeline, PipelineError


MOCK_TARGET = "src.bedrock_client.invoke"


# ---------------------------------------------------------------------------
# planner.plan
# ---------------------------------------------------------------------------

def test_planner_returns_subtasks():
    raw = "1. Find background\n2. Analyse data\n3. Summarise results"
    with patch(MOCK_TARGET, return_value=raw):
        state = SharedState("What is quantum computing?")
        subtasks = planner.plan(state)

    assert subtasks == ["Find background", "Analyse data", "Summarise results"]
    assert state.get("subtasks") == subtasks


# ---------------------------------------------------------------------------
# researcher.research
# ---------------------------------------------------------------------------

def test_researcher_returns_findings():
    subtasks = ["Find background", "Analyse data"]
    responses = ["Background finding.", "Data finding."]

    with patch(MOCK_TARGET, side_effect=responses):
        state = SharedState("What is quantum computing?")
        state.set("subtasks", subtasks)
        findings = researcher.research(state)

    assert len(findings) == 2
    assert findings[0] == {"subtask": "Find background", "finding": "Background finding."}
    assert findings[1] == {"subtask": "Analyse data", "finding": "Data finding."}
    assert state.get("findings") == findings


# ---------------------------------------------------------------------------
# writer.write
# ---------------------------------------------------------------------------

def test_writer_returns_answer():
    findings = [
        {"subtask": "Find background", "finding": "Background finding."},
        {"subtask": "Analyse data", "finding": "Data finding."},
    ]
    expected = "Quantum computing uses qubits."

    with patch(MOCK_TARGET, return_value=expected):
        state = SharedState("What is quantum computing?")
        state.set("findings", findings)
        answer = writer.write(state)

    assert answer == expected
    assert state.get("answer") == expected


def test_writer_prompt_includes_question_and_findings():
    findings = [{"subtask": "T1", "finding": "F1"}]
    captured = {}

    def capture(prompt, **kwargs):
        captured["prompt"] = prompt
        return "answer"

    with patch(MOCK_TARGET, side_effect=capture):
        state = SharedState("My question")
        state.set("findings", findings)
        writer.write(state)

    assert "My question" in captured["prompt"]
    assert "T1" in captured["prompt"]
    assert "F1" in captured["prompt"]


# ---------------------------------------------------------------------------
# orchestrator.run_pipeline  (end-to-end)
# ---------------------------------------------------------------------------

def test_run_pipeline_happy_path():
    plan_raw = "1. Sub-task one\n2. Sub-task two"
    research_responses = ["Finding one.", "Finding two."]
    write_response = "Final answer."
    critique_response = "STRONG"

    invoke_responses = [plan_raw] + research_responses + [write_response, critique_response]

    with patch(MOCK_TARGET, side_effect=invoke_responses):
        result = orchestrator.run_pipeline("What is quantum computing?")

    assert result["question"] == "What is quantum computing?"
    assert result["subtasks"] == ["Sub-task one", "Sub-task two"]
    assert len(result["findings"]) == 2
    assert result["answer"] == "Final answer."
    assert result["critique"] == "STRONG"


def test_run_pipeline_result_keys():
    with patch(MOCK_TARGET, side_effect=["1. T1", "F1", "Answer.", "STRONG"]):
        result = orchestrator.run_pipeline("Q?")

    assert set(result.keys()) == {"question", "subtasks", "findings", "answer", "critique"}


# ===========================================================================
# FAILURE-PATH TESTS
# ===========================================================================

def _throttling_error():
    """Build a botocore ThrottlingException."""
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeModel",
    )


# ---------------------------------------------------------------------------
# 1. ThrottlingException mid-way through researcher.research
#    BUG EXPOSED: findings collected before the error are silently discarded
#    because researcher.research only calls state.set("findings", ...) at the
#    very end of the loop. The exception unwinds the stack before that line,
#    so state["findings"] stays [] and the partial results are lost.
# ---------------------------------------------------------------------------

def test_researcher_throttle_preserves_prior_findings():
    """
    researcher.research now writes to state after every item, so findings
    collected before the exception are not lost.
    """
    subtasks = ["T1", "T2"]
    with patch(MOCK_TARGET, side_effect=["Finding one.", _throttling_error()]):
        state = SharedState("Q?")
        state.set("subtasks", subtasks)

        with pytest.raises(ClientError):
            researcher.research(state)

        # Partial result is preserved in state.
        assert state.get("findings") == [{"subtask": "T1", "finding": "Finding one."}]


# ---------------------------------------------------------------------------
# 2. planner.plan returns unexpected format -> empty subtask list
#    BUG EXPOSED: run_pipeline passes the empty list straight to researcher
#    (which is a no-op) and then to writer, which calls invoke with an empty
#    context and returns a hollow answer. There is no guard or early exit.
# ---------------------------------------------------------------------------

def test_planner_unexpected_format_yields_empty_subtasks():
    """Blank / whitespace-only model output produces an empty subtask list."""
    with patch(MOCK_TARGET, return_value="   \n\n   "):
        state = SharedState("Q?")
        subtasks = planner.plan(state)

    assert subtasks == []


def test_pipeline_empty_subtasks_raises_not_hollow_answer():
    """
    BUG FIXED: empty subtask list now raises PipelineError via run_pipeline
    instead of silently producing a hollow answer.
    """
    with patch(MOCK_TARGET, return_value=""):
        with pytest.raises(PipelineError, match="no subtasks"):
            orchestrator.run_pipeline("Q?")


# ---------------------------------------------------------------------------
# 3. writer.write called with zero findings
#    BUG EXPOSED: writer still invokes the model and returns an answer even
#    when findings is empty, producing an ungrounded response.
# ---------------------------------------------------------------------------

def test_writer_zero_findings_still_invokes_model():
    """
    BUG EXPOSED: writer.write does not guard against empty findings.
    It calls invoke and returns a hollow answer instead of raising or
    returning a sentinel like None / "".
    """
    with patch(MOCK_TARGET, return_value="Hollow answer.") as mock_invoke:
        state = SharedState("Q?")
        state.set("findings", [])
        answer = writer.write(state)

    mock_invoke.assert_called_once()          # BUG: model is called with no context
    assert answer == "Hollow answer."         # hollow answer is silently returned


# ---------------------------------------------------------------------------
# 4. run_pipeline retry loop is a no-op
#    BUG EXPOSED: the `for _attempt in range(max_retries)` loop contains an
#    unconditional `return` on its first iteration, so max_retries is ignored
#    and the pipeline never actually retries on failure.
# ---------------------------------------------------------------------------

def test_run_pipeline_retries_on_throttle():
    """
    Pipeline.run retries on ThrottlingException and succeeds on the second
    attempt. sleep is patched so the test stays fast.
    """
    plan_raw = "1. T1"
    # First full attempt: plan raises; second attempt: plan+research+write+critique succeed.
    with patch(MOCK_TARGET, side_effect=[_throttling_error(), plan_raw, "F1", "Answer.", "STRONG"]):
        with patch("src.pipeline.time.sleep") as mock_sleep:
            result = Pipeline(max_retries=2, backoff_base=0.0).run("Q?")

    mock_sleep.assert_called_once()          # backoff fired exactly once
    assert result["answer"] == "Answer."


def test_run_pipeline_raises_after_all_retries_exhausted():
    """
    Pipeline.run re-raises the ClientError once max_retries is exhausted.
    """
    with patch(MOCK_TARGET, side_effect=_throttling_error()):
        with patch("src.pipeline.time.sleep"):
            with pytest.raises(ClientError):
                Pipeline(max_retries=2, backoff_base=0.0).run("Q?")


# ---------------------------------------------------------------------------
# 5. Lambda handler receives an event with no "question"
#    BUG EXPOSED: handler passes question=None straight into run_pipeline,
#    which passes it to planner.plan, which concatenates None into a string
#    prompt — a TypeError in Python 3 — instead of returning a 400 response.
# ---------------------------------------------------------------------------

def test_handler_missing_question_returns_400():
    """handler now validates the question field and returns 400."""
    event = {"body": json.dumps({})}
    response = orchestrator.handler(event, context=None)
    assert response["statusCode"] == 400
    assert "question is required" in json.loads(response["body"])["error"]


def test_handler_missing_body_returns_400():
    """handler treats a missing body the same as a missing question."""
    response = orchestrator.handler({}, context=None)
    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# Pipeline class — new tests
# ---------------------------------------------------------------------------

def test_pipeline_happy_path():
    plan_raw = "1. Sub-task one\n2. Sub-task two"
    with patch(MOCK_TARGET, side_effect=[plan_raw, "F1", "F2", "Answer.", "STRONG"]):
        result = Pipeline().run("Q?")

    assert result["subtasks"] == ["Sub-task one", "Sub-task two"]
    assert len(result["findings"]) == 2
    assert result["answer"] == "Answer."
    assert result["critique"] == "STRONG"


def test_pipeline_empty_subtasks_raises_pipeline_error():
    """Empty subtask list now raises PipelineError instead of hollow answer."""
    with patch(MOCK_TARGET, return_value=""):
        with pytest.raises(PipelineError, match="no subtasks"):
            Pipeline().run("Q?")


def test_pipeline_partial_findings_preserved_on_throttle():
    """
    _research_with_partial_results skips throttled subtasks and keeps
    findings from the ones that succeeded.
    """
    plan_raw = "1. T1\n2. T2\n3. T3"
    # T1 succeeds, T2 throttles (skipped), T3 succeeds; then write + critique
    invoke_seq = [plan_raw, "F1", _throttling_error(), "F3", "Answer.", "STRONG"]
    with patch(MOCK_TARGET, side_effect=invoke_seq):
        with patch("src.pipeline.time.sleep"):
            result = Pipeline().run("Q?")

    subtask_names = [f["subtask"] for f in result["findings"]]
    assert "T1" in subtask_names
    assert "T3" in subtask_names
    assert "T2" not in subtask_names
    assert result["answer"] == "Answer."


def test_pipeline_handler_returns_422_on_pipeline_error():
    """handler maps PipelineError to a 422 response."""
    with patch(MOCK_TARGET, return_value=""):   # empty plan -> PipelineError
        response = orchestrator.handler(
            {"body": json.dumps({"question": "Q?"})}, context=None
        )
    assert response["statusCode"] == 422
    assert "error" in json.loads(response["body"])


# ---------------------------------------------------------------------------
# critic.critique
# ---------------------------------------------------------------------------

def test_critic_strong_verdict_keeps_original_answer():
    """STRONG verdict: invoke called once, original answer unchanged."""
    with patch(MOCK_TARGET, return_value="STRONG") as mock_invoke:
        state = SharedState("Q?")
        state.set("findings", [{"subtask": "T1", "finding": "F1"}])
        state.set("answer", "Original answer.")
        result = critic.critique(state)

    assert result == "Original answer."
    assert state.get("answer") == "Original answer."
    assert state.get("critique") == "STRONG"
    mock_invoke.assert_called_once()   # only the scoring call


def test_critic_weak_verdict_triggers_revision():
    """WEAK verdict: critic calls writer.write once more and returns revised answer."""
    # First invoke = scoring (WEAK), second invoke = writer's revised answer
    with patch(MOCK_TARGET, side_effect=["WEAK - too vague", "Revised answer."]):
        state = SharedState("Q?")
        state.set("findings", [{"subtask": "T1", "finding": "F1"}])
        state.set("answer", "Vague answer.")
        result = critic.critique(state)

    assert result == "Revised answer."
    assert state.get("answer") == "Revised answer."
    assert state.get("critique").startswith("WEAK")


def test_critic_weak_case_insensitive():
    """'weak' in lowercase still triggers a revision."""
    with patch(MOCK_TARGET, side_effect=["weak", "Revised."]):
        state = SharedState("Q?")
        state.set("findings", [{"subtask": "T1", "finding": "F1"}])
        state.set("answer", "Bad answer.")
        result = critic.critique(state)

    assert result == "Revised."


def test_critic_stores_verdict_in_state():
    """critique key is always written to state regardless of verdict."""
    for verdict in ("STRONG", "WEAK"):
        side = [verdict] if verdict == "STRONG" else [verdict, "Rev."]
        with patch(MOCK_TARGET, side_effect=side):
            state = SharedState("Q?")
            state.set("findings", [{"subtask": "T", "finding": "F"}])
            state.set("answer", "A.")
            critic.critique(state)
        assert state.get("critique") == verdict


def test_critic_prompt_contains_answer():
    """The scoring prompt sent to invoke includes the current answer text."""
    captured = {}

    def capture(prompt, **kwargs):
        captured["prompt"] = prompt
        return "STRONG"

    with patch(MOCK_TARGET, side_effect=capture):
        state = SharedState("Q?")
        state.set("findings", [])
        state.set("answer", "My specific answer text.")
        critic.critique(state)

    assert "My specific answer text." in captured["prompt"]


def test_pipeline_result_includes_critique_key():
    """End-to-end: pipeline result always contains a 'critique' key."""
    with patch(MOCK_TARGET, side_effect=["1. T1", "F1", "Answer.", "STRONG"]):
        result = Pipeline().run("Q?")

    assert "critique" in result
    assert result["critique"] == "STRONG"


def test_pipeline_weak_answer_revised_end_to_end():
    """End-to-end: WEAK verdict causes pipeline to return the revised answer."""
    # plan, research, write(first), critique=WEAK, write(revision)
    with patch(MOCK_TARGET, side_effect=["1. T1", "F1", "Vague.", "WEAK", "Revised."]):
        result = Pipeline().run("Q?")

    assert result["answer"] == "Revised."
    assert result["critique"].startswith("WEAK")
