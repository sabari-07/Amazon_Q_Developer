# Blog Blueprint — Benchmarking Amazon Q Developer in VS Code

**Working title:** *Benchmarking Amazon Q Developer in VS Code: Automated Unit Testing, Security Scans, and Multi-File Refactoring Limits (on a Multi-Agent App)*

**Track:** AWS Community Builders — AI Engineering
**Cost:** $0 (AWS Builder ID free tier, VS Code, no AWS deployment)
**Format:** Medium post + public GitHub repo + real screenshots

---

## The angle (why this post earns attention)

Most Q Developer posts are "look, it autocompletes." This one is a
**benchmark with a verdict**: three realistic workflows run against a
**multi-agent AI app** (a planner/researcher/writer pipeline), and for each
an honest "what worked / where it broke / when to reach for a human." Using
a multi-agent codebase — not a plain CRUD app — makes the AI-track story
stronger: Q has to reason about agent coordination, shared state, and
failure paths, which stresses its limits in a more interesting way.

**One-line thesis:** Amazon Q Developer reliably compresses the boilerplate
~80% of test/security/refactor work, but its value drops at the edges —
adversarial test cases, cross-file reasoning, and coordinated multi-file
change — which is exactly where an AI engineer still earns their seat.

---

## The test subject

A local **multi-agent research assistant** (no AWS deployment, Bedrock only
referenced/mocked):
- `planner.py` — turns a question into sub-tasks
- `researcher.py` — produces a finding per sub-task
- `writer.py` — composes the final answer
- `orchestrator.py` — coordinates the three over shared state (monolithic on purpose)

Seeded flaws give each test real material: no error handling, fragile
parsing, no partial results on failure, a fake (no-op) retry loop, mixed
concerns in the orchestrator, and a wildcard IAM policy in the CDK stack.

---

## Framing / facts to get right

- Amazon Q Developer is AWS's agentic AI assistant for the IDE (successor
  branding to CodeWhisperer). Free tier via AWS Builder ID.
- **$0 / no deploy:** every test runs on the code text inside VS Code.
  Generated tests mock `bedrock_client.invoke`, so no real AWS calls. No
  DynamoDB, no provisioned account, nothing to deploy.
- **Accuracy note to include:** AWS has publicly announced it will
  discontinue Amazon Q Developer **IDE plugins on April 30, 2027**. Mention
  as a "state of the tooling" aside; verify the exact wording on the
  official Q Developer page before publishing.
- **Command names change.** `/test`, `/dev`, and the security-scan entry
  point have been renamed across versions and are folding into a unified
  agentic chat. Don't hard-code command syntax from memory — screenshot
  what your installed version shows and describe by function too.

---

## Section-by-section content

### 1. Introduction & $0 setup
- What Q Developer is, one paragraph, no fluff.
- The evaluation goal: 3 workflows — unit tests, security scan, agentic refactor.
- Why a multi-agent app: richer coordination/state/failure surface to test.
- Setup: VS Code + Amazon Q extension + Builder ID. Emphasize $0, no deploy.
- **Hypothesis up front:** Q saves the most time on boilerplate and loses
  ground as required context widens across agents/files.

### 2. Test Case 1 — Automated unit test & mock generation
- **Setup:** the agent pipeline in `src/`; tests must mock `bedrock_client.invoke`.
- **Prove it works:** Q generates pytest happy-path tests for planner,
  researcher, writer, and end-to-end `run_pipeline`, quickly and correctly.
- **Prove the limit:** without a nudge it skips failure paths — a
  `ThrottlingException` mid-research (which loses all findings), an empty
  sub-task list from the planner, a zero-findings writer call, and the fact
  that `run_pipeline`'s retry loop never retries. Note whether Q's tests
  expose these real bugs.
- **Verdict line:** great test scaffolder, weak adversarial thinker.

### 3. Test Case 2 — In-IDE security scan vs. over-privileged IAM
- **Setup:** `infra/agent_stack.py` has `actions=["*"], resources=["*"]`.
- **Prove it works:** scan flags the wildcard IAM, offers a scoped
  remediation (only `bedrock:InvokeModel` on the model ARN the agents use).
- **Prove the limit:** it reasons on local/immediate references; tracing the
  actual permissions the agents need across `agents/*.py` + `bedrock_client.py`
  is where whole-app context thins out.
- **Verdict line:** excellent first-pass gate, not a threat model.

### 4. Test Case 3 — Agentic multi-file refactor
- **Setup:** ask the agent to untangle `orchestrator.py` — thin the Lambda
  handler, extract a Pipeline module, add real error handling, make retries
  real, and give each agent clear inputs/outputs instead of shared mutable state.
- **Prove it works:** on this contained repo it produces a clean multi-file
  diff; tests stay green after applying.
- **Prove the limit:** then ask for a coordinated, cross-cutting change — add
  a new `critic` agent, wire it into the pipeline after the writer, thread it
  through state, update IAM notes, update all tests. As the change spans many
  files at once, watch for lost references or missed wiring.
- **Verdict line:** force-multiplier on contained scopes; supervise across boundaries.

### 5. Results table + conclusion
- The scorecard (below).
- Takeaway: use Q to delete boilerplate, keep humans on the adversarial +
  architectural edges — especially in multi-agent coordination.
- CTA: link the repo, invite readers to reproduce.

---

## Scorecard (fill with your real observations)

| Workflow | What worked | Where it broke | Human still needed for |
|---|---|---|---|
| Unit tests | happy-path mocks for the agent pipeline | throttling mid-research, empty subtasks, no-op retry loop | adversarial / failure-path cases |
| Security scan | flagged wildcard IAM + suggested fix | permissions the agents actually need across files | threat modeling |
| Agentic refactor | clean orchestrator split | coordinated multi-file change (new critic agent wiring) | large-scale agent architecture |

---

## Success criteria for the post
- [ ] Every "what works" and "limitation" is backed by a real screenshot.
- [ ] Repo is public and linked.
- [ ] Command names match what your installed version shows (not memory).
- [ ] The 2027 plugin EOL note is included and verified.
- [ ] The "$0, no deploy, Bedrock mocked" point is clear to readers.
- [ ] Verdict is balanced — credible, not a hit piece and not an ad.
