# Copy-Paste Prompts for Amazon Q Developer

Paste these into the Amazon Q chat panel in VS Code. Have the relevant
file(s) open / in context first. Two prompts per test case: one to show
what works, one engineered to surface the limitation.

> Command names (`/test`, `/dev`, scan entry point) differ by version and
> are consolidating into a single agentic chat. If a slash command isn't
> recognized, just describe the task in plain language — the agent handles
> it. Screenshot whatever your version actually shows.

> The app never calls real AWS. Tests must mock `src.bedrock_client.invoke`.

---

## Test Case 1 — Unit tests & mocks (multi-agent pipeline)

### 1a. What works (happy path)
```
Generate pytest unit tests for the multi-agent pipeline in src/.
Mock src.bedrock_client.invoke so no real AWS/Bedrock calls happen.
Cover the happy paths for:
- planner.plan (question -> list of subtasks)
- researcher.research (subtasks -> findings)
- writer.write (findings -> final answer)
- orchestrator.run_pipeline (end to end with mocked invoke)
Write them into tests/test_pipeline.py.
```

### 1b. Surface the limitation (failure paths across agents)
```
Now add negative/failure-path tests for the pipeline:
1. bedrock_client.invoke raises a botocore ThrottlingException mid-way
   through researcher.research - assert prior findings are not lost.
2. planner.plan receives model output in an unexpected format and yields
   an empty subtask list - assert the pipeline handles it, not a hollow answer.
3. writer.write is called with zero findings.
4. run_pipeline's retry loop - prove whether it actually retries on failure.
5. the Lambda handler receives an event with no "question".
Point out any real bugs these tests expose in the current code.
```
> Watch for: does Q notice the researcher loses all findings on one
> failure, and that run_pipeline's retry loop is a no-op? These are the
> "adversarial thinking" gaps.

---

## Test Case 2 — Security scan

### 2a. What works
```
Run a security scan on this project. Focus on infra/agent_stack.py and
flag any over-privileged IAM. Explain the risk of the current policy and
suggest a least-privilege replacement scoped to only the Bedrock
InvokeModel action on the specific model ARN the agents use.
```
> Screenshot the finding for `actions=["*"], resources=["*"]` and the
> suggested/one-click remediation.

### 2b. Surface the limitation (cross-file context)
```
Beyond the wildcard policy, trace how the orchestrator's IAM role relates
to the Bedrock calls made inside src/agents/*.py and src/bedrock_client.py.
Which exact permissions do the agents actually require, and what context
across these files can't you fully assess from the CDK stack alone? Be
explicit about what you're missing.
```
> Watch for: strong local reasoning, but an honest admission about
> whole-app / cross-file context. That admission IS your finding.

---

## Test Case 3 — Agentic multi-file refactor

### 3a. What works
```
Refactor src/orchestrator.py without changing behavior. Separate concerns:
- keep the Lambda handler thin (HTTP parse only)
- move pipeline sequencing into a dedicated Pipeline class/module
- add real error handling so one failing agent doesn't crash everything
- make the retry loop actually retry with backoff
- give each agent a clear input/output instead of mutating shared state
Show me the full multi-file diff before applying, and update the tests.
```
> Screenshot the proposed diff / new files. Accept, then run `pytest`.

### 3b. Surface the limitation (deep / cross-cutting change)
```
Now add a new "critic" agent at src/agents/critic.py that reviews the
writer's answer and requests one revision if it's weak. Wire it into the
orchestrator's pipeline AFTER the writer, thread it through the shared
state, update the IAM notes in infra/agent_stack.py, and update all tests.
Trace the full call path from the Lambda entry point through every agent.
```
> Watch for: as the change spans many files at once, does Q keep every
> reference consistent, miss a wiring point, or lose track across the
> agent modules? That's the indexing/context-boundary limitation.
