---
docType: review
layer: project
reviewType: arch
slice: substrate-run-state-store
project: amoeba
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/100-arch.substrate-run-state-store.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: 8152b469dc3faff35a93348433098b11b555b410
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "CF 220 ownership status contradicts the parent initiative-plan document"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:27"
  - id: F002
    severity: concern
    category: completeness
    summary: "Crash-recovery reconciliation for command-before-result is unspecified"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:55"
  - id: F003
    severity: concern
    category: consistency
    summary: "Substrate's ownership of \"process exit\" detection conflicts with the stated Runner/substrate boundary"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:79"
  - id: F004
    severity: concern
    category: technology
    summary: "Storage-engine choice and the single-writer/multi-writer decision are treated as independent when they aren't"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:89"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Mitigation for Squadron's implicit-resume collision doesn't address where the race actually happens"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:97"
  - id: F006
    severity: note
    category: abstraction
    summary: "\"Three surfaces\" framing doesn't match the five-slice decomposition"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:73"
  - id: F007
    severity: note
    category: completeness
    summary: "Single-writer question is framed as fully open despite the doc's own component placement partially answering it"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md:91"
---

# Review: arch — slice 100

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] CF 220 ownership status contradicts the parent initiative-plan document

The architecture doc treats CF initiative 220 ownership as unresolved throughout: Scope says "pending CF-team confirmation" (line 27), and Technical Considerations devotes a bullet to "CF 220 ownership is unconfirmed... Confirm with CF team before CF starts 221" (line 87). But its own declared parent, `001-initiative-plan.amoeba.md:32`, states the opposite in the same 2026-09-13 revision: "**Scope added 2026-09-13 (PM):** absorbs... and (confirmed by PM 2026-09-13) CF initiative 220." One document says PM already confirmed; the other says confirmation is still outstanding and gates slice separability ("Slice planning must keep that half separable"). Since `002-upstream-delta.amoeba.md`'s own "Next steps" (line 145) also lists this as still-open ("confirm CF 220 ownership with the CF team"), the initiative-plan's "(confirmed by PM 2026-09-13)" wording looks like the stale/wrong one — but as written, a reader following `parent:` from this arch doc hits a direct contradiction on a load-bearing scope boundary (whether Amoeba builds the CF-side daemon or only consumes CF's). Per this project's own rule ("Do not guess or assume... ask the Project Manager"), this should be reconciled before slice planning rather than left as two documents asserting opposite states.

### [CONCERN] Crash-recovery reconciliation for command-before-result is unspecified

The "Command-before-result" principle (line 55) and the restart-survival claim (line 81: "any in-flight command is either recorded-and-unresolved (recoverable) or not-yet-recorded (never issued)") both stop short of saying what "recoverable" means for a side-effecting command. If the resident process crashes after issuing `sq run` (or a CF write) but before recording the result, the command is "recorded-and-unresolved" — but the doc never states whether recovery means re-issuing it (risking a duplicate side-effecting run, which line 55 explicitly says must never happen silently), querying the external system for actual outcome (implying a reconciliation contract with SQ/CF that doesn't otherwise appear anywhere in the doc), or something else. This is exactly the hard part the architecture is supposed to settle — "restart-survival... cost[s] a rewrite if it is wrong" (line 29) — and it's the one piece of the recovery story left as "recoverable" without a mechanism.

### [CONCERN] Substrate's ownership of "process exit" detection conflicts with the stated Runner/substrate boundary

Scope explicitly excludes "parsing of SQ JSON/frontmatter or CF MCP results (the Runner's control surface, initiative 120)" from the substrate (line 27), implying the Runner is the process that shells out to `sq`/`cf` and would naturally observe process exit directly. But Envisioned State (line 79) says the event seam "subscribes to... SQ run completion" and, since no completion event exists yet, "the seam owns the detector so the Runner never does" — and Current State (line 69) names "process exit" as one of the two detection signals. Detecting a subprocess's exit ordinarily requires being (or being told by) the process that spawned it. The doc doesn't specify how a component that explicitly does not own the CF/SQ control surface observes process exit without either duplicating part of that control surface or requiring the Runner to report exits to it (which would mean the Runner *is* involved in detection, contradicting "so the Runner never does"). This is under-specified at exactly the boundary the doc otherwise polices carefully (line 27's "does not own" list).

### [CONCERN] Storage-engine choice and the single-writer/multi-writer decision are treated as independent when they aren't

"Storage technology" (line 89) defers the engine to slice design, framing it as separable from the architectural commitment ("the contract, not the engine, is the architectural commitment"). "Concurrency and the single-writer question" (line 91) then presents two symmetric options — sole-writer-with-enqueue vs. store-arbitrates-concurrent-writers — as if either is equally available regardless of engine. But the only storage candidate actually named anywhere in the doc is SQLite (line 89, inherited from SQ 280's proposal, and the natural choice since Amoeba is Python per the concept doc). SQLite's writer model makes "the store arbitrates concurrent writers itself" materially harder (single active writer, `SQLITE_BUSY` under concurrent write pressure) than it would be with e.g. Postgres. If slice design defaults to SQLite for stack-consistency reasons, the multi-writer option isn't actually a peer choice to sole-writer — the doc should flag this coupling instead of implying the two decisions can be made independently at slice design.

### [CONCERN] Mitigation for Squadron's implicit-resume collision doesn't address where the race actually happens

"Squadron run lifecycle" (line 97) correctly identifies the hazard — "Implicit resume auto-detects a paused run for the same pipeline + params, so the store must know which paused runs it owns to avoid resuming the wrong one" — but the stated mitigation ("the store must know which paused runs it owns") can't prevent the collision: per `002-upstream-delta.amoeba.md` §9, implicit resume is resolved inside `sq run` itself, before Amoeba's store is ever consulted. The store knowing what it owns lets it *detect* after the fact that the wrong run was resumed, not *prevent* it. The actual fix — the Runner must always pass an explicit `--resume <run_id>` and never invoke `sq run` in a way that lets SQ's implicit-match kick in — isn't stated, even though the surrounding text (line 97) already names explicit resume as the resolution path for the store's own `blocked_on_sq_checkpoint` records.

### [NOTE] "Three surfaces" framing doesn't match the five-slice decomposition

Envisioned State says the substrate "exposes three surfaces" (line 73) and bundles the durable queue and the event seam together as surface #3 (line 79). Anticipated Slices then splits them into two independent slices — "Durable message queue" and "Event seam" (lines 114–115) — with different consumers, different delivery semantics (point-to-point intent/escalation vs. pub/sub state-change notification), and different upstream dependencies (CF/SQ events vs. internal actors). The grouping in the overview undersells that these are two distinct mechanisms sharing a section number; worth renumbering or explicitly noting the split so a reader doesn't expect one contract where the slice plan delivers two.

### [NOTE] Single-writer question is framed as fully open despite the doc's own component placement partially answering it

Technical Considerations presents "sole writer vs. store arbitrates" as an open question for slice design (line 91). But Envisioned State has already established an asymmetric topology: "The Runner (120) runs inside the resident process... The Judge (140) and Translator (160) attach through the same contract from outside the process" (line 81). That placement already constrains the answer — an in-process Runner can write directly under a sole-writer model, while out-of-process Judge/Translator would need to enqueue regardless of which option is chosen for them. The doc would be stronger if it connected this existing decision to the "open" question rather than presenting the two as unrelated.
