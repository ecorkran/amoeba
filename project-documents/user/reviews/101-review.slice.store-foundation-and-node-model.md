---
docType: review
layer: project
reviewType: slice
slice: store-foundation-and-node-model
project: amoeba
verdict: CONCERNS
sourceDocument: project-documents/user/slices/101-slice.store-foundation-and-node-model.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 82a5952698bb849fa1269492c3a17cbe0d0ba83d
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Scope boundaries match the slice plan's decomposition"
    location: "project-documents/user/slices/101-slice.store-foundation-and-node-model.md:40-48"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Writer-model deferral is explicit, not a hidden gap"
    location: "project-documents/user/slices/101-slice.store-foundation-and-node-model.md:102-104"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "Store-locality decision preempts scope the slice plan assigns to slice 110"
    location: "project-documents/user/slices/101-slice.store-foundation-and-node-model.md:126-132"
  - id: F004
    severity: concern
    category: error-handling
    summary: "No failure-mode enumeration for the slice's own new I/O path"
    location: "project-documents/user/slices/101-slice.store-foundation-and-node-model.md:100-107"
  - id: F005
    severity: note
    category: consistency
    summary: "`interfaces` frontmatter field lists downstream consumers, not required interfaces"
    location: "project-documents/user/slices/101-slice.store-foundation-and-node-model.md:7"
---

# Review: slice — slice 101

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Scope boundaries match the slice plan's decomposition

The "Explicitly excluded" list (command journal/process → 102, inbox → 103, findings/verdicts → 104, change feed → 106, pruning → 110) maps exactly onto the slice plan's per-slice ownership in `100-slices.substrate-run-state-store.md`, and the "Provides to Other Slices" section correctly mirrors each downstream slice's stated `Interfaces`/`Dependencies` fields (102 consumes the store API and inspection schema, 103 consumes the write API and resolution-slot operation, 104 consumes the migration mechanism and reference fields, 106 consumes status transitions, 110 consumes the public API only).

### [PASS] Writer-model deferral is explicit, not a hidden gap

The architecture (100-arch.substrate-run-state-store.md:83) makes the resident process the sole writer, but that process doesn't exist until slice 102. Rather than silently ignoring this or prematurely building enforcement, the slice states outright that single-writer discipline is caller-owned here and enforcement is 102's job — avoiding both scope creep and a hidden assumption.

### [CONCERN] Store-locality decision preempts scope the slice plan assigns to slice 110

The slice plan (`100-slices.substrate-run-state-store.md:105`) lists "closes out store-locality behavior (per-project versus per-supervisor)" as deliverable scope for slice 110 — consistent with the architecture's own framing that this is a "slice design decides" question left open (100-arch...md:103). This slice design instead makes and closes that decision now ("Decision (PM, 2026-09-14): one store per supervisor at a central path... the design commitment is central-and-project-keyed"), leaving only path-resolution mechanics open. If intentional, the slice plan (110's entry) should be updated to reflect that the fundamental locality decision moved to 101, or slice 110's author will expect to still be deciding it. As written, the two planning documents disagree about which slice owns this decision.

### [CONCERN] No failure-mode enumeration for the slice's own new I/O path

This slice introduces the first I/O path in the repository — opening, reading, and writing the SQLite file — and the document is otherwise disciplined about explicit handling (e.g., "a store newer than the code is an error, not a silent downgrade," "an unmappable row raises"). But it never enumerates the local-I/O equivalents of hang/timeout/disconnect: SQLite lock contention (`SQLITE_BUSY`, since WAL only guarantees one concurrent writer and this slice does not enforce single-writer — a caller-side race is possible even inside this slice's own tests), disk-full during a commit, a corrupted database file on open, or a permission error on the store path. None of these are marked "TBD," they're simply absent, which is the implicit-gap pattern the review criteria calls out. A busy-timeout/retry policy (or an explicit statement that none is set and why) belongs in this slice's Technical Decisions or API Contract section rather than being left to be discovered in 102.

### [NOTE] `interfaces` frontmatter field lists downstream consumers, not required interfaces

Frontmatter sets `interfaces: [102, 103, 104, 106, 110]`, but the body states "Interfaces Required: None from other slices" and the listed slices are all consumers of this one (102-110 depend on 101, not the reverse). If the project's frontmatter schema intends `interfaces` to mean "interfaces required from other slices" (as slice-plan entries for 102-110 use it), this list is backwards; if it's meant to mean "related/interfacing slices" regardless of direction, it's fine. Worth confirming against the schema convention since it reads ambiguously as-is.
