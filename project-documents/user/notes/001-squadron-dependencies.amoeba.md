---
docType: dependency-register
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
audience: [human, ai]
description: Cross-repo dependencies Amoeba places on Squadron, with priority, blocking-status, and the Amoeba initiative each gates. Hand-off doc for the Squadron team to start work in parallel.
dateCreated: 20260620
dateUpdated: 20261020
status: not_started
---

# Amoeba → Squadron Dependency Register

Purpose: surface, **as early as possible**, every change Amoeba needs from Squadron, so the Squadron team can work in parallel rather than on Amoeba's critical path. Each item states what Amoeba needs, why, which Amoeba initiative it gates, whether it is **blocking**, and a recommended priority.

All claims below are grounded in a read-only inspection of the Squadron source (`src/squadron/{review,pipeline,cli}`); file:line citations are included so the Squadron team can start from the exact code.

## TL;DR for the Squadron team

The good news first: **most of what Amoeba needs already exists.** Programmatic-enough invocation (JSON output), per-invocation model selection, and a machine-readable verdict are all present today. That leaves a **short** list of genuine asks:

| # | Item | Blocking? | Priority | Gates | Status (observed 2026-10-20) |
|---|---|---|---|---|---|
| S1 | **Checkability-tier field** on each emitted finding | No (Amoeba infers in v1) | **High** — start early; it's the long-pole quality item | 120 routing | Not delivered. `category` still free-form. Finding triage (SQ slice 186, a `scope` field) unstarted. |
| S2 | **In-process review API** (export `run_review_with_profile`) | No (CLI works) | Medium | 120, 140 ergonomics | Not delivered. |
| S3 | **CONCERNS vs PASS in exit code** (or documented JSON-only contract) | No | Low | 120 routing | Unchanged (2 = FAIL, 1 = unsaved, else 0). JSON `verdict` is the gate. |
| S4 | **Auto-fix-and-recheck** pipeline capability | No (deferred) | Low / later | a future 120 routing branch | Effectively delivered as revise loops in every phase pipeline. Escalation on checkpoint (SQ 185) unstarted. |
| S5 | **Native consensus/N-run aggregation** | No (Amoeba builds it) | **None / optional** | 140 (Amoeba owns this) | Not needed. |
| S6 | Derived-verdict flag in frontmatter | No | High | 120 gating | Met another way: `verdictSource: stated\|derived\|imposed` in frontmatter and JSON. `fallback_used` stays JSON-only. |
| S7 | `location_verified` and `finding_scan` in `to_dict()` | No | Medium | 120 tier inference | Delivered in JSON (per-finding `location_verified`, top-level `finding_scan`). Not in frontmatter. |
| S8 | Run-level or review-completed event | No | Medium | 100 seam, 120 | Not delivered. Events are still `commit` and `post-action` only. |
| S9 | Caller-supplied or launch-printed run id for `sq run` | No (matching works) | Medium | 100 recovery, 120 | **Delivered on Squadron main 2026-10-20** (commit ca9608b0, #243), not yet in a release. Public `sq run <pipeline> <target> --run-id <id>`, documented in Squadron's `docs/PIPELINES.md` ("Launching from another program"). Id rule: letters, digits, `.`, `_`, `-`; first character a letter or digit; max 128. An invalid id exits 1 before anything runs; an existing id exits 1 ("already exists"); cannot be combined with `--resume`. Every fresh run prints a plain `run_id=<id>` line to stderr before its first step; resumed runs do not. |
| S10 | Machine-readable run outcome with pause reason | No (pause escalates) | Medium | 120 routing | Filed as squadron #244 (2026-10-20); queued, not started. `--json` on `sq runs wait` / `sq runs show`, carrying checkpoint reason, step, verdict. |
| S11 | `merge` param on code pipelines (P6, `implement`, P56, P456), default true | No (Amoeba ships its own P6 without the merge) | Medium | 120 merge policy | New ask 2026-10-20. Pipeline steps have no on/off switch today, so this needs a small Squadron mechanism; sq-cf recommends it, PM's call. |

Net: **nothing here blocks Amoeba.** S1 is still the highest-value quality item. S9 and S10 are what the Runner (120) most wants next.

---

## What already exists (no Squadron work needed)

Confirmed in source — Amoeba will build on these as-is:

- **Machine-readable findings.** `sq review --output json` emits stable JSON via `ReviewResult.to_dict()` — `verdict`, `findings[]`, and `structured_findings[]` (`{id, severity, category, summary, location}`). `src/squadron/cli/commands/review.py:127-139`, `src/squadron/review/models.py:78-110`.
- **Per-invocation model selection.** `sq review --model <id|alias>` overrides the template model; resolution order is CLI flag → per-template config → global → template default. `src/squadron/cli/commands/review.py:251-277`. **This is why native consensus (S5) is not needed** — Amoeba can call N times with N models and aggregate itself.
- **Verdict via exit code (partial).** Exit code `2` = `FAIL`, `0` = everything else; full verdict enum `{PASS, CONCERNS, FAIL, UNKNOWN}` available in the JSON. `src/squadron/cli/commands/review.py:439,507,710`, `src/squadron/review/models.py:10-16`.
- **Daemon-independent pipeline/review runs.** `sq run` / `sq review` do **not** require the resident daemon (it manages agent lifecycle only). This is why Amoeba can reuse the daemon as its substrate base without breaking SQ execution. (Concept finding E.)

---

## The dependencies

### S1 — Checkability-tier field on emitted findings  ·  **High priority, non-blocking**

**What Amoeba needs:** each emitted finding self-classifies its checkability tier at emission time — Tier 1 (mechanically verifiable predicate), Tier 2 (semantic-coverage judgment), Tier 3 (mixed). A new field on `StructuredFinding`, e.g. `tier: 1|2|3` (or `checkability: mechanical|judgment|mixed`).

**Why:** Amoeba's routing policy keys on tier, not severity. Two facts from source make this important:
- `severity` (`{PASS, NOTE, CONCERN, FAIL}`) is too coarse — `concern` spans both mechanical rule-violations and semantic judgment, so it can't drive routing alone. `src/squadron/review/models.py:19-25`.
- **`category` is a free-form string** (no controlled vocabulary; defaults to `"uncategorized"`). `src/squadron/review/parsers.py:107`, `models.py:121`. **This is a correction to an earlier Amoeba assumption** — we cannot reliably infer tier from `category`. v1 inference therefore leans on `severity` + per-finding heuristics, which is lossy. The emitted tier field replaces a fragile heuristic with a clean signal.

**Bonus value:** because Tier-1 claims are deterministically verifiable, an emitted tier yields **free eval data** on which categories the reviewer classifies reliably vs. confabulates — exactly the calibration signal Amoeba's "build by inducing failure" method wants.

**Blocking?** No. Amoeba ships v1 with `severity`+heuristic inference (concept decision: "tier inferred inside Amoeba for v1"). But this is the **highest-value** Squadron item and the one with the longest useful life, so it's worth queuing the Squadron team on it **soon** even though Amoeba isn't blocked.

**Gates:** Amoeba initiative **120 (Runner & Routing)** — improves routing accuracy; does not block its existence.

**Suggested shape for Squadron:** add `tier` to `StructuredFinding` + `to_dict()`; have the review prompt instruct the reviewer to self-classify; parse it leniently (default to Tier 2 / "judgment" if absent, never silently to Tier 1).

---

### S2 — In-process review API  ·  **Medium priority, non-blocking**

**What Amoeba needs:** a supported, exported Python entry point to run a review and get `ReviewResult` back in-process, instead of `subprocess` + JSON parsing.

**Why:** `run_review_with_profile()` exists and returns a `ReviewResult` dataclass, but it is **not exported** (`review/__init__.py` is a stub; not in `__all__`). `src/squadron/review/review_client.py:52-60`, `review/__init__.py:1`. `execute_pipeline()` *is* exported (`pipeline/__init__.py:37-53`) — so the pipeline path is already clean; the review path is not.

**Blocking?** No — Amoeba will shell out to `sq review --output json` for v1, which is a stable contract. This is an **ergonomics/robustness** upgrade (no subprocess overhead, typed returns, no output-file plumbing).

**Gates:** ergonomics for **120** and **140**. Nice-to-have, not a blocker.

**Suggested shape for Squadron:** export `run_review_with_profile` (and `ReviewResult`/`StructuredFinding`) in `review/__init__.py.__all__`, with a documented stability guarantee.

---

### S3 — Distinguish CONCERNS from PASS without parsing prose  ·  **Low priority, non-blocking**

**What Amoeba needs:** a machine-readable way to tell `CONCERNS` from `PASS` without reading the JSON body — e.g. distinct exit codes, or a documented guarantee that the JSON `verdict` field is the contract.

**Why:** today exit code `2` = `FAIL` and `0` = everything-else, collapsing `PASS`/`CONCERNS`/`UNKNOWN`. `src/squadron/cli/commands/review.py:439,507,710`. Amoeba's routing wants to branch on CONCERNS specifically.

**Blocking?** No — Amoeba already parses `--output json` for `structured_findings`, so it reads `verdict` from there anyway. This is purely a "would be cleaner" item.

**Gates:** **120** routing tidiness. Lowest-effort of the list; can be folded into S1's work.

---

### S4 — Auto-fix-and-recheck pipeline capability  ·  **Low priority, explicitly deferred**

**What Amoeba would eventually use:** a Squadron capability to *act* on a finding — regenerate the offending artifact (e.g. add the missing load-test task to a task breakdown) and re-run the review — driven non-interactively.

**Why it's Squadron's, not Amoeba's:** acting on a finding is a *pipeline capability*. Squadron already has the building blocks: loop conditions (`REVIEW_PASS`, `REVIEW_CONCERNS_OR_BETTER`, `ACTION_SUCCESS`) and an on-exhaust **checkpoint** action — but the checkpoint is **human-triggered**, not automated. `src/squadron/pipeline/executor.py:215-243,307-385`. Auto-fix = making that loop drive a regeneration step automatically. Amoeba's job is to *route to* this and read the verdict, not to own regeneration logic.

**Blocking?** No — explicitly deferred in the concept. v1 Amoeba routing is **continue / Judge / escalate**; there is no auto-fix branch until this lands.

**Gates:** a *future* routing branch in **120** ("auto-fix-and-recheck" for Tier-1 findings). Build only after the first Kalshi proof has run and shown it's worth it.

---

### S5 — Native consensus / N-run aggregation  ·  **Optional / likely NONE**

**Original concern (now downgraded):** the concept identified that Squadron has no built-in N-run / N-model agreement scoring, and assigned the aggregation to Amoeba.

**Why it's likely no Squadron work at all:** since per-invocation model selection already works (see "What already exists"), Amoeba can run the same review across N models / N runs by calling `sq review --model …` N times and computing agreement itself. **The consensus metric is Amoeba's to own (initiative 140) and needs nothing new from Squadron.**

**The only thing that would make this a Squadron item** is if, for efficiency, we later want Squadron to run N evaluations in one pipeline (via `fan_out` + a new consensus reducer) rather than Amoeba orchestrating N separate calls. That's an optimization, not a requirement — defer unless N-call overhead proves painful.

**Blocking?** No. **Gates:** nothing — listed only so the Squadron team knows it was considered and consciously left out.

---

## Recommended action for the Squadron team

1. **Queue S1 (tier field) now.** It's the only High item, it's the highest-value quality lever, and it has the longest useful life. Everything else can wait.
2. **S2 / S3** are small; fold them in opportunistically (S3 can ride along with S1's emission changes).
3. **S4 / S5** — do nothing yet; revisit after Amoeba's first Kalshi proof produces real induced-failure data showing whether they're worth it.

None of these block Amoeba from starting initiative 100 (Substrate) or 120 (Runner), which depend on Squadron only through the already-existing CLI/JSON contract.

## Notes

- **Context Forge initiative 240 (Review-Aware Workflow Gating) — landed** (CF 0.9.0/0.10.0). The shipped config keys are `workflow.review_enabled` / `review_threshold` / `review_unknown_as` / `review_gates.{arch,slice,tasks,code}.threshold` / `review_gate_effective_date` — **not** `workflow.review_required` as originally recorded here. `score` is parsed but not enforced. The Runner reads the gate via `workflow_status.activeSlice.status` + `gateInfo`, not `workflow_next`'s prose. Amoeba **consumes** this gate rather than reimplementing it. (Canonical: `context-forge/docs/REVIEW-GATING.md`; boundary rationale: `context-forge/project-documents/user/notes/001-review-gating-architecture-input.context-forge.md`.)
- **Status as of 2026-09-13:** S1, S2, S3, S5 not delivered. **S4 is effectively delivered** — `findings-addressed-cycle.yaml` (slice 303/305) is an unattended revise → review → gate loop with `checkpoint: on-concerns` as a human backstop; the remaining gap is that a non-interactive checkpoint exits rather than escalating (SQ slice 185, unstarted). Amoeba invokes this loop rather than building an auto-fix branch. Ground truth with citations in `002-upstream-delta.amoeba.md` §4 and §9.
- **Defects reported to Squadron 2026-09-13 (filing requested via sq-base):** stdout `--output json` omits `verdict_override`, so judge templates report `verdict: UNKNOWN` while the artifact carries the real verdict (`review.py:217-219` vs `persistence.py:588`); `_aggregate_verdicts` KeyErrors on UNKNOWN; stale `merge_findings` comment at `reducers.py:4`. Squadron slice 189 (`merge_findings` reducer) is the SQ-side home for S5 if ever wanted.
- **New asks appended 2026-09-13:**
  - **S6 — derived-verdict flag in frontmatter** (SQ #97). `fallback_used` reaches `--output json` but not `_review_frontmatter_lines`; CF's gate reads frontmatter, so a derived PASS auto-clears it. One-line builder change; **PM decision** because it alters a contract CF consumes. Priority High, non-blocking for Amoeba (we gate on JSON).
  - **S7 — expose `location_verified` and `finding_scan` in `to_dict()`.** Computed today, deliberately withheld from every machine-readable surface. Tier-1 signals (hallucinated citation, parser mangling). Priority Medium, non-blocking.
  - **S8 — a run-level or review-completed event.** The events system has exactly `commit` and `post-action`; an orchestrator needs "review persisted" to subscribe to rather than poll. Priority Medium, non-blocking; relevant to the CF 220 seam Amoeba now owns.
  - Agreed with slice 918 (in flight): `stop_reason`, `reasoning_chars`, `failed_tool_calls` added to `to_dict()` as optional keys — retry-vs-escalate predicates.
  - **S9 — caller-supplied or launch-time-emitted run ID for `sq run`.** `StateManager` already accepts `run_id: str | None` (`pipeline/state.py:202-211`) but the CLI has no `--run-id`; the ID is generated internally and only learnable after the fact. Amoeba's crash-recovery journal (arch 100, "command-before-result") must otherwise match a journaled launch against the runs directory by pipeline + params + timestamp. A `--run-id` option, or printing the run ID to stderr before execution starts, makes recovery exact. Priority Medium, non-blocking (matching works; ambiguity becomes a blocked-state). *(Added 2026-09-13 from arch 100 review F002.)*
  - Noted, no ask: implicit resume in `sq run` is gated on `sys.stdin.isatty()` (`cli/commands/run.py:1207`), so a non-interactive caller never triggers it. Amoeba resumes only via explicit `--resume <run_id>` and always invokes with non-TTY stdin.
- **Status as of 2026-10-20** (re-grounded against Squadron main for arch 120; details in the table above):
  - Fixed: stdout `--output json` now carries the judge's score-derived verdict (Squadron issue #140), so judge templates no longer report `UNKNOWN`.
  - Slice 918 fields `stop_reason`, `reasoning_chars`, `failed_tool_calls` are always emitted in JSON (not frontmatter).
  - **Run outcome contract (sq-cf, 2026-10-20):** `sq run` exits 0 for completed *and* paused. Use `sq runs wait <id>`; its exit codes (`WAIT_EXIT_CODES` in `pipeline/run_wait.py`) are the contract: 0 completed, 1 failed, 3 paused, 4 timed_out, 5 not_found, 6 unreadable, 7 unknown_status, 8 orphaned; 2 is reserved for usage errors. **The run-state JSON under `~/.config/squadron/runs/` is internal and may change; do not read it directly.** Amoeba's recovery observer (arch 100) does read it today, so it should move to a supported surface once S9 or S10 lands.
  - **`sq runs wait <id> --timeout 0`** is a pinned contract (Squadron b5edb697, test plus a line in `docs/COMMANDS.md`). It reads the state file once and never sleeps; exit 4 means still running, and terminal states return their usual codes. A stale-heartbeat run also logs a WARNING on every call. This is how Amoeba's Runner polls in-flight runs.
  - Squadron's code pipelines commit their own output (`commit_each_iteration`) and end with `branch: { op: merge }`, which merges into the target with a merge commit, never pushes, and aborts cleanly on failure. Project-local pipelines are first-class (`sq pipelines list`, `sq run <name>`).
  - `--instructions` on `sq run` works only with `--resume ... --item N`, i.e. batch items. Per-phase runs have no channel for resolution instructions. No ask filed yet.
  - **S9:** delivered on Squadron main (ca9608b0, #243); it ships in the next patch release, and sq-cf will report the version. S10 is squadron #244, queued.
  - New since September and relevant to 120: batch pipelines (`slices-plan`, `tasks-plan`, `implement-plan`) write a per-item report beside the run; one flagged item resumes with `sq run --resume <id> --item N --decision retry|accept`. A task marked `BLOCKED` pauses a run for a person (`awaits_human`). Runs can fail with `cost_cap` (`pipeline.max_cost_usd`).
- This register is a living document. As Amoeba's initiatives reach architecture (P2) and induce real failures (P6), new Squadron asks may appear — they get appended here with the same priority/blocking/gates treatment.
- Correction logged: the concept and initiative plan assume tier can be *inferred* in v1; source shows `category` is free-form, so v1 inference relies on `severity`+heuristics and is lossier than implied. S1 is the clean fix. (Concept finding C should be read with this caveat.)
