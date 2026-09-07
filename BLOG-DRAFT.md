# Benchmarking Amazon Q Developer in VS Code: Automated Unit Testing, Security Scans, and Multi-File Refactoring Limits

*How AWS's agentic coding assistant does on a real multi-agent AI app — and where a human still has to step in. All on the $0 AWS Builder ID free tier, no AWS deployment.*

> Replace every `[SCREENSHOT xx]` marker with your captured image. Replace
> every `> OBSERVATION:` block with what you actually saw. Keep the verdict
> honest — that balance is what makes the post credible.

---

## Why benchmark, not just demo

Plenty of posts show Amazon Q Developer autocompleting a function. Fewer
ask the harder question: on realistic AI-engineering work, *where does it
save you hours, and where does it quietly need a human?* This post runs
three workflows against a deliberately-imperfect **multi-agent research
assistant** and gives each a straight verdict.

I chose a multi-agent app on purpose. A planner/researcher/writer pipeline
forces Q to reason about coordination, shared state, and failure paths —
a much richer surface than a plain CRUD handler.

**Thesis:** Q reliably erases the boilerplate ~80% of test, security, and
refactor work. Its value drops at the edges — adversarial test cases,
cross-file reasoning, and coordinated multi-file change — which is exactly
where an AI engineer still earns their seat.

The sample repo is public: **[GITHUB LINK]**

---

## Setup: $0 in about 30 minutes (no deployment)

- Install the **Amazon Q Developer** extension in VS Code.
- Sign in with a free **AWS Builder ID** — no AWS account or card required.
- Open the sample project and go.

Everything runs on the code itself. The generated tests mock the Bedrock
client, so nothing calls real AWS — no DynamoDB, no provisioned account,
nothing to deploy.

`[SCREENSHOT 01 — Builder ID connected]`

*(Tested on Amazon Q Developer extension v[VERSION]. Note: AWS has
announced it will discontinue the Amazon Q Developer IDE plugins on
April 30, 2027 — verify current status on the official page; everything
here works today.)*

The test subject: a multi-agent pipeline — a **planner** splits a question
into sub-tasks, a **researcher** answers each, a **writer** composes the
final answer, and a monolithic **orchestrator** wires them together over
shared state, plus a CDK stack carrying one glaring wildcard IAM policy.

---

## Test Case 1 — Automated unit tests & mocks

**The experiment:** point Q at `src/` and ask for `pytest` tests that mock
`bedrock_client.invoke`, covering each agent and the end-to-end pipeline.

*(Environment: Amazon Q Developer extension v2.7.0, Language Server v1.78.0,
model set to Auto. All logs below are the real Amazon Q session transcript,
not reconstructed.)*

### Step 1 — The happy-path prompt

I gave Amazon Q this prompt:

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

Q read all seven source files, generated six tests that patch
`src.bedrock_client.invoke`, installed pytest, and ran them:

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 6 items

tests/test_pipeline.py::test_planner_returns_subtasks PASSED             [ 16%]
tests/test_pipeline.py::test_researcher_returns_findings PASSED          [ 33%]
tests/test_pipeline.py::test_writer_returns_answer PASSED                [ 50%]
tests/test_pipeline.py::test_writer_prompt_includes_question_and_findings PASSED [ 66%]
tests/test_pipeline.py::test_run_pipeline_happy_path PASSED              [ 83%]
tests/test_pipeline.py::test_run_pipeline_result_keys PASSED             [100%]

============================== 6 passed in 0.97s ==============================
```

**What worked:** it scaffolded the happy-path tests, mocked the Bedrock
boundary correctly (zero real AWS calls), and covered planner, researcher,
writer, and `run_pipeline` in seconds. On its own, though, it tested only
the paths where everything goes right — no failure handling at all.

### Step 2 — Forcing the failure paths

So I pushed it with a second prompt:

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

Now it wrote eight more tests and ran the full suite:

```
============================= test session starts =============================
collected 14 items

tests/test_pipeline.py::test_planner_returns_subtasks PASSED             [  7%]
tests/test_pipeline.py::test_researcher_returns_findings PASSED          [ 14%]
tests/test_pipeline.py::test_writer_returns_answer PASSED                [ 21%]
tests/test_pipeline.py::test_writer_prompt_includes_question_and_findings PASSED [ 28%]
tests/test_pipeline.py::test_run_pipeline_happy_path PASSED              [ 35%]
tests/test_pipeline.py::test_run_pipeline_result_keys PASSED             [ 42%]
tests/test_pipeline.py::test_researcher_throttle_loses_prior_findings PASSED [ 50%]
tests/test_pipeline.py::test_planner_unexpected_format_yields_empty_subtasks PASSED [ 57%]
tests/test_pipeline.py::test_pipeline_empty_subtasks_still_calls_writer PASSED [ 64%]
tests/test_pipeline.py::test_writer_zero_findings_still_invokes_model PASSED [ 71%]
tests/test_pipeline.py::test_run_pipeline_does_not_retry_on_failure PASSED [ 78%]
tests/test_pipeline.py::test_run_pipeline_retry_loop_is_noop_on_success PASSED [ 85%]
tests/test_pipeline.py::test_handler_missing_question_crashes_instead_of_400 PASSED [ 92%]
tests/test_pipeline.py::test_handler_missing_body_crashes_instead_of_400 PASSED [100%]

============================= 14 passed in 0.59s ==============================
```

And this time it identified five real bugs in the code:

```
Bug 1 - Researcher loses partial findings on throttle:
  research() only saves findings after the loop, so a ThrottlingException
  on sub-task 2 discards sub-task 1's result.

Bug 2 - Empty subtask list flows silently into the writer:
  planner.plan returns [] on odd output; the orchestrator has no guard,
  so the writer still produces an ungrounded "hollow" answer.

Bug 3 - Writer invokes the model with empty context:
  no early return when findings == [].

Bug 4 - Retry loop is a no-op:
  the `for _attempt in range(max_retries)` loop has an unconditional
  return, so max_retries never takes effect (invoke.call_count == 1).

Bug 5 - Lambda handler crashes on missing "question":
  no validation; None flows into planner.plan and raises a TypeError
  instead of returning a clean 400.
```

**The limitation:** Q found all five bugs — but only after I explicitly
asked for failure paths. Its first pass tested only the happy paths. The
adversarial thinking was on me.

**Verdict:** excellent test *scaffolder*, weak *adversarial thinker*. Great
at the routine 80%, needs a human to drive the edge-case 20%.

---

## Test Case 2 — In-IDE security scan vs. over-privileged IAM

**The experiment:** run Q's security scan on the CDK stack whose orchestrator
role uses `actions=["*"], resources=["*"]`.

**The prompt:**

```
Run a security scan on this project. Focus on infra/agent_stack.py and
flag any over-privileged IAM. Explain the risk of the current policy and
suggest a least-privilege replacement scoped to only the Bedrock
InvokeModel action on the specific model ARN the agents use.
```

Q read `infra/agent_stack.py` and `src/bedrock_client.py`, then logged two
findings to the Code Issues panel. Here is its actual report:

```
CRITICAL — Wildcard IAM policy grants full AWS access to Lambda role
infra/agent_stack.py, lines 41-45

  PolicyStatement uses actions=["*"] and resources=["*"], giving the
  OrchestratorFn Lambda role unrestricted access to every AWS service and
  resource in the account. If the function is compromised (e.g. via prompt
  injection through the Bedrock model output, or a dependency
  vulnerability), an attacker gains full account-takeover capability:
  read/delete S3 buckets, exfiltrate Secrets Manager values, create IAM
  users, pivot to other services. The agents only ever call
  bedrock:InvokeModel on a single model ARN.

  Suggested fix:
    fn.add_to_role_policy(
        iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model"
                "/anthropic.claude-3-sonnet-20240229-v1:0"
            ],
        )
    )

LOW — boto3 client created at module scope with no region or config
src/bedrock_client.py, line 16

  boto3.client("bedrock-runtime") is built at import time with no
  region_name or Config. In Lambda the region is inferred implicitly;
  outside Lambda it can target the wrong region or raise NoRegionError.

  Suggested fix: pass region_name=os.environ.get("AWS_REGION") and a
  botocore Config(retries={"max_attempts": 3, "mode": "adaptive"}).
```

**What worked — and it went further than expected.** Q didn't just flag the
wildcard policy. To build the least-privilege replacement it *cross-read*
`bedrock_client.py`, found that the only API ever called is
`bedrock:InvokeModel` on exactly one model ID, and scoped the fix to that
single action on that single ARN — resolving the region from the stack
context instead of hardcoding it. It also framed the real risk in
AI-specific terms (prompt injection through model output as an
account-takeover path), and caught a second, unrelated config smell I
hadn't asked about.

### Pushing on cross-file context

To probe the limit I followed up:

```
Beyond the wildcard policy, trace how the orchestrator's IAM role relates
to the Bedrock calls made inside src/agents/*.py and src/bedrock_client.py.
Which exact permissions do the agents actually require, and what context
across these files can't you fully assess from the CDK stack alone? Be
explicit about what you're missing.
```

This is where I expected Q to thin out. It didn't. It read all five files
and traced the entire call chain:

```
handler()                          orchestrator.py
  └── run_pipeline()
        ├── planner.plan()         -> bedrock_client.invoke() -> invoke_model
        ├── researcher.research()  -> bedrock_client.invoke() xN -> invoke_model
        └── writer.write()         -> bedrock_client.invoke() -> invoke_model

Exactly one boto3 call exists in the whole codebase: bedrock:InvokeModel.
No agent makes any other AWS API call directly.
```

**What genuinely impressed me:** rather than stop at "looks fine," Q listed
five things it *cannot* verify from the code alone — and every one is a real
gap:

```
1. MODEL_ID is a runtime env var, not a deploy-time constant. The code and
   the policy agree today, but the env var can be overridden without
   touching the CDK stack, silently breaking the scoped IAM policy.

2. The boto3 client has no explicit region. If deployed to a region where
   Claude 3 Sonnet isn't available, calls fail with AccessDeniedException
   that looks like an IAM problem but isn't.

3. No VPC / condition keys. Exfiltrated role credentials could call
   InvokeModel from anywhere on the internet; a VPC-endpoint condition
   would close that, but there's no VPC here to assess.

4. bedrock:InvokeModel also needs an account-level Bedrock model-access
   grant, which lives outside the codebase entirely and can't be verified
   from CDK.

5. No logging/tracing configured, so the blast radius of a prompt injection
   can't be audited from the stack alone.
```

**The real limitation (and it's a subtle one):** *within the repository*,
Q's cross-file reasoning was excellent — it proved there's a single AWS
call and derived a one-action, one-resource policy correctly. What it
cannot see is everything *outside* the code: runtime environment variables,
the deploy region, account-level Bedrock grants, and network posture. So
the honest finding isn't "Q reasons only locally" — it's that a static
in-IDE scan is bounded by the code it can read, and a real threat model
still has to account for the account and runtime context the code doesn't
capture.

**Verdict:** a genuinely strong security reviewer across the codebase —
better at cross-file tracing than I expected — but bounded by what static
code can reveal. It even enumerated its own blind spots, which is the most
useful thing a scan can do. A human still owns the account- and
runtime-level threat model.

---

## Test Case 3 — Agentic multi-file refactor

**The experiment:** ask the agent to untangle the monolithic
`orchestrator.py` — thin the Lambda handler, extract a Pipeline module, add
real error handling, make the retries real, and fix the seeded bugs.

**The prompt:**

```
Refactor src/orchestrator.py without changing behavior. Separate concerns:
- keep the Lambda handler thin (HTTP parse only)
- move pipeline sequencing into a dedicated Pipeline class/module
- add real error handling so one failing agent doesn't crash everything
- make the retry loop actually retry with backoff
- give each agent a clear input/output instead of mutating shared state
Show me the full multi-file diff before applying, and update the tests.
```

**What worked — and it was genuinely clean.** Q created a new
`src/pipeline.py`, reduced `orchestrator.py` to a 28-line HTTP handler, and
kept a one-line `run_pipeline` shim so existing callers and tests didn't
break. It didn't just move code around — it fixed the seeded bugs and
updated the test suite to match. Its own summary:

```
New file src/pipeline.py:
  - run() retry loop now only continues on retryable ClientError codes
    (ThrottlingException, ServiceUnavailableException, ModelTimeoutException),
    with exponential backoff (0.5s, 1s). Non-retryable errors re-raise.
  - _execute() raises PipelineError on empty subtasks / empty findings
    instead of silently producing a hollow answer.
  - _research_with_partial_results() runs subtasks one at a time; a throttle
    skips that subtask but preserves prior findings.

orchestrator.py:
  - down to 28 lines: parse body, validate question, delegate to Pipeline.
  - run_pipeline kept as a shim so existing tests need no changes.

researcher.py:
  - one-line fix: state.set("findings", findings) moved inside the loop.

tests/test_pipeline.py:
  - test_researcher_throttle_loses_prior_findings -> renamed
    ..._preserves_prior_findings, assertion flipped to the partial result.
  - test_pipeline_empty_subtasks_still_calls_writer -> renamed
    ..._raises_not_hollow_answer, now asserts PipelineError.
  - handler missing question/body -> now assert statusCode == 400.
  - four new Pipeline tests: happy path, retry with mocked sleep,
    partial findings on throttle, 422 from handler on PipelineError.
```

Re-running the suite after the refactor:

```
..................                                                       [100%]
18 passed in 0.63s
```

Every one of the five bugs from Test Case 1 is now fixed, the tests that
*documented* the bugs were rewritten to assert correct behavior, and four
new tests were added — all green. On a contained, single-repo change like
this, Q behaved less like an autocomplete and more like a careful engineer:
it preserved backward compatibility, explained each decision, and left the
suite passing.

### The coordinated cross-file change (3b)

Then the hard one — a single change that has to stay consistent across many
files at once:

```
Now add a new "critic" agent at src/agents/critic.py that reviews the
writer's answer and requests one revision if it's weak. Wire it into the
orchestrator's pipeline AFTER the writer, thread it through the shared
state, update the IAM notes in infra/agent_stack.py, and update all tests.
Trace the full call path from the Lambda entry point through every agent.
```

Q touched five files coherently: created `agents/critic.py`, added a
`critique` slot to `state.py`, imported and called the critic in
`pipeline.py`, updated the IAM comment, and revised the tests. It also
traced the whole call path and made sensible choices (a `startswith("WEAK")`
check to tolerate messy model output; reusing `writer.write` for the
revision so it stays grounded in the same findings). The suite grew from
18 to 25 tests:

```
.........................                                                [100%]
25 passed in 0.56s
```

On the surface: a clean, consistent, multi-file agentic change. Green tests,
correct output, good explanation.

**The limitation — and this is the real find.** Reviewing the generated
`pipeline.py` by hand, I found a bug Q introduced *and* its own 25 tests
missed. To reuse the existing `researcher.research` (which reads
`state["subtasks"]`), the new per-item loop does this:

```python
def _research_with_partial_results(self, state, subtasks):
    findings = []
    for subtask in subtasks:
        state.set("subtasks", [subtask])   # <-- clobbers shared state each pass
        partial = researcher.research(state)
        findings.extend(partial)
    state.set("findings", findings)
    return findings
```

After the loop, `state["subtasks"]` no longer holds the full list — it holds
only the **last** subtask. The pipeline happens to return the correct
*local* `subtasks` variable, so the output looks right and every test
passes. But the shared state is now internally inconsistent: any agent that
later reads `state["subtasks"]` (a future critic revision, a logging step, a
sixth agent) would silently see one item instead of all of them.

That is precisely the shared-mutable-state trap the original monolith was
built around — and while wiring in a new agent across files, Q quietly
reintroduced a version of it, then wrote tests that assert the *output*
rather than the *state invariants*, so nothing flagged it.

**Verdict:** on a contained refactor (3a) Q is a genuine force-multiplier.
On a coordinated cross-file change (3b) it produces correct-looking,
passing code — but the subtle state-consistency bug it introduced, and the
tests that missed it, are the whole point: an agent optimizes for "tests
green," not "invariants held." A human reviewer still has to read the diff
for the bug the tests don't catch.

---

## Scorecard

| Workflow | What worked | Where it broke | Human still needed for |
|---|---|---|---|
| Unit tests | fast, correct happy-path mocks for the whole pipeline | tested only happy paths until explicitly asked; found the 5 real bugs only on the follow-up prompt | driving the adversarial / failure-path thinking |
| Security scan | flagged the wildcard IAM, cross-read a second file to derive a one-action least-privilege fix, enumerated 5 gaps it couldn't see | nothing wrong — but bounded by static code (can't see env vars, region, account grants, network) | account- and runtime-level threat modeling |
| Refactor (3a) | clean module extraction, kept a back-compat shim, fixed all 5 bugs, updated tests, 18/18 green | — | almost nothing; this is its strength |
| Cross-file change (3b) | coherent 5-file change, full call-path trace, sensible design, 25/25 green | introduced a subtle shared-state clobber bug that its own tests missed | reading the diff for the bug the green tests hide |

---

## Takeaway for AI engineers

The pattern across all four runs is consistent, and more nuanced than "AI
good" or "AI bad":

- **On contained, well-specified work, Amazon Q is excellent** — the
  refactor (3a) was better than a lot of human first drafts: it fixed bugs,
  kept backward compatibility, and left the suite green.
- **On reasoning it can ground in the code, it exceeded expectations** — the
  security scan traced across files and even listed its own blind spots.
- **The failure mode isn't sloppiness, it's optimization target.** In both
  the unit-test run and the cross-file change, Q optimized for "tests pass"
  and "output looks right" — not for "adversarial cases covered" or "state
  invariants held." That's why it needed a nudge to test failure paths, and
  why it shipped a passing-but-subtly-broken cross-file change.

So the division of labor is clear: let Q delete the boilerplate 80% — the
happy-path tests, the obvious security findings, the mechanical refactors.
Keep a human on the 20% that an "is it green?" agent structurally can't own:
the adversarial test design, the account- and runtime-level threat model,
and reading the multi-file diff for the bug the tests don't catch.

Reproduce it yourself: **[GITHUB LINK]** — the repo includes every prompt,
so you can run the same benchmark on your version of Amazon Q.

---

*Tags: AWS, Amazon Q, AI, Multi-Agent, Developer Tools*
