"""
Orchestrator: Lambda entry point only.

Pipeline sequencing has moved to src/pipeline.py.
This file is now responsible solely for HTTP parsing and response shaping.
"""

import json

from src.pipeline import Pipeline, PipelineError

_pipeline = Pipeline()


def run_pipeline(question: str, max_retries: int = 2) -> dict:
    """Shim kept so existing callers and tests require no changes."""
    return Pipeline(max_retries=max_retries).run(question)


def handler(event, context):
    """Lambda entry point: parse HTTP, delegate to Pipeline, shape response."""
    body = json.loads(event.get("body") or "{}")
    question = body.get("question")

    if not question:
        return {"statusCode": 400, "body": json.dumps({"error": "question is required"})}

    try:
        result = _pipeline.run(question)
        return {"statusCode": 200, "body": json.dumps(result)}
    except PipelineError as exc:
        return {"statusCode": 422, "body": json.dumps({"error": str(exc)})}
