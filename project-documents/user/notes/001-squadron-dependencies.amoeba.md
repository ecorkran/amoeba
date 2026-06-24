---
docType: dependency-register
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
audience: [human, ai]
description: Cross-repo dependencies Amoeba places on Squadron, with priority, blocking-status, and the Amoeba initiative each gates. Hand-off doc for the Squadron team to start work in parallel.
dateCreated: 20260620
dateUpdated: 20260620
status: not_started
---

# Amoeba → Squadron Dependency Register

Purpose: surface, **as early as possible**, every change Amoeba needs from Squadron, so the Squadron team can work in parallel rather than on Amoeba's critical path. Each item states what Amoeba needs, why, which Amoeba initiative it gates, whether it is **blocking**, and a recommended priority.

All claims below are grounded in a read-only inspection of the Squadron source (`src/squadron/{review,pipeline,cli}`); file:line citations are included so the Squadron team can start from the exact code.

## TL;DR for the Squadron team

The good news first: **most of what Amoeba needs already exists.** Programmatic-enough invocation (JSON output), per-invocation model selection, and a machine-readable verdict are all present today. That leaves a **short** list of genuine asks:

| # | Item | Blocking? | Priority | Gates |
|---|---|---|---|---|
| S1 | **Checkability-tier field** on each emitted finding | No (Amoeba infers in v1) | **High** — start early; it's the long-pole quality item | 120 routing |
| S2 | **In-process review API** (export `run_review_with_profile`) | No (CLI works) | Medium | 120, 140 ergonomics |
| S3 | **CONCERNS vs PASS in exit code** (or documented JSON-only contract) | No | Low | 120 routing |
| S4 | **Auto-fix-and-recheck** pipeline capability | No (deferred) | Low / later | a future 120 routing branch |
| S5 | **Native consensus/N-run aggregation** | No (Amoeba builds it) | **None / optional** | 140 (Amoeba owns this) |

Net: **nothing here blocks Amoeba from starting.** S1 is the one worth queuing soon because it is the highest-value quality improvement and has the longest useful life. The rest are ergonomics or explicitly-deferred.

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

- **Context Forge initiative 240 (Review-Aware Workflow Gating)** is the upstream home for the deterministic, AI-free review gate Amoeba's Runner (init 120) would otherwise have to own: `cf next` itself becomes review-aware (config-driven `workflow.review_required` / `workflow.review_threshold`, reading the Squadron slice-300 verdict/score frontmatter contract). Amoeba **consumes** this gate rather than reimplementing it — one less thing the routing engine builds. Tracked in CF, not as a Squadron dependency, since it's CF-side logic; recorded here only so the Runner's architecture knows the gate exists and reads its result. (CF input doc: `context-forge/project-documents/user/notes/001-review-gating-architecture-input.context-forge.md`.)
- This register is a living document. As Amoeba's initiatives reach architecture (P2) and induce real failures (P6), new Squadron asks may appear — they get appended here with the same priority/blocking/gates treatment.
- Correction logged: the concept and initiative plan assume tier can be *inferred* in v1; source shows `category` is free-form, so v1 inference relies on `severity`+heuristics and is lossier than implied. S1 is the clean fix. (Concept finding C should be read with this caveat.)
