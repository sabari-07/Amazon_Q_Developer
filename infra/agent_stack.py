"""
CDK stack for the multi-agent research assistant.

Intentionally contains an OVER-PRIVILEGED IAM policy (Action: "*",
Resource: "*") so Amazon Q Developer's security scan has an obvious
finding to flag and offer a remediation for.

This is the "before" state you screenshot for the security-scan test.
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
)
from constructs import Construct


class AgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = _lambda.Function(
            self,
            "OrchestratorFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="orchestrator.handler",
            code=_lambda.Code.from_asset("src"),
            timeout=Duration.seconds(60),
            environment={
                "MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
            },
        )

        # ---- SECURITY SMELL (intentional) ----
        # Wildcard action + wildcard resource. All four agents (planner,
        # researcher, writer, critic) funnel through bedrock_client.invoke
        # and collectively need only one permission:
        #   bedrock:InvokeModel on the specific model ARN below.
        # The critic adds no new IAM requirements — it calls the same
        # invoke() wrapper as every other agent.
        #
        # Least-privilege replacement (see security scan findings):
        #   actions=["bedrock:InvokeModel"]
        #   resources=[f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model"
        #              "/anthropic.claude-3-sonnet-20240229-v1:0"]
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["*"],
                resources=["*"],
            )
        )
