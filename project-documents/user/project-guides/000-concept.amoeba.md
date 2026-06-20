---
docType: concept
layer: project
phase: 0
phaseName: concept
project: amoeba
audience: [human, ai]
description: Concept for Amoeba — an orchestration runner with deterministic control flow and bounded nondeterminism that drives Context Forge and Squadron through a project's full lifecycle, escalating to a human (or first to an ephemeral Judge) only where judgment is the actual work.
dependsOn: [000-pre-concept.amoeba.md]
dateCreated: 20260618
dateUpdated: 20260618
status: in_progress
---

# Amoeba

## Overview

Amoeba is an orchestration runner with **deterministic control flow and bounded nondeterminism** that drives a software project through its full Context Forge / Squadron lifecycle (P0 concept → P6 code), reducing human involvement to the points where judgment is the actual work.

## User-Provided Concept

> **Note on status:** This is a *pre-concept* — input for the P0/concept stage, not the finished concept. It front-loads the architectural decisions that should be locked before the runner starts, and deliberately leaves open the decisions the concept stage exists to make.
>
> **Note on the name:** Amoeba. In Amoeba's world, amoebas are immense, apex entities — formless, adaptive, and powerful. The name encodes the architecture: a single adaptive process that flows around each project's shape and extends ephemeral *pseudopods* (on-demand Judge nodes) to grab what it needs, then reabsorbs them. Subsystem vocabulary follows the metaphor (e.g. "the Amoeba extends a pseudopod to evaluate finding F002").
>
> **Repo description:** *Deterministic control flow, bounded nondeterminism, named after an apex amoeba.*
>
> **Note on "deterministic":** The control flow is deterministic; the system as a whole is not, because the Judge (and Squadron's reviewers) are LLMs. The precise and stronger claim is **bounded nondeterminism** — nondeterminism is confined to named, bounded subroutines whose blast radius is fixed by the deterministic structure around them, not by the subroutine itself. The Runner is a deterministic machine that calls nondeterministic oracles and applies fixed rules (thresholds, routing) to their answers; the structure determines how far any single bad answer can propagate. Avoid the bare phrase "deterministic orchestration" anywhere load-bearing — it overclaims in the one way a careful reader will catch.

#### High-Level Project Concept

Amoeba is an orchestration runner with **deterministic control flow and bounded nondeterminism** that drives a project through its full Context Forge / Squadron lifecycle — P0 concept through P6 code — with human involvement reduced to the points where judgment is the actual work. It is the "next level of automation" above Squadron: where Context Forge removed nondeterminism from scaffolding and Squadron placed nondeterminism deliberately inside pipeline steps, Amoeba removes the human from the *orchestration* of those pipelines wherever the orchestration is deterministic, and escalates to a human (or first to an ephemeral Judge) only where it isn't. The control flow is deterministic; the judgment subroutines (Judge, reviewers) are not — but the deterministic structure bounds how far any one of their outputs can propagate.

The governing principle is the same one the whole toolchain is built on: **every intelligence added to a system — human or AI — reduces its determinism, so you place intelligence only where judgment pays for the variance it introduces, and remove it everywhere else.** Amoeba applies this to its own design by splitting into parts with deliberately opposite natures:

* **The Runner** — a deterministic state machine. It executes a known command sequence (`cf set slice 104`, `cf build`, `sq run p4 104 -v`), reads structured findings, applies a routing policy, and either advances or writes a blocked-state. It has zero discretion. It is not an agent. It is Context Forge's shape pointed at the orchestration layer. The Runner is the central body; everything nondeterministic is a bounded subroutine it invokes and a deterministic rule it applies to the result.
* **The Translator** — a conversational AI at the human edge. It converts natural-language intent ("add Kalshi as a source in trading-data, follow the existing pattern") into the deterministic command sequence the Runner executes, and converts the Runner's structured findings back into natural language for the human. It does *not* run the project. It interprets intent and reports state.
* **The Judge** — an ephemeral, on-demand node (a *pseudopod*) the Runner spawns when it hits a finding that is *not* deterministically resolvable. The Judge runs a scored evaluation and returns `(resolution, confidence)`. The Runner then applies a deterministic threshold: confidence above threshold → apply resolution and continue (human never pinged); below → write blocked-state and escalate. The Judge is a nondeterministic intelligence, but **the Runner's use of it is deterministic** — the Runner does not judge, it calls a judger and applies a fixed rule to the number. The discretion lives entirely inside the ephemeral node; the orchestration around it stays a state machine. The pseudopod is spawned, used, and reabsorbed.

The parts never call each other directly. **They communicate through Context Forge / Squadron state.** The Translator writes intent into state; the Runner reads state and executes; the Runner writes findings and checkpoint-blocks into state; the Translator reads state to report and to surface escalations; the Judge reads the finding and its locked constraints from state and writes its resolution back. State is the interface — the same principle CF already runs on, extended one level up. This decoupling is what makes the whole thing async by construction: the Runner grinds while the human chats with the Translator whenever convenient, and nothing blocks waiting on anything.

Amoeba exists because building software with AI tools works until the project becomes at all complicated, then falls apart — and the part that still requires a human (running the pipeline, resolving each checkpoint, advancing each phase) is mostly deterministic and mostly not worth a human's time. Amoeba automates the deterministic orchestration layer, lets a Judge absorb the evaluable-but-not-mechanical findings, and preserves the human exactly where direction is set.

* This is a **standalone runner + thin conversational front-end + on-demand Judge**, built on top of existing Context Forge and Squadron installations. It does not replace either; it drives them.
* The Runner is deterministic Python (or equivalent), authored by hand — it is the interesting artifact and the embodiment of the project's own thesis.
* The Translator is an AI conversational layer (Claude Code VS Code extension, a chat interface, or both — the surface is interchangeable because it only reads/writes state).
* The Judge is a Squadron-invoked evaluation (Squadron already supports SDK sessions, tool calls, and multi-provider models — the Judge is a pipeline that scores a finding and returns a structured verdict).
* First proof: drive `trading-data` to add Kalshi as a data source, near-autonomously, with one front-loaded human checkpoint at concept.
* The single load-bearing design decision: **a checkpoint is a persisted blocked-state, not a blocking call.** The Runner writes "slice 104 P2 blocked-on-human, finding F002, awaiting resolution," stops touching that branch, and moves on to other runnable work or idles. When the resolution lands in state, the branch becomes runnable again. This is what makes async real, makes restart-survival free, and makes the eventual multi-project version a quantity change rather than a rewrite.

##### Target Users

Initially: Erik, driving his own projects (trading-data first, then the backlog of specialized utilities). The human role is **direction-setter and escalation-resolver**, not operator. The human locks concept, glances at the borderline P1 plan, and thereafter answers only the escalations the routing policy (and the Judge) raise.

This broadens as the routing policy and the Judge's calibration mature. Early on, more findings escalate (the policy is conservative and the Judge's threshold is set to always-escalate); as deterministic gates absorb the mechanically-checkable findings and the Judge earns trust, the escalation rate drops and the same person supervises more concurrent work. The eventual multi-project mode (running several lifecycle-trees at once) has the same single supervisor watching a forest of runnable / blocked / done nodes rather than a single linear run.

##### Proposed Technical Stack

* **Runner:** Hand-written deterministic state machine. Python is the natural choice (matches Squadron, matches the CLI surface). Core logic: `while runnable work exists: run command -> parse structured findings -> apply routing table -> advance, spawn Judge, or write blocked-state`.
* **Control surface into the toolchain:** the existing CF/SQ CLIs (`cf ...`, `sq run ...`), which are already deterministic. The Runner shells out and parses; it does not reimplement CF/SQ logic.
* **State:** the existing Context Forge / Squadron state plus a small amount of Amoeba-owned run-state (per-node status: runnable / blocked-on-human / blocked-on-judge / done; open findings; pending resolutions). Reuse CF/SQ state mechanisms where they fit rather than inventing a parallel store. *(See open question on the resident substrate / message queue.)*
* **Findings contract:** Squadron already emits structured findings (YAML front-matter, `severity` in {pass, concern, fail, note}, `category`, `summary`, `location`). The Runner parses these directly. *(See open question on the checkability tier — this likely needs an added field.)*
* **Translator:** an AI conversational layer with access to read/write CF/SQ state and to invoke CF/SQ commands. Could be the Claude Code VS Code extension, a chat surface, or an SDK-connected model. Interchangeable by design.
* **Judge:** a Squadron evaluation pipeline, spawned on demand, returning `(resolution, confidence)`. Confidence is *not* the model's self-reported number (poorly calibrated); the real metric is **agreement across N judge runs or across models** — which Squadron's multi-provider substrate is built for. Consensus = confidence; divergence = escalate.
* **Notification channel:** outbound Discord webhook on escalation (cheap, async, already acceptable). Inbound: a way to read the human's reply back into the blocked node's resolution. Deliberately *not* an autonomous-agent runtime (e.g. ZeroClaw) as the orchestration substrate — adopting an autonomous-agent framework as dumb plumbing contradicts the project's own thesis, and the notification half is a day of code.

##### Proposed Development Methodology

In general, favor simplicity and avoid over-engineering. Remember the cliche about premature optimization. Use industry standard solutions where practical and available. Avoid reinventing wheels.

* **DFS, not BFS, through the lifecycle tree.** Implement the first slice fully before planning the next, because early implementation reveals information that changes later design. BFS commits to downstream plans before upstream code has taught you why they're wrong.
* **Cherry-pick the easiest slice category first.** Validate the Runner, the routing table, and the Judge on low-risk work before pointing them at hard slices. The easiest category is where the routing table is most likely already correct.
* **Build by inducing failure** (the house method). Point the Runner at real work, watch where it stops that it shouldn't have, and refine the routing table or the Judge threshold at exactly that point. Each wrong escalation is the next deterministic gate or routing rule. Each missed escalation that should have fired is a finding-severity or Judge-calibration correction. Each confident Judge resolution that disagrees with what the human would have decided is calibration data that lowers (or holds) the threshold for that finding category.
* **Front-load judgment to manufacture downstream checkability AND judgeability.** Early human checkpoints (concept, borderline P1) are dense; they resolve the genuine unknowns into constraints. Done well, the front-loading is *why* later phases reach high autonomy: downstream tasks inherit constraints to verify against (checkability, for deterministic gates) and locked references to score against (judgeability, for the Judge), rather than decisions to make. Early human judgment earns the right to later autonomy.

**Checkpoint and review-gate policy (initial):**

| Phase | Gate | Human role |
|---|---|---|
| P0 concept | no formal review; **mandatory human checkpoint** | direction-setter; iterate until good before Runner starts |
| P1 initiative plan | no formal review; **usual human glance** | borderline; usually a yes/iterate |
| P2 architecture | review gate | Judge first; escalate on low consensus |
| P4 slice plan | review gate | Judge first; escalate on low consensus |
| P5 tasks | review gate | Judge first; escalate on low consensus |
| P6 code | review gate | Judge first; escalate on low consensus |

**Routing policy keyed on checkability tier, not category:**

* **Tier 1 — mechanically checkable predicate** (path exists, grep match, schema diff, typecheck; e.g. "slice number 193 vs 169", "no load-test task in `tests/load/`"). Run as deterministic gates *before* the AI reviewer where possible. Routing: auto-fail / auto-fix-and-recheck, never escalate, never Judge. Any Tier-1 finding the AI emits is deterministically verifiable, so the AI's mechanical claims are free to audit — and a deterministic check that *disagrees* with an AI Tier-1 claim is itself a high-value signal (the reviewer confabulated).
* **Tier 2 — semantic-coverage judgment** (e.g. "prompt-only capability probe omitted", "relative gate insufficient to confirm the NFR"). Judgment is the work. Routing: **Judge first** — score against the finding's own predicate and the project's locked constraints (reference-free / rubric-based, no golden output needed because the locked architecture *is* the reference). High consensus → resolve and continue. Low consensus → escalate to human. Current threshold = always-escalate (Judge runs and logs, human still decides) until the Judge earns trust.
* **Tier 3 — borderline / mixed** (a checkable core wrapped in a judgment, e.g. "timeout path untested"). Decompose: carve off the deterministic predicate to Tier 1, leave the residual judgment at Tier 2. Often a single finding is doing two jobs — detecting a mechanical gap and judging its significance — and only the second needs the Judge.

##### Summary

Amoeba runs Context Forge and Squadron through a full project lifecycle with **deterministic control flow and bounded nondeterminism**. A deterministic Runner (a state machine, not an agent) is the central body; a conversational Translator handles judgment at the human edge; an ephemeral Judge (a pseudopod) absorbs the evaluable-but-not-mechanical findings and returns a scored verdict the Runner trusts via a deterministic threshold. The parts communicate only through toolchain state. Humans are involved at the front-loaded concept checkpoint and at Tier-2 findings the Judge can't resolve with consensus. It is the toolchain's own thesis applied one level up: deterministic control flow around bounded nondeterministic subroutines, spending an intelligence only where judgment is the actual work.

##### Output Location

On adoption into a CF project, save the finished concept as `001-concept.amoeba.md` in the `user/project-guides/` directory.

---

## Refined Concept

> This section adds structured analysis on top of the User-Provided Concept above. It is grounded in a read-only inspection of the current Context Forge (`packages/core`, `packages/cli`, `packages/mcp-server`) and Squadron (`src/squadron/{review,pipeline,server,client}`) source. Where the source contradicts an assumption in the pre-concept, that is called out explicitly — those corrections are the main value this section adds.

### Problem & Motivation

Building software with AI tooling works until a project gets complicated, then degrades: the human becomes a full-time operator of a pipeline that is, step for step, **mostly deterministic**. Context Forge already removed nondeterminism from scaffolding; Squadron already placed nondeterminism deliberately inside review steps. The remaining human cost is the *orchestration* — running each command, reading each finding, deciding advance-or-block, and doing it again — plus the smaller, genuine-judgment cost of resolving the findings that aren't mechanical.

Amoeba removes the human from the deterministic orchestration and routes the genuine-judgment findings first to an ephemeral Judge, escalating to the human only on low Judge consensus. The thesis it embodies is the toolchain's own, one level up: **spend an intelligence only where judgment pays for the variance it introduces.** Why now: CF and SQ are both mature enough to expose deterministic CLI/MCP surfaces and structured findings, which is exactly the substrate a deterministic runner needs.

### Target Users

Initially **Erik**, as direction-setter and escalation-resolver (not operator), driving `trading-data` first and then a backlog of specialized utilities. The audience evolves only in *degree*, not in kind: as deterministic gates absorb mechanical findings and the Judge earns per-category trust, the escalation rate falls and the same single supervisor oversees more concurrent lifecycle-trees. No new user *role* appears; multi-project mode is the same person watching a larger forest of runnable / blocked / done nodes.

### Solution Approach

A **standalone Runner + conversational Translator + on-demand Judge**, built *on top of* existing CF and SQ installations. It drives them via their deterministic surfaces; it does not reimplement or replace either.

**Amoeba is a real subsystem, not a thin wrapper over CF/SQ state — and that is by design.** The source inspection makes the scope concrete: Amoeba owns its own structured findings/run-state store (finding A) and owns the consensus-aggregation logic the Judge needs (finding D). It does **not** absorb capabilities that are properly CF's or Squadron's: the emitted tier field (finding C) and auto-fix (finding B) are both **Squadron-side upgrades** Amoeba *routes to and reads from*, not logic Amoeba reimplements. The boundary is consistent — Amoeba orchestrates and judges; CF and SQ generate and act. "Thin" describes only the *Translator's command authority* (a narrow fixed whitelist) and the Runner's *discretion* (zero — it's a state machine). It does **not** describe Amoeba's footprint. The deterministic-control-flow / bounded-nondeterminism thesis is unchanged by this; a substantial deterministic machine is still a deterministic machine. The named pieces Phase 1 will formalize into initiatives:

1. **Runner** — the deterministic state machine and the project's core artifact. Loop: `while runnable work exists → run CF/SQ command → parse findings → apply routing table → {advance | spawn Judge | write blocked-state}`. Zero discretion; not an agent.
2. **Run-state store** — Amoeba-owned durable state for per-node status, open findings, blocked-states, and pending resolutions. (See "Where state actually lives" — this is a **correction** to the pre-concept's "reuse CF/SQ state": CF does not persist findings or checkpoints, so this store must exist as its own component.)
3. **Routing engine** — the Tier 1/2/3 policy and thresholds. Deterministic table; the place where "build by inducing failure" makes its edits.
4. **Judge** — a Squadron evaluation invoked on demand, returning `(resolution, confidence)` where confidence = cross-run / cross-model agreement. (See "Consensus is Amoeba's to orchestrate" — Squadron has no consensus primitive today.)
5. **Translator** — the conversational layer at the human edge (intent → command sequence; findings → natural language). Surface-interchangeable because it only reads/writes state and issues a narrow, fixed command set.
6. **Notification bridge** — outbound Discord webhook on escalation; an inbound path to land the human's reply back into the blocked node's resolution.
7. **Resident substrate** — the long-lived process hosting the Runner loop and the durable message-queue the Translator, Judge, and (later) Cowork leave each other messages on. (See "The daemon is safe to relocate.")

These are *named pieces*, not yet sequenced initiatives — Phase 1 will index and order them. DFS through the lifecycle tree (implement the first slice fully before planning the next) is the intended build order, starting from the easiest slice category.

#### Grounding findings (the corrections that matter)

These five facts come from the source inspection and should be treated as load-bearing for Phase 1/2. Each maps to one or more of the pre-concept's open questions.

**A. Where state actually lives — Amoeba must own a findings/run-state store.**
CF persists project *workflow* state cleanly (`projects.json` under `getStoragePath()`; readable/writable via MCP `project_get` / `project_update` and CLI `cf get`/`cf set --json`). All `cf` commands are deterministic (no AI in the loop). **But CF does not persist review findings, checkpoints, or judge outputs** — its only freeform slot is `customData.recentEvents`/`additionalNotes`, which is unstructured text. Squadron emits findings but is request-shaped (it does not retain a queryable findings store across runs). **Conclusion:** "communicate through CF/SQ state" holds for *workflow pointers* (phase/slice/artifact paths), but Amoeba must own a small structured store for findings, blocked-states, and pending resolutions. This is the pre-concept's "small amount of Amoeba-owned run-state" — confirmed *necessary*, not optional, and larger than "small" implies for findings. *(Resolves part of OQ6; corrects the Technical Stack "reuse CF/SQ state" line.)*

**B. Auto-fix does not exist in Squadron — v1 routing is continue / Judge / escalate.**
Squadron review is **read-only**: it emits findings and does not act on them. The only action-shaped mechanism is pipeline **loop conditions** (`REVIEW_PASS`, `REVIEW_CONCERNS_OR_BETTER`, `ACTION_SUCCESS`) with an on-exhaust **checkpoint** that is *human-triggered* (accept findings as next-iteration instructions, override, or exit-and-resume). **Conclusion:** there is a real **loop-until-verdict-improves** branch the Runner can drive deterministically, but no "regenerate the task breakdown to add the missing load-test task" auto-fix. v1 routing is **continue / Judge / escalate** exactly as the pre-concept's fallback predicted. True auto-fix (re-invoke a generation step, then recheck) is a later upgrade that belongs **in Squadron, not Amoeba** — acting on a finding is a *pipeline capability* (the same shape as Squadron's existing loop-conditions and human-triggered checkpoint actions, just automated). Amoeba's role stays *routing to* that capability and reading the verdict; it does not own the regeneration logic, which is squarely Squadron's identity. When the capability lands in Squadron, Amoeba gains an "auto-fix-and-recheck" routing branch for Tier-1 findings; until then, v1 routes those to continue/escalate. *(Resolves OQ1.)*

**C. The findings contract has no tier field — adding one is a Squadron dependency.**
Squadron's structured finding is `{id, severity, category, summary, location}` with `severity ∈ {PASS, NOTE, CONCERN, FAIL}`. There is **no checkability-tier field**, and `concern` genuinely spans both mechanical rule-violations and semantic judgment — so the routing policy **cannot key on `severity` alone**, as the pre-concept already suspected. The clean fix (reviewer self-classifies each finding's tier at emission) is a **change to Squadron**, making it an Amoeba *dependency on Squadron* rather than something Amoeba owns. Until that field exists, Amoeba must infer tier in v1 — but note a refinement from a closer source read: **`category` is a free-form string** (no controlled vocabulary; defaults to `"uncategorized"`), so tier cannot be inferred from `category` reliably. v1 inference therefore leans on `severity` plus per-finding heuristics, and on Amoeba running its own Tier-1 deterministic predicates independent of severity. This makes the emitted tier field (tracked as Squadron dependency **S1**) the clean fix sooner rather than later. *(Resolves OQ2 and OQ3 together; see `notes/001-squadron-dependencies.amoeba.md`.)*

**D. Consensus is Amoeba's to orchestrate — Squadron has no consensus primitive.**
Squadron has **no built-in N-run / N-model agreement scoring.** It has `fan_out` + reducers (`collect`, `first_pass`) and pool-based per-action model selection, but nothing that runs the same evaluation N times and aggregates verdicts. **Conclusion:** "consensus = confidence" is **Amoeba's orchestration job** — the Runner drives N Squadron evaluations (across runs and/or the multi-provider pools Squadron does expose) and computes agreement itself — or it is a new Squadron feature. Either way it is not free, and the Judge component must own the aggregation logic. The pre-concept's instinct (don't trust self-reported confidence; use agreement) is right; the mechanism must be built. *(Resolves OQ4; the N, per-model-vs-per-run, and initial threshold remain to decide — see below.)*

**E. The Squadron daemon is safe to relocate — pipeline runs don't depend on it.**
The Squadron daemon manages **agent lifecycle only** (`sq spawn/list/task/message/history/shutdown`). **Pipeline and review runs (`sq run`, `sq review`) do not depend on the daemon**, and no Langfuse coupling to the daemon was found. **Conclusion:** the pre-concept's required confirmation — "nothing in Squadron's pipeline/Langfuse/session paths depends on the daemon being resident" — **holds.** The daemon can be reused as the base for Amoeba's resident substrate (item 7) and relocated out of Squadron's request-shaped identity without breaking pipeline execution. *(Resolves OQ6.)*

#### Decisions locked at concept

* **Checkpoint = persisted blocked-state, not a blocking call.** Unchanged and central. Enables async-by-construction, free restart-survival, and a quantity-not-rewrite path to multi-project mode.
* **State is the interface between parts** — for *workflow pointers* via CF, and for *findings/blocked-states/resolutions* via the Amoeba-owned run-state store (finding A). Parts never call each other directly.
* **v1 routing = continue / Judge / escalate** (finding B). Auto-fix is explicitly deferred.
* **Tier is inferred inside Amoeba for v1** (finding C). Amoeba derives each finding's tier from `category` plus its own Tier-1 deterministic predicates, run independently of Squadron's `severity`. No Squadron change is required to start; the emitted self-classified tier field stays a later upgrade, keeping the first Kalshi proof self-contained in one repo.
* **Initial Judge threshold = always-escalate** (Judge runs and logs; human still decides) until per-category trust is earned by calibration data.
* **Notification = outbound Discord webhook + an inbound reply path.** No autonomous-agent runtime as the orchestration substrate (it would contradict the thesis).

#### Open questions carried into Phase 1/2

The source inspection answered the *architecture-shaping* open questions (OQ1, OQ2/3, OQ6). These remain genuine and belong to later phases:

* **OQ4 calibration parameters:** choose N, decide consensus per-model vs per-run, and define the per-category trust-earning mechanism that lowers the always-escalate threshold over time. *(Phase 2 / tuned by induced-failure during P6.)*
* **OQ2 tier field, later upgrade:** the inference path is locked for v1 (see Decisions). The deferred decision is *when* to add the self-classified tier field to Squadron — for cleaner routing and free reviewer-reliability eval data — once the first proof has run. *(Phase 2+ cross-repo upgrade, not a blocker.)*
* **OQ5 Translator command authority:** fix the exact whitelist of `cf`/`sq` commands the Translator may issue, and flag any with side effects that warrant human confirmation even though the Translator is itself an intelligence. *(Phase 2.)*
* **OQ6 substrate scope:** decide whether the resident substrate + durable queue + structured run-state store is an Amoeba-internal component or a separate primitive that Squadron, Amoeba, and Cowork sit on as peers. *(Phase 1 boundary decision.)*
* **OQ7 Kalshi discovery:** a single front-loaded research step (granularity / history / structure of the Kalshi API) to turn the storage-format decision into a constraint to verify (predicted: relational → existing TimescaleDB) rather than a decision to make. Conditional escalation only if the data turns out non-relational. *(Phase 0/1 research step for the first proof.)*

### Initial Technical Direction

Directional, not committal (detailed stack decisions belong in Phase 2):

* **Runner:** hand-written deterministic state machine in **Python** (matches Squadron and the CLI surface). Shells out to / invokes `cf` and `sq`; parses structured output; applies a routing table. No AI in its own loop.
* **CF interface:** prefer **MCP tools** (`project_get`, `project_update`, `workflow_status`, `introspection_*`) or **`cf ... --json`** for clean programmatic read/write; avoid editing `projects.json` directly (no file locking).
* **SQ interface:** `sq run` / `sq review {slice|arch|tasks|code}` for evaluation; pipeline loop-conditions for the loop-until-verdict branch. `sq` agent-lifecycle commands (`spawn/list/task`) require the daemon; pipeline/review runs do not.
* **Run-state store:** Amoeba-owned, durable, structured (findings, per-node status, blocked-states, pending resolutions). Substrate TBD pending the OQ6 boundary decision — candidate base is the relocated Squadron daemon plus a durable message-queue; keep it as simple as the first proof allows.
* **Findings parsing:** parse Squadron's `{id, severity, category, summary, location}` front-matter leniently (semantic content, not exact formatting). Tier is **inferred** in v1 (no emitted tier field yet).
* **Judge:** a Squadron evaluation pipeline invoked N times across runs/models; **Amoeba computes the agreement metric.** Confidence = consensus, not self-report.
* **Translator:** AI conversational layer (Claude Code VS Code extension and/or a chat/SDK surface), interchangeable; narrow fixed command authority.
* **Notification:** outbound Discord webhook; inbound reply path into the blocked node's resolution.

### Development Approach

* **DFS through the lifecycle tree**, easiest slice category first, to validate Runner + routing table + Judge on low-risk work before hard slices.
* **Build by inducing failure** — point the Runner at real work, and treat every wrong escalation as the next deterministic gate / routing rule, every missed escalation as a severity/calibration correction, and every confident-but-wrong Judge resolution as threshold-calibration data.
* **Front-load judgment** at the concept and borderline-P1 checkpoints to manufacture downstream checkability (for deterministic gates) and judgeability (for the Judge).
* **First proof:** drive `trading-data` to add Kalshi as a data source, near-autonomously, with one front-loaded human checkpoint at concept and a single Kalshi-API research step.
* **Favor simplicity**; avoid premature optimization and avoid adopting an autonomous-agent framework as plumbing.
