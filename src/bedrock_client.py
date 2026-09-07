"""
Thin wrapper around Bedrock's invoke_model.

Referenced by all three agents. In tests you mock `invoke` so nothing
ever calls real AWS (keeps the whole project $0 and offline).
"""

import json
import os

import boto3

MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

# Created at module scope. NOTE (seeded smell): no region/config handling,
# no retry/backoff, no timeout.
_client = boto3.client("bedrock-runtime")


def invoke(prompt: str, max_tokens: int = 500) -> str:
    """Send a single-turn prompt to Bedrock and return the text.

    Seeded flaw: no error handling. A ThrottlingException or a malformed
    response payload will crash the caller instead of degrading gracefully.
    """
    resp = _client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    payload = json.loads(resp["body"].read())
    return payload["content"][0]["text"]
