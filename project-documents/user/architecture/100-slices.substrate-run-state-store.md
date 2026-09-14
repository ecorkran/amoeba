---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/100-arch.substrate-run-state-store.md
archIndex: 100
component: substrate-run-state-store
audience: [human, ai]
description: Slice plan for Amoeba initiative 100 — decomposes the substrate and run-state store into foundation, feature, and integration slices that each leave the system in a working state.
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Slice Plan: Substrate and Run-State Store

## Parent Document

`100-arch.substrate-run-state-store.md`

## Planning Context

Architecture-level. Greenfield — Amoeba has no code, so there are no migration or refactoring slices. The parent architecture document has already settled the decisions that would otherwise fan out across slice design: the substrate is Amoeba-internal behind a documented contract (OQ6, ratified), the resident process is the **sole writer** with a durable inbox as the only externally-writable surface, and Amoeba owns the event-seam half of CF initiative 220 (slices 221, 224, 225, 226; CF keeps 222, 223, 227, 228).

Two consequences shape the decomposition:

- **The contract is the deliverable, not the engine.** Initiatives 120, 140, and 160 all code against this component's read/write interface. Slice 101 exists to make that interface real and stable as early as possible, because every downstream initiative is blocked on it.
- **Sole-writer collapses what would otherwise be concurrency slices.** Because only the resident process mutates the store, there is no distributed-write slice, no lock-arbitration slice, and no conflict-resolution slice. The inbox (slice 104) is where that decision is paid for, and it is deliberately adjacent to the resident process (slice 103).

## Foundation Work

1. [ ] **(101) Store Foundation and Node Model** — The lifecycle node schema and the read/write contract every other initiative codes against. Establishes the project-keyed node tree (initiative → phase/artifact → slice → gate), the closed status vocabulary (`runnable`, `in_progress`, `blocked_on_human`, `blocked_on_judge`, `blocked_on_sq_checkpoint`, `done`), blocked-state records with an explicit resolution slot, CF/SQ reference fields (project id, phase, slice, artifact path, SQ run ids, reviewed SHA), and the two queries the Runner's loop consumes — "what is runnable?" and "what is blocked and on whom?". Also lands the storage engine decision, the schema-version stamp, and the migration mechanism, because every later slice adds tables to a store that must already know how to migrate itself. Ships with a library-level API and no process around it: a test can open a store, write nodes, and query them.
   **Value:** Architectural enablement — unblocks all of 120/140/160 by making the contract real.
   **Success Criteria:**
   - Node tree can be created, read, updated, and queried by project, status, and parent.
   - Runnable and blocked queries return correct results across all status values.
   - Blocked-state records carry a resolution slot; filling it flips the node runnable.
   - Schema carries a version stamp; a migration from version N to N+1 runs and is tested.
   - Status vocabulary is defined once as an enumeration and referenced everywhere.
   - Contract is documented well enough that initiative 120 can code against it without reading the implementation.
   **Dependencies:** None (foundation).
   **Interfaces:** Provides the store read/write API consumed by every subsequent slice and by initiatives 120, 140, 160.
   **Risk Level:** Medium — the schema is hard to change once downstream initiatives depend on it.
   **Relative Effort:** 4

## Feature Slices

2. [ ] **(102) Findings, Verdicts, and Provenance** — The evidence layer. Content-based finding identity with a defined normalization rule (Squadron's finding ids are positional and not stable across runs, so identity cannot key on them), per-iteration finding status, and verdict records carrying full provenance: source (stdout JSON vs artifact frontmatter), `fallback_used` derivation flag, failure-artifact status, judge score and criteria, SQ run id, reviewed SHA, and the upstream version the record was parsed from. Includes the SQ 280 typed-artifact scope (`review_findings`, `checkpoint`, `task_progress`, `devlog`) as record types in the store. Records what a mechanical check examined alongside its result, so a check that ran against nothing is distinguishable from one that passed.
   **Value:** Developer value — the Runner can ask "is this the same finding as last round?" and "is this PASS trustworthy?", neither of which CF's gate nor SQ's output can answer alone.
   **Success Criteria:**
   - The same finding emitted across two runs with different positional ids resolves to one identity.
   - Normalization rule is defined, documented, and tested against real Squadron finding text.
   - A verdict record distinguishes a genuine PASS from a derived PASS (`verdict == PASS && fallback_used`) and from a provider-failure placeholder.
   - Judge invocation samples (model, run id, score, verdict) are recorded individually, not collapsed.
   - Calibration evidence is queryable and reportable; nothing writes back into Squadron's metrology store.
   - Every ingested record stores the upstream version it was parsed from.
   **Dependencies:** [101]
   **Interfaces:** Provides finding/verdict/judge-sample records to initiatives 120 (routing) and 140 (consensus); consumes the store API from 101.
   **Risk Level:** Medium — normalization correctness is the crux, and getting it wrong is silent.
   **Relative Effort:** 4

3. [ ] **(103) Resident Process and Recovery** — The long-lived process that hosts the Runner loop and is the store's sole writer. Start/stop/status lifecycle, PID and single-instance handling, graceful shutdown, and the command journal: an entry is written before a side-effecting command is issued and resolved when its result arrives. On restart, journaled-but-unresolved entries are reconciled by observation — CF writes are idempotent and read back for comparison; Squadron runs are matched against the runs directory by pipeline, params, and timestamp, where exactly one match is adopted and zero-or-several becomes an explicit `blocked_on_human` node carrying the journal entry. Includes the local inspection surface (the `sq artifacts list` analogue) for looking at store contents without writing a client.
   **Value:** Architectural enablement — makes restart-survival real, which is what the concept's "checkpoint is a persisted blocked-state" depends on.
   **Success Criteria:**
   - Process starts, reports status, and shuts down gracefully; a second instance refuses to start.
   - A command journaled and then interrupted before resolution is reconciled on restart, not re-issued.
   - The zero-match and multiple-match reconciliation cases both produce a blocked node rather than a guess.
   - Killing the process mid-operation and restarting loses no committed state.
   - Inspection surface lists nodes, findings, verdicts, and journal entries.
   **Dependencies:** [101]
   **Interfaces:** Hosts the Runner (initiative 120); provides process lifecycle commands; consumes 101's store API.
   **Risk Level:** High — crash recovery is the hardest correctness problem in this component and the arch doc flags it as rewrite-expensive if wrong.
   **Relative Effort:** 4

4. [ ] **(104) Durable Inbox and Message Queue** — The one surface parts outside the resident process may write to, and the channels between them. Durable append from outside the process (including while the process is down, with submissions applied on restart), plus the point-to-point channels: intent (Translator → Runner), escalation (Runner → Translator and notification bridge), and inbound human reply (bridge → a blocked node's resolution slot). Defines delivery and replay semantics and the apply loop by which the resident process consumes the inbox and commits the resulting writes.
   **Value:** Architectural enablement — without it the sole-writer model has no way for the Judge, Translator, or notification bridge to contribute state, which blocks initiatives 140 and 160.
   **Success Criteria:**
   - An out-of-process writer can append to the inbox while the resident process is stopped; the submission is applied when it starts.
   - The apply loop is idempotent — replaying an already-applied submission does not double-write.
   - A human reply landing in the inbox fills a blocked node's resolution slot and flips it runnable.
   - Delivery and replay semantics are documented (what is guaranteed, what is not).
   - No path exists for an external writer to mutate the store except through the inbox.
   **Dependencies:** [101, 103]
   **Interfaces:** Provides the inbox API consumed by initiatives 140 and 160 and by the notification bridge; consumes 101 and 103.
   **Risk Level:** Medium
   **Relative Effort:** 3

5. [ ] **(105) Outbound Change Feed and Detection of External Work** — The half of the event seam that does not depend on Context Forge. Outbound: a publish/subscribe change feed that emits state-change notifications to subscribers (the Translator surface, a status view, later Cowork). Inbound: detection of work nobody in Amoeba issued — a review artifact appearing under `project-documents/user/reviews/` from a PM-launched `sq review` (the field norm), and human replies arriving. Detection ownership follows who issued the action: commands the Runner issued are observed by the Runner at process exit and reported into the store; this slice detects only the rest. Structured so that Squadron's review-completed event (dependency S8), if it ever lands, replaces the filesystem watching without changing subscribers.
   **Value:** Developer value — the Translator and any status view stop polling, and PM-launched reviews become visible to the Runner.
   **Success Criteria:**
   - A subscriber receives a notification when a node's status changes.
   - A review artifact written by an external `sq review` is detected and ingested as a verdict record with correct provenance.
   - A provider-failure artifact is detected as a failure, not as a review that happened.
   - Detection is replaceable by an upstream event without changing the subscriber contract.
   - Subscribers that disconnect and reconnect do not corrupt feed state.
   **Dependencies:** [101, 102, 103]
   **Interfaces:** Provides the change feed consumed by initiative 160 and by status views; consumes 101, 102, 103.
   **Risk Level:** Medium
   **Relative Effort:** 3

6. [ ] **(106) Context Forge Event Seam** — The CF-side half of the seam, and the scope absorbed from CF initiative 220 (CF slices 221 daemon lifecycle, 224 storage event emission, 225 server-initiated notifications, 226 client subscription model). Replaces polling `cf next` with push: CF state changes made by any client become events Amoeba's seam receives and applies to the node tree. CF retains the transport work it did not delegate (222, 223, 227, 228), so this slice must state precisely which side owns the daemon process and what the wire contract is. Because 222 and 227 on CF's side were specified as depending on CF's 221 — which is now Amoeba's — the dependency inversion must be resolved with the CF team before this slice is designed.
   **Value:** Architectural enablement — removes the last polling loop and makes multi-client CF coordination possible.
   **Success Criteria:**
   - A CF project mutation made by another client produces an event Amoeba receives.
   - Received events update the node tree without a full re-read of `projects.json`.
   - The subscription model filters by project.
   - Missing an event (process down, subscriber disconnected) degrades to a reconciling re-read rather than silent drift.
   - The CF-side ownership boundary and wire contract are documented and agreed with the CF team.
   **Dependencies:** [101, 103, 105]
   **Interfaces:** Consumes CF's storage events; provides CF-sourced state changes to the node tree and the change feed.
   **Risk Level:** High — spans two repositories and an unresolved cross-project dependency inversion.
   **Relative Effort:** 4

## Integration Work

7. [ ] **(107) Contract Proof and Hardening** — Prove the contract from the outside before initiative 120 commits to it. An end-to-end exercise driving a realistic lifecycle sequence through the substrate — nodes created, a Squadron run journaled and its verdict ingested, a blocked-state written and resolved through the inbox, a restart mid-sequence, subscribers observing the whole thing — using only the documented API, no internal access. Closes out store-locality behavior (per-project versus per-supervisor), the pruning policy for paused Squadron runs that SQ never prunes, and documentation for downstream initiative authors.
   **Value:** Developer value — the contract is demonstrated to work for its actual consumer rather than assumed to.
   **Success Criteria:**
   - A full lifecycle sequence runs through the public API with no internal access.
   - A restart injected mid-sequence leaves the sequence completable and the final state correct.
   - Store locality behaves correctly for the chosen model and is documented.
   - Pruning policy for paused SQ runs is implemented and documented.
   - Contract documentation is sufficient for initiative 120's slice design to proceed against it.
   **Dependencies:** [101, 102, 103, 104, 105]
   **Interfaces:** Consumes the full public contract; produces the documentation initiatives 120/140/160 design against.
   **Risk Level:** Low
   **Relative Effort:** 3

## Implementation Order

`101 → 103 → 104 → 102 → 105 → 107`, with `106` sequenced when the CF dependency inversion is resolved.

Rationale, in the guide's order of precedence:

- **Dependencies.** 101 is foundation for everything. 103 needs only 101. 104 needs the process it appends into. 102 needs only 101 but is placed after 104 deliberately (see testability).
- **Testability.** 101 + 103 + 104 is the earliest point at which a vertical path exists: something outside the process can submit, the process applies it, state persists, and a restart preserves it. That is the substrate's core claim, provable before any evidence-layer work.
- **Risk.** 103 is the highest-risk non-CF slice (crash recovery) and is placed second so its problems surface early rather than after four slices depend on it.
- **Enablement.** 102 unblocks initiative 140's consensus work and the Runner's routing; 104 unblocks 160. Both land before the integration slice.
- **106 is deliberately unsequenced.** It depends on a cross-project decision that is not Amoeba's alone. The other six slices deliver a working substrate without it — the Runner polls CF until 106 lands, which is exactly the pre-220 behavior — so 106 can slot in whenever CF's side is settled without blocking anything.

## Notes

- Slice 106 is blocked on a cross-repository question, not on code: CF's slices 222 and 227 were specified as depending on CF's 221, which Amoeba now owns. Until the CF team resolves that inversion, 106 should not enter slice design. The delegation request has been sent to the CF session.
- Finding normalization (slice 102) has an open question with the Squadron team: whether slice 305's `findings_addressed/screens.py` contains a canonical normalization worth reusing. If it does not, Amoeba defines its own and accepts that "same finding, reworded" is a judgment question for initiative 140 rather than a store question.
- Slices 102 and 105 both depend on Squadron output shapes that change without semver. Both record the upstream version they parsed, per the arch doc's schema-versioning consideration.
- No migration or refactoring slices exist — Amoeba is greenfield. If the substrate is later extracted into a peer package (the deferred half of OQ6), that extraction is a migration slice added here at that time.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Peer-primitive extraction** — If Squadron, Context Forge, or Cowork ever consume the store directly, extract it from Amoeba into a versioned package. Deferred half of the OQ6 decision; requires a second consumer to justify the repository and compatibility contract.
2. [ ] **Squadron review-completed event (S8) adoption** — Replace slice 105's filesystem detection with a real upstream event if Squadron adds one. Subscriber contract is designed to make this a swap.
3. [ ] **Caller-supplied Squadron run id (S9) adoption** — Replace slice 103's match-by-attributes reconciliation with exact run-id matching if Squadron exposes `--run-id` or emits the id at launch.
4. [ ] **Multi-project supervision surface** — The node model is project-keyed from slice 101, so running several lifecycle trees at once is a quantity change. The supervision view over a forest of runnable/blocked/done nodes is not built here.
5. [ ] **Store compaction and retention** — History grows without bound. Retention policy for resolved nodes, superseded verdicts, and applied journal entries is deferred until there is real data volume to measure.
