---
docType: notes
layer: project
project: amoeba
audience: [human, ai]
description: What changed in Squadron, Context Forge, ai-project-guide, and trading-data between the June 2026 concept and September 2026, and how each change modifies Amoeba's design before Phase 2 begins.
dateCreated: 20260913
dateUpdated: 20260913
status: complete
---

# Upstream Delta — June → September 2026

Purpose: Amoeba's concept (P0) and initiative plan (P1) were grounded against Squadron (SQ), Context Forge (CF), and ai-project-guide as of 2026-06-20. Since then: SQ +773 commits, CF +361, trading-data +669, ai-project-guide 0.15.6 → 0.17.4. This note records every upstream change that modifies Amoeba's design, so Phase 2 architecture starts from current ground truth. Sources: live peer sessions (sq-pr, squadron-e7, cf-base, td-api-kalshi, ai-project-guide) cross-checked by read-only source inspection on 2026-09-13.

Nothing below invalidates the three-part architecture (Runner / Translator / Judge, communicating only through CF/SQ state). What changes is what Amoeba **builds vs. consumes**, two **ownership boundaries**, and the **first proof**.

## Ownership decisions (PM, 2026-09-13)

- **SQ initiative 280 "Shared Agent Artifact Store"** (SQLite, typed `review_findings` / `checkpoint` / `task_progress` / `devlog` artifacts, `sq artifacts list`) — unstarted in Squadron; **Amoeba owns this scope now.** It merges into initiative 100 (Substrate & Run-State Store). Squadron's per-pipeline `RunState` stays Squadron's; Amoeba's store is the project-lifecycle layer that references SQ run IDs.
- **CF initiative 220 "Event-Driven Pipeline"** (persistent MCP daemon, `cf server start/stop/status`, port 3100, server-initiated notifications for multi-client coordination) — active in CF's plan but slice 221 unstarted, `packages/server` does not exist; **Amoeba owns this** (confirmed by PM 2026-09-13). It is the push-based substrate seam that replaces polling `cf next`. CF's plan should mark 220 as delegated so slice 221 is not started on the CF side.

## 1. Squadron has a Judge — re-scope initiative 140

- SQ initiatives 300 (Intrinsic LLM Judging & Scoring) and 320 (Judge Calibration & Metrology) are **complete**. Judge templates emit `score` + `criteria` in artifact frontmatter; `verdict` for judges is score-derived and passed as an override (`src/squadron/review/persistence.py:266-301`). A findings-addressed judge exists (`src/squadron/review/addressed/judge.py`, `pipeline/actions/findings_addressed/`). `src/squadron/data/pipelines/judge-cycle.yaml` runs `loop: {max: 3, until: review.pass, on_exhaust: checkpoint}`.
- **Consensus is still Amoeba's.** `fan_out` + model pools exist, but the only reducers are `collect` and `first_pass` (`pipeline/intelligence/fan_in/reducers.py:139-140`); `merge_findings` is SQ slice 189, unstarted; `consensus` has zero hits in SQ `src/`.
- **Design change:** initiative 140 becomes *Consensus & Judge Invocation* — invoke SQ judges N times (per-invocation `--model` works), own aggregation and the deterministic threshold. Do not build a scorer.

## 2. Run-state ownership confirmed; boundary drawn

- CF still persists **pointers only** (`packages/core/src/types/project.ts:6-36`): no findings, checkpoints, run history, blocked states, escalations. Gate state is recomputed from disk every call. CF's 240 architecture explicitly names Amoeba as the consumer of the gate and places reconciliation "above CF's layer" (`context-forge/project-documents/user/notes/001-review-gating-architecture-input.context-forge.md`).
- SQ now persists per-run state: `RunState`, `StepState`, `CheckpointState`, run IDs `run-{date}-{slug}-{uuid8}`, one JSON per run, resumable via `sq run --resume <run_id>` (`src/squadron/pipeline/state.py`).
- **Boundary:** Amoeba 100 = project-lifecycle run-state (phases, checkpoints as persisted blocked-states, escalations, verdict-per-iteration), referencing SQ run IDs. SQ = per-pipeline execution state. Plus the 280 artifact-store scope now folded into 100.

## 3. CF review gating landed (initiative 240) — consume the structured surface

- Shipped in CF 0.9.0/0.10.0 across slices 240–243; canonical doc `context-forge/docs/REVIEW-GATING.md`; evaluator `packages/core/src/introspection/reviewGate.ts`.
- Config keys: `workflow.review_enabled` (default false), `review_threshold` (`pass|concerns`), `review_unknown_as` (`fail|concerns|pass`), `review_gates.{arch,slice,tasks,code}.threshold`, `review_gate_effective_date`. **`workflow.review_required` never shipped** — the dependency register's Notes section is wrong on the name. Review *type* is position-derived (`preSlicePlan→arch`, `preTasks→slice`, `preImplementation→tasks`, `preAdvance→code`), never configured.
- `workflow_next` reports an unmet gate only as **prose** in `recommendation` (`WorkflowNavigator.ts:335-353`). **Branch on `workflow_status.activeSlice.status ∈ {pending-review, review-failed}` + `gateInfo.reviewType`**, not on strings.
- `score` is parsed but **not enforced**; gating is verdict-only. Multiple artifacts → lexicographically last wins.
- **Two silent-ungate escape hatches the Runner must detect:** `review: none` on a slice design (exempts every non-arch boundary; PM-only per guide 0.17.4; trading-data has 8, five shipped ungated) and `dateCreated` before `review_gate_effective_date` (exempts every boundary).
- No `cf next --go` or execute mode; `cf next` is read-only advisory. Amoeba stays the executor. `workflow.auto_advance` is a consumer-layer concern; a firing gate wins naturally.
- `cf validate frontmatter` (0.12.0): scriptable, exit 0/1/2, `--json` — a Runner pre-commit gate. **Caveat:** it silently skips out-of-root paths in a registered worktree and exits 0 with `filesChecked: 0` (cf#87/#88, sq#98). Any gate on a validator's exit code alone must also check what was examined.
- `agent_quickstart` MCP tool is CF's declared "for orchestrators and CI pipelines" entry point.
- Wire changes: status values underscored with no aliases since 0.12.0 (`in_progress`, `not_started`, `complete`, `deferred`, `deprecated`); phases 0–7; MCP results may carry a `notices[]` array (0.14.0); guide strategy `manual` → `tarball`.

## 4. Squadron asks S1–S5 — none delivered as filed

| # | Status | Ground truth |
|---|---|---|
| S1 tier | **No** | `StructuredFinding` = `{id, severity, category, summary, location}` (`review/models.py:32-40`); `category` still free-form regex (`parsers.py:105`); `checkability` zero hits. v1 inference (severity + heuristics) stands. |
| S2 in-process API | **No** | `review/__init__.py` is a docstring; no `__all__`. SQ disclaims semver: "no compatibility meaning" (`docs/PIPELINES.md:437`). Drive via CLI `--output json` + artifact frontmatter only. |
| S3 exit codes | **No** | `_exit_on()` (`cli/commands/review.py:380-396`): 2 = FAIL, 1 = unsaved *or* generic error, 0 = PASS/CONCERNS/UNKNOWN. `--json` is the gate. |
| S4 auto-fix loop | **Partial** | Multi-step `loop` + `judge-cycle.yaml` exist. On exhaust → checkpoint; non-TTY or `SQUADRON_NO_INTERACTIVE` → `CheckpointResolution.EXIT`, state saved (`executor.py:309-347`). Escalation behavior is SQ slice 185, unstarted. Amoeba's routing must treat "SQ run exited at checkpoint" as a persisted blocked-state and resume by run ID. |
| S5 consensus | **No** | See §1. Amoeba-owned as planned. |

## 5. New Squadron surfaces to design against

- **Events system** (slice 173): exactly two events, `commit` and `post-action`; `sq events fire` / `sq events list`; plugin bindings in `events.yaml`; built-in `squadron.review-verdict-gate` rejects staging any review whose `verdict` is not a `Verdict` member (`events/builtin/review_verdict_gate.py`). Actions Observe / Fail / Mutate — no WARN tier. No run-level or review-completed event exists.
- **Failure artifacts** (slice 917): provider failure writes `verdict: UNKNOWN` + `## Provider Failure` into the live slot, prior artifact archived. **Artifact exists ≠ review happened.**
- **`fallback_used` in `--output json`** (`models.py:170-172`): true exactly when the verdict was *derived* from findings after a failed summary parse, or a CONCERNS/FAIL parsed with zero findings (`parsers.py:753,780`). `verdict == PASS && fallback_used` is Amoeba's false-negative predicate — available on `main` today. Stays false in the nothing-parsed case (verdict is UNKNOWN there). Does not say *why* the parse failed (#96 newline-free shape vs ordinary).
- **Gap for PM (SQ #97):** `fallback_used` reaches JSON but **not** frontmatter (`_review_frontmatter_lines`, `persistence.py:205-257` emits `verdict` with no degradation flag). CF's gate reads frontmatter. A derived PASS therefore auto-clears CF's gate. Fix is one line in that builder (e.g. `verdictDerived: true`) but it changes a contract CF consumes — PM decision, raised with squadron-e7 who added the use case to #97.
- `location_verified` (tri-state, `models.py:65`) and `finding_scan` counts are computed but deliberately withheld from JSON and frontmatter. Small ask to add to `to_dict()`.
- **SQ slice 918** (in flight, squadron-e7): adds `stop_reason`, `reasoning_chars`, `failed_tool_calls` to `to_dict()` as optional keys (null when unstamped) — agreed 2026-09-13 as Tier-1 retry-vs-escalate predicates. Also makes re-review verdicts converge (#94) and adds four Run Digest lines to the artifact body (diagnostic, not contract).
- **Run Digest** (`persistence.py:162-194`) is a body section by design; frontmatter is the consumed contract. Treat the digest as human/debug only.
- **Frontmatter contract** (`_review_frontmatter_lines`): always `docType, layer, reviewType, slice, project, verdict, sourceDocument, aiModel, status, dateCreated, dateUpdated`; conditional `reviewedSha`, `revision_number`, `toolsGiven`, `toolCallsMade`, `toolsSuppressedReason`; judges add `score` + `criteria`; structured `findings:` list. Artifacts live in `project-documents/user/reviews/`, prior versions in `archive/`.
- **Initiative 380 Pull Request Workflow** (session sq-pr, worktree `squadron-pr`, ~43 commits behind `main`): 381 `sq pr show [TARGET] --json` merged on that branch only (read-only, `record.key = {host}/{owner}/{repo}#{n}` is the stable ID, exit 0/1, errors typed — classify on error type, never message text). 382–386 unstarted: 383 `review.external_reviews_dir`; **384 `sq review pr --post`** — first outward write, the seam for an approval/dry-run gate; 385 `sq pr create`. Every process call goes through one injected `ProcessRunner` (`CodeHost.runner`); `FakeProcessRunner.write_calls()` proves a run was read-only.
- SQ's initiative plan (`001-initiative-plan.squadron.md:53`) reserves the orchestrator role *above* Squadron consuming CLI/JSON and forbids that loop inside pipeline actions. Amoeba is the thing Squadron planned for.
- Daemon unchanged: signal handling + uvicorn + PID/socket, routes `agents` and `health` only. Still safe as substrate base (finding E holds). `core/message_bus.py` is a stub; SQ initiative 200 (Multi-Agent Communication) not started — no cross-session messaging to build on inside SQ.

## 6. Process changes (ai-project-guide 0.15.6 → 0.17.4)

- **`{index}-planning.{name}` branches removed** (0.15.8–0.15.12). Planning work (P0–P5) commits directly to the integration target. Slice branches remain `{index}-slice.{name}`, never prefixed. Amoeba's CLAUDE.md still mandates planning branches — stale until `cf guides update`.
- `git.integration_branch` (personal scope, `.context-forge.local.toml`) replaces `branch_root`; if set, slice branches fork from and merge into it; automation never merges to `main`. Never delete branches unless instructed.
- **Review gates are a hard stop:** "stop and report to the PM, or run the review." Never edit frontmatter to clear a gate. `review: none` is PM-only; agents must not add it, run `cf check --set-review-none`, or copy it from a template. A non-interactive runner models "review required" as a checkpoint needing a Squadron run or a PM decision.
- DEVLOG/session-summary phases explicitly do **not** decide next action — that belongs to orchestration (`guide.ai-project.process.md` ~177).
- Status enum canonical: `not_started | in_progress | complete | deferred | deprecated`.
- Legacy code-review guide cluster deleted in 0.17.1 (`guide.ai-project.090-code-review.md`, `prompt.code-review-crawler.md`, `agents/code-review-agent.md`, `skills/review.md`). Structured review is Squadron's.
- No orchestrator role or non-interactive operation is defined in the guide. Phase approval delegation unchanged: P0–P2 human PM; P3–P5 AI Architect under established patterns; P6 self-validate via tests/CI; P7 PM.

## 7. First proof is gone — pick later, not now (PM decision 2026-09-13)

trading-data initiative 260 (Kalshi, 7 slices) is complete and in production. The concept's first-proof target therefore no longer exists.

**Decision: do not anchor the proof to a specific sibling-project slice.** All sibling projects are moving; whatever looks unstarted today will likely be done by hand before Amoeba can run a proof. When Amoeba reaches proof stage, the PM picks from what is unstarted then.

Selection criteria recorded from the 2026-09-13 survey (the reusable part):
- Genuinely unstarted at the plan-entry level, so the runner drives P3→P6 end to end rather than entering mid-pipeline.
- Bounded scope with a fresh in-tree worked precedent of the same shape.
- Contains at least one genuine design decision — tests whether the runner *surfaces* a decision rather than silently picking.
- No production host / cutover step, no purchase decision, no repo-infrastructure change the runner itself would depend on (e.g. introducing CI).
- Low blast radius; no paper dependency on a large unstarted grind.

## 8. Field-observed failure shapes the Runner must model

From trading-data's 157 reviews and process journal, and the trading-data session:
- ~55% of reviews return CONCERNS (87/157); CONCERNS *passes* the gate at `threshold=concerns`; only FAIL/UNKNOWN needs re-review. 5 UNKNOWNs came from `sq review --diff` not writing an artifact (fixed by SQ 916/917).
- **Reviews are PM-launched by standing rule** in trading-data; the Claude session reports and addresses findings. "Review pending" is a first-class blocked state with a human in it.
- `cf status` reported Phase 0 throughout live work — read task checkboxes and frontmatter, not `cf status`. `cf check` findings are the real consistency gate.
- Task files split (`-1.md` / `-2.md`) when over the line guideline; the instruction prompt named a single non-existent file.
- `main` carries known-failing tests (4 integration + 2 config flakes). A runner treating any red as regression stalls permanently — diff against a baseline.
- Test tiers must run separately (`unit` / `integration` / `load`, env-gated); collecting all of `test/` at once yields ~49 spurious errors.
- `ruff format` rewrites unrelated lines in touched files; every commit needs a deletion scan.
- Host cutover sections are exactly three human steps (cut release, run one script, close from its report); merge + tag are the PM's only git act. Slices stall at the host step, not the code step.
- Time-shaped handoffs between slices (e.g. a tape draining over ~10 days).
- PM-ratified mid-slice reversals are common and recorded in slice-plan Notes; a slice (266) was retired outright and replaced.
- Runner must never invent bounds or effort estimates; load thresholds are measured first and recorded beside the number.
- SQ parser shapes live on `main`: #96 newline-free response collapses findings and drops the verdict; #97 derived verdict indistinguishable in frontmatter (§5); kimi27 shape — every tool call fails and the error blames the model.

## 9. Additions from the Squadron base session (2026-09-13, after §1–8)

Verified by sq-base against branch `918-slice.review-grounding`, pkg 0.12.2.

- **Bug Amoeba will hit:** `_display_json` (`cli/commands/review.py:217-219`) calls `to_dict()` without `verdict_override`, while persistence calls `to_dict(verdict_override=...)` (`persistence.py:588`). Judge templates parse to UNKNOWN and get their real verdict from a score floor, so **stdout JSON says `verdict: UNKNOWN` for every judge template** while the artifact says the true verdict. Until fixed: route judge templates on `score` (defaults `_DEFAULT_PASS_FLOOR=75.0`, `_DEFAULT_CONCERNS_FLOOR=50.0`, `pipeline/actions/judge.py:41-57`) or read the artifact. Filing requested. Related: `_aggregate_verdicts` (`review.py:446`) KeyErrors on UNKNOWN in multi-part tasks reviews.
- **Finding ids are positional, not stable.** `StructuredFinding` is derived on the fly (`models.py:182-196`); `id = f"F{i:03d}"` by enumeration order; `severity` there is a lowercased str, not the enum. Amoeba's run-state cannot key findings on `id` across runs; identity must be content-based (305's screens already do exact-match on content — asked sq-base whether there is a canonical normalization to reuse).
- **S4 is more delivered than §4 says.** `data/pipelines/findings-addressed-cycle.yaml`: loop max 3, `until: review.pass`, `commit_each_iteration: true`, body `dispatch(revise) → review(fresh) → gate(policy: findings-addressed)`, `checkpoint: on-concerns` — human is a backstop, not a step. Round 2+ dispatch synthesizes the fix prompt from the prior review's findings (`pipeline/actions/dispatch.py:346-394`). `implement.yaml` has no loop. Non-interactive checkpoint still exits (§4 caveat stands).
- **Daemon: frozen and unused — drop the relocation plan.** Last functional commit `e6acb1c1` (2026-05-19). The pipeline engine has zero references to it; all of `sq run` is in-process. `core/message_bus.py`, `topology.py`, `supervisor.py` are docstring stubs; no versioning on the HTTP API (unix socket `~/.squadron/daemon.sock` + `127.0.0.1:7862`, agent-lifecycle routes only). Finding E's "safe to relocate" holds technically, but sq-base advises against building on it without an explicit support commitment. **Design change:** Amoeba builds its substrate fresh (it now owns the CF 220 seam anyway); the daemon is not reused.
- **Squadron has already shipped most of the within-artifact runner** (ranked by collision with Amoeba):
  1. **Slice 303 judge-gated cycle** — review → fix → re-review with auto-advance and escalation on failure to clear. Shipped (`300-slices:65`).
  2. **Slice 305 findings-addressed gate** — deterministic screens first (round-1 annotated PASS; byte-identical round → FAIL at zero tokens; exact-match recurring → unaddressed), judge only on the residue; per-finding `addressed|unaddressed|moved|disputed`; verdict derived by rule, not taken from the model (`pipeline/actions/findings_addressed/{policy.py:41-80, screens.py:43-161, judge.py}`). Stated principle: "deterministic where measurable, model-backed where not, and the boundary explicit at each node" (`305-slice:49-52,:80`). **This is Amoeba's checkability tiering, already built for one question, under another name.**
  3. **Slice 322 calibration-to-threshold feedback** — graduation registry (`metrology/graduation.py`, `store.py:170-190`), `metrology.min_evidence_n`, judge floors in template YAML `judge:` blocks.
  4. 180 finding triage (in progress, not shipped) — tags findings `code|slice|architecture|process|external` by artifact level, auto-addresses the first two, escalates the rest.
  5. 210 ensemble review (planned) + 300 multi-sample judging (config, not default).
- **Three Squadron architectural constraints Amoeba must honor:**
  - **No automatic threshold mutation, permanently** (`320-arch:121`, `320-slices:66`). Loosening a gate is an operator decision on reported evidence. The concept's "per-category trust earned by calibration data lowers the always-escalate threshold" becomes *Amoeba recommends, PM changes* — never a runtime mutation.
  - **Metrology flows down as generated static config** (`320-arch:99`); the Runner must not query it live.
  - **Escalated-gate verdicts are anchored and inadmissible as blind agreement data** (`320-slices:116,:127`). Amoeba's escalation flow must never write verdicts into the metrology store.
- **No seam exists for an external orchestrator.** `VALID_GATE_POLICIES` (`actions/gate.py:30`) is for policies *inside* Squadron; the unbuilt 200-series task store puts the SQ CLI in the sequencer seat. The only forward nod is `320-slices:116` ("compatible with increasingly autonomous operation (Amoeba direction)"). Nearest generic item: `300-slices` Future Work 6, "Generic Judge-Over-Results Gate", deferred until a second concrete gate policy exists — an external checkability-tier router is essentially that item built outside Squadron.
- **Boundary this settles for initiative 120:** the Runner *invokes* Squadron's shipped loops (judge-cycle, findings-addressed-cycle) for within-artifact convergence and owns only the lifecycle-level loop — phases, slices, CF gates, cross-run blocked-states, and routing of what those loops escalate. Tier routing at the lifecycle level stays Amoeba's; tier routing inside a review round is 305's.
- **918 Part 1 (landed, `50d2f8de`):** document reviews (arch/slice/tasks and the slice-vs-arch / tasks-vs-slice judges) can no longer read anything under `project-documents/user/reviews/`. Prior-findings injection goes only through 305's findings-addressed judge (exempt). Amoeba must not rely on a reviewer discovering prior artifacts from the tree.
- **918 Part 2** task file updated (`76231a0d`) to serialize `stop_reason` / `reasoning_chars` / `failed_tool_calls` in `to_dict()`, citing Amoeba as the consumer; code not yet implemented.
- Misc: `Severity.CONCERN` (singular) vs `Verdict.CONCERNS` (plural); loop conditions are a closed set of three, `strategy:` is accepted but unimplemented; `fan_out` is blocked when an SDK session is live (`executor.py:1655`); implicit resume auto-detects a matching paused run for the same pipeline + params (`state.py:512-522`); paused runs are never pruned.

## Corrections to earlier Amoeba documents

- `000-concept.amoeba.md` finding C: still true (category free-form). Finding E: still true (daemon unchanged). Findings A/B/D: true, but B must add that SQ now has an unattended loop that exits at checkpoint non-interactively, and D must add that SQ has a scorer (§1).
- `001-initiative-plan.amoeba.md`: initiative 140 re-scoped (§1); initiative 100 absorbs SQ 280 scope and likely CF 220 (Ownership decisions) and no longer reuses the Squadron daemon (§9); initiative 120 invokes Squadron's shipped loops and owns only the lifecycle-level loop (§9); first proof replaced (§7).
- `000-concept.amoeba.md` "Decisions locked at concept": the *always-escalate until trust is earned* threshold decision must be reworded — Amoeba reports calibration evidence and recommends; the PM changes thresholds (§9 constraints).
- `001-squadron-dependencies.amoeba.md`: Notes section names `workflow.review_required` — the shipped key is `workflow.review_enabled`. S1–S5 status as of 2026-09-13 in §4. New asks to append: `fallback_used` (or a derived flag) in frontmatter (#97); `location_verified` + `finding_scan` in `to_dict()`; a run-level / review-completed event.

## Next steps

1. `cf guides update` to 0.17.4 and refresh CLAUDE.md branch rules (PM).
2. Apply the corrections above to the concept, initiative plan, and dependency register.
3. PM decisions still open: whether to ask Squadron for the #97 frontmatter flag (S6). CF 220 ownership: **confirmed by PM 2026-09-13** (Amoeba owns it). (First proof: deferred by decision — pick when ready, §7.)
4. Phase 2 architecture for initiative 100, committed directly on `main` per 0.17.x branch rules.
