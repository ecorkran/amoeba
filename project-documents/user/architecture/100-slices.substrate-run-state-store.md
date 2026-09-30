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
dateUpdated: 20260928
status: not_started
---

# Slice Plan: Substrate and Run-State Store

## Parent Document

`100-arch.substrate-run-state-store.md`

## Planning Context

Architecture-level. Greenfield — Amoeba has no code, so there are no migration or refactoring slices. The parent architecture document has already settled the decisions that would otherwise fan out across slice design: the substrate is Amoeba-internal behind a documented contract (OQ6, ratified), the resident process is the **sole writer** with a durable inbox as the only externally-writable surface, and Amoeba owns the scope of CF initiative 220, which it meets entirely on its own side by watching CF's `projects.json` (revised 20260928; see slice 108).

Two consequences shape the decomposition:

- **The contract is the deliverable, not the engine.** Initiatives 120, 140, and 160 all code against this component's read/write interface. Slice 101 exists to make that interface real and stable as early as possible, because every downstream initiative is blocked on it.
- **Sole-writer collapses what would otherwise be concurrency slices.** Because only the resident process mutates the store, there is no distributed-write slice, no lock-arbitration slice, and no conflict-resolution slice. The inbox (slice 103) is where that decision is paid for, and it is deliberately adjacent to the resident process (slice 102).

**Slice numbers are execution order.** They were renumbered on 20260930 (PM direction) to match the build order after the 104 split, the deferral of the Context Forge slice, and the addition of the Network API had left numbers out of sequence. The mapping, for reading older commits and reviews: parser and ingest 108→105, change feed 105→106, judge samples 109→107, Context Forge event seam 107→108, network API 110→109, contract proof 106→110. Slices 101–104 did not change. See Implementation Order.

## Foundation Work

1. [x] **(101) Store Foundation and Node Model** — The lifecycle node schema and the read/write contract every other initiative codes against. Establishes the project-keyed node tree (initiative → phase/artifact → slice → gate), the closed status vocabulary (`runnable`, `in_progress`, `blocked_on_human`, `blocked_on_judge`, `blocked_on_sq_checkpoint`, `done`), blocked-state records with an explicit resolution slot, CF/SQ reference fields (project id, phase, slice, artifact path, SQ run ids, reviewed SHA), and the two queries the Runner's loop consumes — "what is runnable?" and "what is blocked and on whom?". Also lands the storage engine decision, the schema-version stamp, and the migration mechanism, because every later slice adds tables to a store that must already know how to migrate itself. Ships with a library-level API and no process around it: a test can open a store, write nodes, and query them.
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

2. [x] **(102) Resident Process and Recovery** — The long-lived process that hosts the Runner loop and is the store's sole writer. Start/stop/status lifecycle, PID and single-instance handling, graceful shutdown, and the command journal: an entry is written before a side-effecting command is issued and resolved when its result arrives. On restart, journaled-but-unresolved entries are reconciled by observation — CF writes are idempotent and read back for comparison; Squadron runs are matched against the runs directory by pipeline, params, and timestamp, where exactly one match is adopted and zero-or-several becomes an explicit `blocked_on_human` node carrying the journal entry. Includes the local inspection surface (the `sq artifacts list` analogue) for looking at store contents without writing a client.
   **Value:** Architectural enablement — makes restart-survival real, which is what the concept's "checkpoint is a persisted blocked-state" depends on.
   **Success Criteria:**
   - Process starts, reports status, and shuts down gracefully; a second instance refuses to start.
   - A command journaled and then interrupted before resolution is reconciled on restart, not re-issued.
   - The zero-match and multiple-match reconciliation cases both produce a blocked node rather than a guess.
   - Killing the process mid-operation and restarting loses no committed state.
   - Inspection surface lists nodes, blocked states, and journal entries, through a listing registry that later slices extend rather than edit.
   **Dependencies:** [101]
   **Interfaces:** Hosts the Runner (initiative 120); provides process lifecycle commands; consumes 101's store API.
   **Risk Level:** High — crash recovery is the hardest correctness problem in this component and the arch doc flags it as rewrite-expensive if wrong. Sequenced early so its problems surface before later slices depend on it.
   **Relative Effort:** 4

3. [x] **(103) Durable Inbox and Message Queue** — The one surface parts outside the resident process may write to, and the channels between them. Durable append from outside the process (including while the process is down, with submissions applied on restart), plus the point-to-point channels: intent (Translator → Runner), escalation (Runner → Translator and notification bridge), and inbound human reply (bridge → a blocked node's resolution slot). Defines delivery and replay semantics and the apply loop by which the resident process consumes the inbox and commits the resulting writes. Also lands runtime project creation (a `create_project` submission makes the running process create and open a new store), folded in by PM decision 20260921 because nothing in 101–102 could bring a project into existence inside the process. Completing this slice closes the first vertical path through the substrate: an outside writer submits, the process applies, state persists, a restart preserves it.
   **Value:** Architectural enablement — without it the sole-writer model has no way for the Judge, Translator, or notification bridge to contribute state, which blocks initiatives 140 and 160.
   **Success Criteria:**
   - An out-of-process writer can append to the inbox while the resident process is stopped; the submission is applied when it starts.
   - The apply loop is idempotent — replaying an already-applied submission does not double-write.
   - A human reply landing in the inbox fills a blocked node's resolution slot and flips it runnable.
   - Delivery and replay semantics are documented (what is guaranteed, what is not).
   - No path exists for an external writer to mutate the store except through the inbox.
   - A project can be created through the inbox while the process is running, and submitted to without a restart.
   **Dependencies:** [101, 102]
   **Interfaces:** Provides the inbox API consumed by initiatives 140 and 160 and by the notification bridge; consumes 101 and 102.
   **Risk Level:** Medium
   **Relative Effort:** 4

4. [x] **(104) Findings, Verdicts, and Provenance** — Review records and finding matching. Each review result is stored with where it came from: verdict, how Squadron reached it, whether it was a provider failure, model, reviewed commit, SQ run id, and the upstream version label. Each finding is stored under a content key built by a documented matching rule, never under Squadron's position numbers. The store answers "what changed since the last round?" and puts a trust label on every verdict. The Judge submits reviews through a new inbox type. *Split 20260926:* parsing moved to 105; judge samples, calibration, check results, and the remaining typed records moved to 107.
   **Value:** Developer value — the Runner can ask "is this the same finding as last round?" and "is this PASS trustworthy?", neither of which CF's gate nor SQ's output can answer alone.
   **Success Criteria:**
   - The same finding emitted across two runs with different positional ids resolves to one identity.
   - The matching rule is defined, documented, and tested against real Squadron finding text.
   - A verdict record distinguishes a genuine PASS from a derived PASS and from a provider-failure placeholder.
   - Every recorded verdict stores the upstream version label it came from.
   - The inspection surface lists findings and verdicts, registered into 102's listing registry.
   **Dependencies:** [101, 102, 103] — 103 added at slice design: the Judge's write path is 103's inbox.
   **Interfaces:** Provides verdict and finding records to 105, 106, 107, 110, and initiatives 120 and 140; consumes the store API from 101 and the inspection listing registry from 102.
   **Risk Level:** Medium — matching correctness is the crux, and getting it wrong is silent.
   **Relative Effort:** 3

5. [ ] **(105) Squadron Review Parser and Ingest** — Split from 104 on 20260926. An adapter package outside the store (`amoeba.upstream.squadron`) that turns `sq review --output json` stdout or a review file into a verdict record input, plus `amoeba ingest review`, which parses a file and submits it through the inbox. Reads keys Squadron has not shipped yet (run id, version stamp, provider-failure flag, SQ 927's fields) when present. Built here, not in initiative 120, because slice 106 must ingest reviews it finds on disk before 120 exists. The first draft of this design is in 104's git history (commit `c525a63`).
   **Value:** Developer value — a real review becomes a stored record with one command, and 106 and the Runner share one parser.
   **Success Criteria:**
   - Every captured review file and stdout capture parses to the verdict, derivation, and findings it states; a provider-failure file parses as a provider failure.
   - The same review's file and stdout produce the same finding keys.
   - Unparseable input fails with a typed error and submits nothing; nothing is defaulted.
   - Ingesting the same file twice produces one record.
   **Dependencies:** [101, 103, 104] — 103 added at slice design: `amoeba ingest review` writes through its inbox.
   **Interfaces:** Provides the parser to 106 and initiative 120, and `amoeba ingest review` to the PM.
   **Risk Level:** Medium — Squadron's output shape moves without semver.
   **Relative Effort:** 3

6. [ ] **(106) Outbound Change Feed and Detection of External Work** — The half of the event seam that does not depend on Context Forge. Outbound: a publish/subscribe change feed that emits state-change notifications to subscribers (the Translator surface, a status view, later Cowork). Inbound: detection of work nobody in Amoeba issued — a review artifact appearing under `project-documents/user/reviews/` from a PM-launched `sq review` (the field norm), and human replies arriving. Detection ownership follows who issued the action: commands the Runner issued are observed by the Runner at process exit and reported into the store; this slice detects only the rest. Structured so that Squadron's review-completed event (dependency S8), if it ever lands, replaces the filesystem watching without changing subscribers.
   **Value:** Developer value — the Translator and any status view stop polling, and PM-launched reviews become visible to the Runner.
   **Success Criteria:**
   - A subscriber receives a notification when a node's status changes.
   - A review artifact written by an external `sq review` is detected and ingested as a verdict record with correct provenance.
   - A provider-failure artifact is detected as a failure, not as a review that happened.
   - Detection is replaceable by an upstream event without changing the subscriber contract.
   - Subscribers that disconnect and reconnect do not corrupt feed state.
   **Dependencies:** [101, 102, 103, 104, 105] — 105 added at the 104 split: detected reviews are ingested through its parser. 103 added at slice design: directory registration and human replies both arrive through its inbox.
   **Interfaces:** Provides the change feed consumed by 109, initiative 160, and status views; consumes 101, 102, 103, 104, 105.
   **Risk Level:** Medium
   **Relative Effort:** 3

7. [ ] **(107) Judge Samples, Checks, and Calibration** — Split from 104 on 20260926. Judge samples are verdict records grouped by a judge-invocation id, recorded one by one and never merged; a read-only calibration report summarizes them by review type and model, and writes nothing back to Squadron. Mechanical check results record what was examined, so a check that ran against nothing is labelled vacuous rather than passed. The SQ 280 typed-artifact scope: `review_findings` is 104's records and `checkpoint` is 101's blocked state; `task_progress` and `devlog` get a small record table with opaque content until a consumer defines their fields. The first draft of this design is in 104's git history (commit `c525a63`).
   **Value:** Developer value — unblocks initiative 140's consensus work, and lets the Runner tell a vacuous check from a pass.
   **Success Criteria:**
   - Judge samples (model, run id, score, verdict) are recorded individually, not collapsed.
   - Calibration evidence is queryable and reportable; nothing writes back into Squadron's metrology store.
   - A check that examined nothing is distinguishable from one that passed.
   - Every recorded item stores the upstream version label it came from.
   **Dependencies:** [104, 105, 106] — 105 added at slice design: judge samples are ingested through its parser and `amoeba ingest review`. 106 added at slice design: it takes the preceding migration and this slice extends its previous-round query.
   **Interfaces:** Provides judge-sample, calibration, and check records to 110 and initiatives 120 and 140.
   **Risk Level:** Low
   **Relative Effort:** 3

8. [ ] **(108) Context Forge Event Seam** — CF state changes made by any client (CLI, MCP, another agent) become records and feed entries in Amoeba, without polling `cf next` and without any change to Context Forge. CF keeps all project state in one `projects.json`, replaced atomically on every write; a tenant in the resident process watches that file, and when it changes, diffs each linked CF project against its last stored snapshot and records a new snapshot plus a change on 106's feed. A PM links an Amoeba project to a CF project by CF's project id through an inbox submission. This is the whole of the scope Amoeba took from CF initiative 220: the long-running process is 102's, notifications and subscriptions are 106's feed, and watching the file replaces CF-side event emission. *Rescoped 20260928:* previously deferred as a two-repository slice needing a CF daemon and an agreed wire contract; neither is needed.
   **Value:** Developer value — the Runner and subscribers learn that a phase, slice, or task pointer moved the moment any client moves it, and missed changes are impossible because the stored snapshot is the baseline every check compares against.
   **Success Criteria:**
   - A change to a linked CF project made by any CF client produces a stored snapshot and one feed change naming the fields that changed.
   - Changes made while the resident process is down are recorded on the first check after it starts.
   - Only linked projects are recorded; changes to other CF projects produce nothing.
   - An unreadable or unrecognized `projects.json`, or a linked project missing from it, is recorded as exactly that, never guessed around.
   - The `projects.json` fields Amoeba reads are documented as an observed shape.
   **Dependencies:** [101, 102, 103, 106]
   **Interfaces:** Consumes CF's `projects.json`; provides CF snapshots and `cf_project_changed` feed entries to 110 and initiative 120.
   **Risk Level:** Low
   **Relative Effort:** 2

9. [ ] **(109) Network API** — Added 20260928 by PM direction: Amoeba is not useful beyond one machine without a network surface. `amoeba serve` is its own process, separate from the resident process, exposing three things over the network: read-only store queries (the same reads `amoeba inspect` makes), submission to the inbox (the only write, so the sole-writer model is unchanged), and the change feed as a live stream that a client resumes from its last `seq`. This is where push reaches remote subscribers; local followers keep 106's polling. Binds to localhost by default; any other bind requires authentication. Protocol, authentication scheme, and endpoint shape are decided at slice design.
   **Value:** Architectural enablement — the notification bridge, Cowork, a status UI, and remote agents can use Amoeba without filesystem access to the supervisor's machine, which initiative 160 needs.
   **Success Criteria:**
   - A remote client can read nodes, blocked states, verdicts, and findings, and gets the same answers as `amoeba inspect`.
   - A remote client can submit to the inbox, and the submission is applied exactly as a local one is, including while the resident process is stopped.
   - A remote client following the feed receives each change once, in order, and resumes after a disconnect from its last `seq` with no gap and no repeat.
   - No endpoint mutates the store except by submitting to the inbox.
   - The server refuses to bind off localhost without authentication configured, and unauthenticated requests to a non-local bind are rejected.
   - Killing the server leaves the resident process and the store unaffected; killing the resident process leaves the server serving reads and accepting submissions.
   **Dependencies:** [101, 102, 103, 104, 106]
   **Interfaces:** Provides the network surface consumed by initiative 160, the notification bridge, and Cowork; consumes the read contract (101–104), the inbox (103), and the feed (106).
   **Risk Level:** Medium — first network exposure; authentication and the stream's resume semantics are the parts to get right.
   **Relative Effort:** 3

## Integration Work

10. [ ] **(110) Contract Proof and Hardening** — Prove the contract from the outside before initiative 120 commits to it. An end-to-end exercise driving a realistic lifecycle sequence through the substrate — nodes created, a Squadron run journaled and its verdict ingested, a blocked-state written and resolved through the inbox, a restart mid-sequence, subscribers observing the whole thing — using only the documented API, no internal access. Verifies store-locality behavior end to end against the model settled in slice 101 (per-supervisor, central, project-keyed) — the locality *decision* is closed there, and what remains here is proving path resolution and project-keying hold under a realistic sequence. Also closes out the pruning policy for paused Squadron runs that SQ never prunes, and documentation for downstream initiative authors.
   **Value:** Developer value — the contract is demonstrated to work for its actual consumer rather than assumed to. This is the point at which initiative 120 can safely begin.
   **Success Criteria:**
   - A full lifecycle sequence runs through the public API with no internal access.
   - A restart injected mid-sequence leaves the sequence completable and the final state correct.
   - Store locality behaves correctly for the chosen model and is documented.
   - Pruning policy for paused SQ runs is implemented and documented.
   - Contract documentation is sufficient for initiative 120's slice design to proceed against it.
   **Dependencies:** [101, 102, 103, 104, 105, 106, 107, 108, 109] — 108 added 20260928 when it was scheduled before this slice. 109 added 20260928 so the contract is proven through the network surface as well as locally.
   **Interfaces:** Consumes the full public contract; produces the documentation initiatives 120/140/160 design against.
   **Risk Level:** Low
   **Relative Effort:** 3

## Implementation Order

`101 → 102 → 103 → 104 → 105 → 106 → 107 → 108 → 109 → 110`, which is also numeric order. 105 (parser) was split from 104 on 20260926 and precedes 106 because 106 ingests reviews through its parser. 107 was split from 104 the same day. 108 was rescoped on 20260928 to need no Context Forge change; it follows 107 so that 107's already-designed migration number (007) stands, and it takes 008. 109 was added on 20260928; it needs 106's feed, adds no migration, and precedes 110 so the proof runs through the network surface too. 110 is last so the contract proof covers everything.

Rationale, in the guide's order of precedence:

- **Dependencies.** 101 is foundation for everything. 102 needs only 101. 103 needs the process it appends into.
- **Testability.** 101 + 102 + 103 is the earliest point at which a vertical path exists: something outside the process submits, the process applies it, state persists, and a restart preserves it. That is the substrate's core claim, provable before any evidence-layer work.
- **Risk.** 102 is the highest-risk slice in the sequenced set (crash recovery) and is placed second so its problems surface early rather than after four slices depend on it.
- **Enablement.** 104 unblocks initiative 140's consensus work; 103 unblocks 160. Both land before the integration slice.
- **Value.** 110 is where the contract stops being a claim and becomes demonstrated, which is the gate initiative 120 actually needs.

## Notes

- Finding normalization (slice 104) has an open question with the Squadron team: whether slice 305's `findings_addressed/screens.py` contains a canonical normalization worth reusing. If it does not, Amoeba defines its own and accepts that "same finding, reworded" is a judgment question for initiative 140 rather than a store question.
- Slices 104 and 106 both depend on Squadron output shapes that change without semver. Both record the upstream version they parsed, per the arch doc's schema-versioning consideration.
- No migration or refactoring slices exist — Amoeba is greenfield. If the substrate is later extracted into a peer package (the deferred half of OQ6), that extraction is a migration slice added here at that time.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Peer-primitive extraction** — If Squadron, Context Forge, or Cowork ever consume the store directly, extract it from Amoeba into a versioned package. Deferred half of the OQ6 decision; requires a second consumer to justify the repository and compatibility contract.
2. [ ] **Squadron review-completed event (S8) adoption** — Replace slice 106's filesystem detection with a real upstream event if Squadron adds one. Subscriber contract is designed to make this a swap.
3. [ ] **Caller-supplied Squadron run id (S9) adoption** — Replace slice 102's match-by-attributes reconciliation with exact run-id matching if Squadron exposes `--run-id` or emits the id at launch.
4. [ ] **Multi-project supervision surface** — The node model is project-keyed from slice 101, so running several lifecycle trees at once is a quantity change. The supervision view over a forest of runnable/blocked/done nodes is not built here.
5. [ ] **Store compaction and retention** — History grows without bound. Retention policy for resolved nodes, superseded verdicts, and applied journal entries is deferred until there is real data volume to measure.
