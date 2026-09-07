# Benchmarking Amazon Q Developer on a Multi-Agent App

A hands-on benchmark of **Amazon Q Developer** in VS Code, run against a
deliberately imperfect **multi-agent research assistant**. It evaluates
three workflows and records exactly where Q saves hours and where a human
still has to step in.

- **Test 1 — Unit test generation** (the agent pipeline in `src/`)
- **Test 2 — In-IDE security scanning** (over-privileged IAM in `infra/`)
- **Test 3 — Agentic multi-file refactoring** (untangle + extend the pipeline)

Full write-up: [`BLOG-DRAFT.md`](BLOG-DRAFT.md).
Complete session logs: [`evidence/`](evidence/).

Tested with Amazon Q Developer extension v2.7.0 (Language Server v1.78.0),
model set to Auto, on the free AWS Builder ID tier.

## The app under test

A mini agent pipeline: a **planner** breaks a question into sub-tasks, a
**researcher** answers each, a **writer** composes the final answer, and
(after the refactor) a **critic** reviews it. A **pipeline** module
sequences them; a thin Lambda **handler** is the entry point. This
multi-agent shape is richer material than a CRUD app — Q has to reason about
coordination, shared state, and failure paths.

## What Amazon Q actually did

Each test gave Q a task and observed the result. In short:

**Test 1 — Generate unit tests.** Asked to write `pytest` tests for the
pipeline (mocking Bedrock), Q read all the source, produced 6 clean
happy-path tests, and ran them (`6 passed`). On a second prompt asking for
failure-path tests, it added 8 more and correctly identified **5 real bugs**
in the code (lost findings on throttle, hollow answer on empty input, a
no-op retry loop, and a missing-input crash) — but only *after* being asked.

**Test 2 — Security scan.** Q flagged the wildcard IAM policy
(`actions=["*"], resources=["*"]`) as Critical, then **cross-read a second
file** to derive a precise least-privilege fix (`bedrock:InvokeModel` on one
model ARN) and caught a bonus config issue. Pushed further, it traced the
whole call graph and honestly **listed 5 things it could not verify** from
static code (env vars, deploy region, account-level model grants, network).

**Test 3a — Refactor the monolith.** Q split the god-object orchestrator
into a dedicated `pipeline.py`, kept a thin Lambda handler, added a
back-compat shim, **fixed all 5 bugs** from Test 1, and updated the suite —
`18 passed`.

**Test 3b — Coordinated cross-file change.** Asked to add a new `critic`
agent and wire it through the pipeline, state, IAM notes, and tests, Q
touched 5 files coherently and got `25 passed` — but **introduced a subtle
shared-state bug that its own passing tests missed**. That's the headline
finding: it optimizes for green tests, not held invariants.

Full prompts are in [`PROMPTS.md`](PROMPTS.md); the complete responses are in
[`evidence/`](evidence/) and [`BLOG-DRAFT.md`](BLOG-DRAFT.md).

## No AWS deployment required ($0)

Everything runs **locally in VS Code on the code itself**. You do NOT deploy
anything and do NOT need a provisioned AWS account. Bedrock is only
*referenced* in code so Q has something to mock — the tests fake
`bedrock_client.invoke`, so no real AWS calls happen. The only thing that
must be free is **Amazon Q Developer**, which it is on the Builder ID tier.

## Results at a glance

| Workflow | What worked | The limitation |
|---|---|---|
| Unit tests | fast, correct happy-path mocks for the whole pipeline | tested only happy paths until explicitly asked; surfaced the 5 real bugs only on the follow-up prompt |
| Security scan | flagged the wildcard IAM, cross-read a second file for a least-privilege fix, listed 5 gaps it couldn't see | bounded by static code — can't see env vars, region, account grants, or network posture |
| Refactor (3a) | clean module extraction, back-compat shim, fixed all 5 bugs, 18/18 tests green | — (this is its strength) |
| Cross-file change (3b) | coherent 5-file change, full call-path trace, 25/25 green | introduced a subtle shared-state bug its own passing tests missed |

**Takeaway:** Q is excellent at the boilerplate ~80% (happy-path tests,
obvious security findings, contained refactors). Its failure mode isn't
sloppiness — it optimizes for "tests green," not "adversarial cases covered"
or "state invariants held." A human still owns that last 20%.

## Evidence

Every claim in this benchmark is backed by the actual Amazon Q session, not
paraphrased. The [`evidence/`](evidence/) folder contains the complete
transcript in two forms plus the script that converts between them:

| File | What it is |
|---|---|
| [`evidence/amazon-q-chat-history-raw.json`](evidence/amazon-q-chat-history-raw.json) | The raw, unedited chat-history file exported by the Amazon Q VS Code extension. Byte-for-byte proof — contains every prompt, response, tool call, and the pytest outputs. |
| [`evidence/amazon-q-full-transcript.md`](evidence/amazon-q-full-transcript.md) | A human-readable Markdown rendering of the same session (prompts + responses in order). This is the one to actually read. |
| [`evidence/extract_transcript.py`](evidence/extract_transcript.py) | Small script that turns the raw JSON into the readable Markdown, so anyone can verify the transcript was not edited. |

**Where the raw log comes from.** The Amazon Q extension stores chat history
locally at:

```
<user home>/.aws/amazonq/history/chat-history-*.json
```

(on Windows, `C:\Users\<you>\.aws\amazonq\history\`). The file in this repo
is a direct copy of that session file.

**Regenerate the readable transcript yourself:**

```
python evidence/extract_transcript.py
```

This reads `amazon-q-chat-history-raw.json` and rewrites
`amazon-q-full-transcript.md` — run it against the raw file and you'll get
the exact transcript quoted in the blog, confirming nothing was doctored.

The code blocks embedded in [`BLOG-DRAFT.md`](BLOG-DRAFT.md) (test output,
scan findings, refactor diffs) are all drawn from this same session.

## Structure

```
.
├── src/
│   ├── orchestrator.py      # thin Lambda entry point (after refactor)
│   ├── pipeline.py          # pipeline sequencing + real retry/backoff (added by Q)
│   ├── state.py             # shared state passed between agents
│   ├── bedrock_client.py    # invoke() wrapper (mocked in tests)
│   └── agents/
│       ├── planner.py       # question -> sub-tasks
│       ├── researcher.py    # sub-task -> finding
│       ├── writer.py        # findings -> final answer
│       └── critic.py        # reviews the answer, may request a revision (added by Q)
├── infra/agent_stack.py     # CDK stack with wildcard IAM (security-scan target)
├── tests/test_pipeline.py   # 25 tests (generated + extended by Q)
├── evidence/                # real Amazon Q session logs (raw + readable)
│   ├── amazon-q-chat-history-raw.json
│   ├── amazon-q-full-transcript.md
│   └── extract_transcript.py
├── PROMPTS.md               # the exact copy-paste prompts used, per test case
├── PLAN.md                  # benchmark blueprint + hypotheses
├── EXECUTION-CHECKLIST.md   # step-by-step run plan
├── BLOG-DRAFT.md            # full write-up with embedded logs
└── requirements.txt
```

## Reproduce it

1. Install the **Amazon Q Developer** extension in VS Code; sign in with a
   free **AWS Builder ID**.
2. Open this folder in VS Code.
3. (Optional, to run the tests) `pip install -r requirements.txt`, then
   `python -m pytest -q`.
4. Paste the prompts from [`PROMPTS.md`](PROMPTS.md) into the Amazon Q chat,
   in order, and compare Q's output against the logs in [`evidence/`](evidence/).

> Note: the code in `src/` is the **post-benchmark** state (Q's refactor and
> critic agent already applied). To reproduce Test 3 from scratch, revert
> `src/` to the pre-refactor monolith first — the original seeded flaws are
> described in `PLAN.md` and visible in the early part of the transcript.

## Seeded issues the benchmark targeted

The original code was intentionally flawed so each workflow had real
material: no error handling, fragile line-based parsing, no partial results
on failure, hollow output on empty findings, a no-op retry loop, mixed
concerns in the orchestrator, and a wildcard `actions=["*"], resources=["*"]`
IAM policy. Test 3a fixed most of these; see the transcript for the diffs.
