# Execution Checklist — This Week

A day-by-day plan to go from zero to a published Medium post. Budget:
~4–6 focused hours total. Cost: $0, no AWS deployment.

---

## Day 1 — Setup (30–45 min)

- [ ] Install the **Amazon Q Developer** extension in VS Code
      (Extensions marketplace → search "Amazon Q").
- [ ] Sign in with a free **AWS Builder ID** (no AWS account/credit card needed).
- [ ] Confirm the Q panel opens and chat responds to a trivial prompt.
- [ ] **Screenshot 01:** the Q sign-in / "connected via Builder ID" state.
- [ ] Open this folder (`Amazon Q devloper test`) in VS Code.
- [ ] (Optional) `python -m venv .venv` and `pip install -r requirements.txt`
      so you can actually run any tests Q generates.
- [ ] Note your installed extension **version number** (Extensions tab) —
      you'll cite it in the post for reproducibility.

## Day 2 — Test Case 1: unit tests (45–60 min)

- [ ] Open `src/` (the agent pipeline: planner, researcher, writer, orchestrator).
- [ ] Use the test-generation command/agent (see `PROMPTS.md` #1a). Let it
      write into `tests/test_pipeline.py`. Ensure it mocks `bedrock_client.invoke`.
- [ ] **Screenshot 02:** Q generating the happy-path tests (mocked Bedrock).
- [ ] Run them: `pytest -q`. **Screenshot 03:** the passing run.
- [ ] Now push for failure paths (`PROMPTS.md` #1b): throttling mid-research,
      empty subtasks, zero-findings writer, no-op retry loop, missing "question".
      **Screenshot 04:** the gap (what it added vs missed).
- [ ] Jot 3 bullet observations while fresh (works / breaks / verdict).

## Day 3 — Test Case 2: security scan (30–45 min)

- [ ] Open `infra/agent_stack.py` (the wildcard IAM lives here).
- [ ] Run the Q security scan on the project (`PROMPTS.md` #2a).
- [ ] **Screenshot 05:** the finding for `actions=["*"], resources=["*"]`.
- [ ] **Screenshot 06:** the suggested/one-click remediation.
- [ ] Test the limit: ask it to trace the permissions the agents actually
      need across files (`PROMPTS.md` #2b). **Screenshot 07:** where it stays local.
- [ ] Jot observations.

## Day 4 — Test Case 3: agentic refactor (45–60 min)

- [ ] Ask the agent to untangle `orchestrator.py` (`PROMPTS.md` #3a).
- [ ] **Screenshot 08:** the multi-file diff / proposed new files.
- [ ] Accept it, re-run `pytest`. **Screenshot 09:** tests still green after refactor.
- [ ] Test the limit: ask it to add a new `critic` agent and wire it through
      the whole pipeline + tests + IAM (`PROMPTS.md` #3b).
      **Screenshot 10:** where the coordinated multi-file change breaks down.
- [ ] Jot observations.

## Day 5 — Publish (60–90 min)

- [ ] Push the repo to a **public GitHub** repository.
- [ ] Fill `BLOG-DRAFT.md` with your real observations + screenshots + the scorecard.
- [ ] Verify the 2027 plugin-EOL note against the official page; keep it accurate.
- [ ] Paste into Medium, drop images, add the GitHub link, tag: `AWS`,
      `Amazon Q`, `AI`, `Multi-Agent`, `Developer Tools`.
- [ ] Read once for the "balanced verdict" tone. Publish.
- [ ] Share the link in the AWS Community Builders channel.

---

## Screenshot shot-list (quick reference)

| # | Shot | Section |
|---|---|---|
| 01 | Builder ID connected | Setup |
| 02 | Test generation (happy path) | TC1 |
| 03 | `pytest` passing | TC1 |
| 04 | Missing failure-path tests | TC1 |
| 05 | Wildcard IAM finding | TC2 |
| 06 | Suggested remediation | TC2 |
| 07 | Local-only context limit | TC2 |
| 08 | Orchestrator refactor diff | TC3 |
| 09 | Tests green post-refactor | TC3 |
| 10 | Cross-file change breakdown (critic agent) | TC3 |

**Screenshot hygiene:** hide any account IDs / emails; crop to the panel;
use a readable VS Code theme and font size for Medium's width.
