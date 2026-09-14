---
docType: architecture
layer: project
project: amoeba
archIndex: 100
component: substrate-run-state-store
initiative: substrate-run-state-store
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: []
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for Amoeba's foundational layer — the durable project-lifecycle run-state store, the resident process that hosts the Runner, the durable message queue between parts, and the push-based event seam over Context Forge and Squadron.
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Architecture: Substrate & Run-State Store

## Overview

Amoeba's three parts — Runner, Translator, Judge — never call each other. They communicate only through state. This component **is that state**, plus the minimum plumbing needed for a long-lived process to keep reading and writing it: a durable, structured **run-state store** for the project lifecycle, a **resident process** that hosts the Runner loop and survives restarts, a **durable message queue** on which the parts leave each other intent and escalations, and a **push-based event seam** so the Runner reacts to Context Forge (CF) and Squadron (SQ) changes instead of polling for them.

**The problem it addresses.** Neither sibling tool persists what an orchestrator needs to remember. CF persists workflow *pointers* only (phase, slice, artifact paths); review and gate state are recomputed from disk on every call, and nothing records findings, checkpoints, escalations, or run history. Squadron persists *per-pipeline* execution state (`RunState`, resumable by run ID) but is request-shaped: it does not keep a queryable, cross-run view of findings or verdicts, and its finding ids are positional (`F001` by enumeration), so they cannot identify a finding across runs. There is no shared store, no long-lived process, and no seam through which an external orchestrator can be notified of anything — both projects planned one (SQ initiative 280, CF initiative 220) and both left it unstarted. The PM assigned that scope to Amoeba on 2026-09-13.

**Scope.** This component owns: (1) the lifecycle run-state schema and its read/write interface — per-node status, open findings with content-based identity, blocked-states, pending resolutions, verdict history, judge invocations and consensus results, calibration evidence, and the typed artifacts SQ 280 described (`review_findings`, `checkpoint`, `task_progress`, `devlog`); (2) the resident process and its start/stop/recover lifecycle; (3) the durable message queue; (4) the event seam (CF 220 scope: server-initiated notifications for multi-client coordination — ownership confirmed by PM 2026-09-13). It does **not** own parsing of SQ JSON/frontmatter or CF MCP results (the Runner's control surface, initiative 120), routing policy (120), consensus aggregation (140), or any conversational surface (160). The substrate contains zero intelligence: it is deterministic plumbing.

**Motivation.** Every other initiative attaches to this one. The Runner cannot exist without a place to persist what it learns; the checkpoint-as-persisted-blocked-state mechanic — the concept's single load-bearing decision — is a property of the store, not of the Runner; restart-survival and the eventual multi-project mode both fall out of getting this layer right and cost a rewrite if it is wrong.

## Design Goals

- **Single source of truth for lifecycle state.** Everything Amoeba knows about a project's progress that CF and SQ do not already hold lives here, once, in a typed schema. Any part can be restarted and reconstruct its view entirely from the store.

- **Checkpoint is a row, not a wait.** A blocked node (on human, on Judge, on a Squadron run that exited at a non-interactive checkpoint) is a persisted record with an explicit resolution slot. Nothing in the system blocks on a call; runnable work is a query.

- **State is the interface.** The store exposes one read/write contract that Runner, Judge, Translator, and the notification bridge all use. No part reaches around it to another part, and no part edits CF's `projects.json` or SQ's run files directly.

- **Push, not poll.** The resident process learns that CF state changed, a Squadron run finished, or a human replied, by subscription. Polling `cf next` is the fallback the seam exists to replace.

- **Evidence is retained; thresholds are not touched.** Every verdict, every judge invocation, every human resolution is kept as history. The store accumulates calibration evidence and surfaces recommendations; it never mutates a threshold at runtime and never writes into Squadron's metrology store.

## Architectural Principles

- **Reference, don't duplicate.** CF workflow pointers and SQ run IDs are referenced by key, never copied as authoritative. Amoeba's store is the lifecycle layer *above* both; when a fact is CF's or SQ's, the store holds a pointer and a snapshot-with-provenance, not a competing truth.

- **Identity is content-based.** Findings are keyed on normalized content (severity, location, summary), never on Squadron's positional `id`. Cross-run questions ("is this the same finding as last round?") must be answerable from the store alone.

- **Provenance on every ingested fact.** A verdict record says where it came from (stdout JSON vs. artifact frontmatter), whether it was derived (`fallback_used`), whether the artifact was a provider-failure placeholder, and which SQ run and reviewed SHA produced it. Presence of an artifact is never treated as evidence that a review happened.

- **Closed vocabularies for anything routed on.** Node status, blocked-state kind, resolution kind, verdict source, and tier are enumerations defined once. Free-form strings (Squadron's `category`, CF's prose `recommendation`) are stored as data and never used as logical structure.

- **Unknown is a value, not a default.** Missing or unparseable input is recorded as explicitly unknown and surfaces as a blocked-state; the store never fills a gap with a plausible default.

- **Command-before-result.** The substrate records that a command was issued before its result exists, so a crash mid-command is recoverable and never silently re-issues side-effecting work.

- **Project is a first-class key from day one.** Every record is scoped to a project so the forest-of-nodes multi-project mode is a quantity change. This does not mean building multi-project supervision now.

- **No intelligence in the substrate.** The substrate stores, queues, and notifies. Anything that decides belongs to the Runner, the Judge, or the human.

## Current State

- **Context Forge (0.14.x).** `projects.json` holds phase/slice/artifact pointers and free-text `customData`; `workflow_status` recomputes gate state from artifact frontmatter each call. Review gating (initiative 240) is consumed via `activeSlice.status ∈ {pending-review, review-failed}` + `gateInfo`; two silent-ungate hatches (`review: none`, `dateCreated` before `review_gate_effective_date`) exist and are not flagged. `cf next` is read-only advisory. CF initiative 220 (persistent MCP daemon, server-initiated notifications) is planned but slice 221 is unstarted and `packages/server` does not exist. CF's own review-gating architecture note places reconciliation "above CF's layer" and names Amoeba as the consumer.

- **Squadron (0.12.2).** Per-pipeline `RunState` / `StepState` / `CheckpointState`, one JSON per run under `~/.config/squadron/runs/`, resumable via `sq run --resume <run_id>`; paused runs are never pruned. A non-interactive checkpoint exits and saves state. Findings are `{id, severity, category, summary, location}` with positional ids and free-form category; `fallback_used` is in JSON but not frontmatter; stdout JSON currently reports `verdict: UNKNOWN` for judge templates (bug filed). The events system has exactly two events (`commit`, `post-action`) — no review-completed or run-level event. SQ initiative 280 (shared artifact store) is unstarted. The SQ daemon is frozen since 2026-05-19 and unused by SQ's own pipeline engine; its message-bus/topology/supervisor modules are stubs. Squadron's plan explicitly reserves the orchestrator role above itself.

- **Amoeba.** Nothing exists. There is no store, no process, no queue, and no seam. The Runner (120) is designed against this component's interface, so the interface must stabilize first.

**Constraints the current state imposes:** SQ disclaims semver on its Python API (CLI JSON + artifact frontmatter are the only contracts); CF's gate reads frontmatter, so a derived PASS clears it (Amoeba must gate on richer evidence than CF's gate alone); no notification exists for "review persisted," so run completion must be detected from process exit and artifact writes until S8 lands.

## Envisioned State

At completion, the substrate is a resident Amoeba process per supervisor (not per project) that owns a durable store and a durable queue, and exposes three surfaces:

1. **A lifecycle node model.** Each project is a tree of nodes (initiative → phase/artifact → slice → gate). Each node has a status from a closed set — at minimum `runnable`, `in_progress`, `blocked_on_human`, `blocked_on_judge`, `blocked_on_sq_checkpoint`, `done` — plus references into CF (project id, phase, slice, artifact path) and SQ (run IDs, review artifact paths, reviewed SHA). "What is runnable?" is one query; "what is blocked and on whom?" is another. The Runner's loop is a consumer of these two queries.

2. **Findings, verdicts, and resolutions with history.** Findings carry content-based identity, an inferred (later: emitted) tier, and per-iteration status. Verdicts carry provenance (source, derivation flag, failure-artifact flag, judge score/criteria where present). Blocked-states carry an explicit resolution slot that the Translator, the notification bridge, or the Judge fills; filling it flips the node runnable. Judge invocations record every sample (model, run ID, score, verdict) and the consensus result the Judge computed, so calibration evidence is queryable and recommendations can be reported to the PM. Nothing here feeds back into Squadron's metrology store.

3. **A queue and an event seam.** The queue carries intent (Translator → Runner), escalations (Runner → Translator/notification), and inbound human replies (bridge → blocked node). The event seam publishes state changes to subscribers (the Translator surface, a status view, later Cowork) and subscribes to upstream signals: CF state changes (the 220 scope — a persistent process that clients coordinate through instead of re-reading `projects.json`), SQ run completion, and human replies. Where an upstream signal does not exist yet (SQ review-completed, S8), the seam owns the detector so the Runner never does.

The Runner (120) runs inside the resident process and only ever reads and writes through surface 1–2 and consumes surface 3. The Judge (140) and Translator (160) attach through the same contract from outside the process. Restarting the process loses nothing: the store is the process's memory, and any in-flight command is either recorded-and-unresolved (recoverable) or not-yet-recorded (never issued).

## Technical Considerations

- **OQ6 boundary — Amoeba-internal component, exposed by contract (ratified by PM 2026-09-13).** The concept deferred whether the substrate is Amoeba-internal or a peer primitive that SQ, Amoeba, and Cowork sit on. Decision: build it *inside* Amoeba, behind a documented read/write contract, and treat extraction into a peer package as a later packaging decision. The PM assigned SQ 280 and CF 220 scope here, which makes Amoeba the de facto shared layer; making it a separate primitive up front adds a repo and a versioning contract before a single consumer exists.

- **CF 220 ownership — confirmed (PM, 2026-09-13).** Amoeba owns the event-driven-daemon scope CF planned as initiative 220. CF will not start slice 221; this component builds the CF-side half of the event seam. CF's plan should be updated to mark 220 as delegated to Amoeba so the two projects do not both build it.

- **Storage technology.** SQ 280 proposed SQLite for typed artifacts; SQ's `RunState` is one JSON per run; CF is one JSON file. The store needs multi-writer safety, queries across nodes and findings, and history — which rules out a single JSON blob but does not by itself choose the engine. Decide at slice design; the contract, not the engine, is the architectural commitment.

- **Concurrency and the single-writer question.** Runner, Judge, Translator, and the inbound reply path all write. Either the resident process is the sole writer and everything else enqueues, or the store arbitrates concurrent writers itself. The first is simpler and matches "state is the interface"; the second avoids the process being a bottleneck when it is down. Slice design must pick one and state the failure mode when the resident process is not running.

- **Finding identity normalization.** Content-based identity needs a normalization rule (whitespace, location format, summary wording drift). Squadron's slice 305 screens already do exact-match on content; whether a canonical normalization is reusable is an open question to sq-base. If not, Amoeba defines one and accepts that "same finding, reworded" is a Tier-2 question, not a store question.

- **Verdict provenance is richer than CF's gate.** The store must hold what CF's gate cannot see: `fallback_used`, failure-artifact status, the `review: none` and effective-date ungate hatches, and — for judge templates — the score-derived verdict read from the artifact rather than stdout until the SQ bug is fixed. The Runner gates on the store's view, never on CF's gate alone.

- **Squadron run lifecycle.** A run that exited at a non-interactive checkpoint is a `blocked_on_sq_checkpoint` node holding the run ID; resolution means `sq run --resume`. Implicit resume auto-detects a paused run for the same pipeline + params, so the store must know which paused runs it owns to avoid resuming the wrong one. Paused runs are never pruned on SQ's side; pruning policy is Amoeba's.

- **Schema versioning against unversioned upstreams.** SQ's JSON and frontmatter shapes change without semver; CF's wire values changed in 0.12.0 with no aliases. Every ingested record stores the upstream version it was parsed from, and the store's own schema is versioned with migrations from the first slice.

- **Metrology constraints from Squadron (permanent).** No automatic threshold mutation; metrology flows down as static config and is never queried live; escalated-gate verdicts are inadmissible as agreement data. The store keeps calibration evidence on Amoeba's side and exposes it as a report, never as a write-back.

- **Store locality.** Per-project (inside the repo, like `project-documents/`) versus per-supervisor (a central location like SQ's `~/.config/squadron/`). Multi-project supervision and "the process is not tied to any one repo" argue for central, keyed by project; auditability with the project's history argues for per-project. Slice design decides; the node model is project-keyed either way.

- **Baseline, not absolute, health signals.** Field data shows `main` carrying known-failing tests and validators that exit 0 having checked nothing (`filesChecked: 0`). Any mechanical check recorded in the store carries what was examined and a baseline reference, so the Runner can diff rather than treat every red as regression.

## Anticipated Slices

Exploratory, not a commitment:

- **Node model and core contract** — the lifecycle node schema, closed status vocabulary, blocked-state/resolution records, project keying, schema versioning, and the read/write interface every other initiative codes against. Runnable/blocked queries.
- **Findings and verdict records** — content-based finding identity and normalization, verdict provenance, judge-sample and consensus records, calibration-evidence report, and the SQ 280 typed-artifact scope (`review_findings`, `checkpoint`, `task_progress`, `devlog`).
- **Resident process** — start/stop/status lifecycle, recovery from the store on restart, command-before-result journaling, the single-writer decision, and the local inspection surface (the `sq artifacts list` analogue).
- **Durable message queue** — intent, escalation, and inbound-reply channels between Runner, Translator, Judge, and the notification bridge; delivery and replay semantics.
- **Event seam** — subscriptions and publishers: CF state-change notifications (the 220 scope, or consumption of CF's daemon if CF builds it), SQ run-completion detection, human-reply arrival, and the outbound change feed the Translator and status views subscribe to.

## Related Work

- Concept: `user/project-guides/000-concept.amoeba.md` — findings A (state ownership), E (daemon not reused), G (derived verdicts), "Decisions locked at concept."
- Initiative plan: `user/project-guides/001-initiative-plan.amoeba.md` — initiative 100 scope, DFS sequencing 100 → 120 → (140 ‖ 160).
- Upstream ground truth: `user/notes/002-upstream-delta.amoeba.md` — §2 (run-state boundary), §3 (CF gating surface), §5 (SQ surfaces, `fallback_used`, failure artifacts), §8 (field-observed failure shapes), §9 (daemon status, finding identity, metrology constraints), "Ownership decisions."
- Squadron dependency register: `user/notes/001-squadron-dependencies.amoeba.md` — S6 (derived-verdict flag in frontmatter), S7 (`location_verified` / `finding_scan`), S8 (review-completed event), slice 918 Part 2 fields.
- Context Forge: `docs/REVIEW-GATING.md`; `packages/core/src/introspection/reviewGate.ts`; initiative 220 (Event-Driven Pipeline) in CF's initiative plan; `notes/001-review-gating-architecture-input.context-forge.md`.
- Squadron: `src/squadron/pipeline/state.py` (`RunState`, run IDs, resume); `src/squadron/review/persistence.py` (frontmatter contract); initiative 280 (Shared Agent Artifact Store) in SQ's initiative plan; `320-arch` and `320-slices` (metrology constraints); slice 305 `findings_addressed/screens.py` (content-match precedent).
- Downstream consumers: initiatives 120 (Runner & Routing), 140 (Judge Invocation & Consensus), 160 (Translator & Notification) — all attach through this component's contract.
