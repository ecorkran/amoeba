---
docType: review
layer: project
reviewType: slice
slice: context-forge-event-seam
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.context-forge-event-seam.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: c3c714fb756e474f991eabe40cb2fe793b68fd4f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 173989
cachedTokens: 88194
cacheWriteTokens: 85789
completionTokens: 4949
durationSeconds: 41.9
costUsd: 0.402144
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Fulfils the architecture's CF event-seam commitment without touching CF"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Overview"
  - id: F002
    severity: pass
    category: boundaries
    summary: "Layering and dependency directions are correct"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Component Structure"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with explicit handling"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Technical Decisions (D4)"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs; name what to cut or defer"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Technical Scope"
  - id: F005
    severity: note
    category: open-decision
    summary: "D7 is a pending decision that affects the default behavior"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Technical Decisions (D7)"
  - id: F006
    severity: note
    category: architecture-drift
    summary: "Architecture's Current State is stale relative to the observed CF shape"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md#Current State"
  - id: F007
    severity: note
    category: error-handling
    summary: "\"Push, not poll\" is met by file watching, and one transient-failure assumption is stated only implicitly"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Technical Decisions (D1, D4)"
---

# Review: slice — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Fulfils the architecture's CF event-seam commitment without touching CF

The slice does what the architecture's "CF 220 ownership" paragraph says. It watches `projects.json`, diffs it against a stored snapshot, and emits a feed change, with no CF change, no wire protocol, and no polling of `cf next`. The snapshot is stored "with provenance" as the "Reference, don't duplicate" principle requires. It carries `cf_updated_at`, `cf_version_label`, and `observed_at`. It is a projection of CF's pointers, not a competing source of truth. The slice also never writes to `projects.json`, which matches the "state is the interface" goal. The visible success criteria in the slice plan entry for 108 are all covered: only linked projects are recorded, down-time changes are caught, and unreadable, unrecognized, and missing cases are recorded explicitly.

### [PASS] Layering and dependency directions are correct

The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`. It holds the projection as opaque JSON. Only the tenant knows both the parser and the store. The link is written through the inbox and the snapshots only by the resident process, so the sole-writer model holds. Interpreting a change is explicitly left to the Runner (120). That respects "no intelligence in the substrate".

### [PASS] Failure modes are enumerated with explicit handling

D4 gives a table covering absent file, permission error, invalid JSON, wrong top-level type, duplicate ids, wrong-typed projected fields, and missing project. Each case has an outcome and a scope. Rows are written on transitions only, so a file that stays broken doesn't flood the feed. Store exceptions are logged and re-raised, per 106. The stalled-mount hang is acknowledged and delegated to 102's standing remedy. No "TBD" appears in the failure handling. The architecture states no numeric NFR for this path, and the slice's own 1-second scan interval is stated.

### [CONCERN] Design is heavier than the slice needs; name what to cut or defer

The slice is rated Effort 2 and described as "one small tenant", but it carries these pieces:
- **Link activation toggle (D5).** The `active` flag adds deactivation and reactivation-baseline semantics, plus two Functional Requirements. The slice plan success criteria I could see ask only that linked projects are recorded and others are not. Link-only, with removal deferred until someone needs it, would drop a column, a payload field, a tick filter, and a test group. If the PM wants the toggle, the design should say which requirement needs it.
- **Listing filters.** `--cf-project-id` and `--outcome` on `inspect cf-snapshots`, plus a computed `last_outcome` and `last_observed_at` on `cf-links`. Nothing in the plan or the architecture consumes these. Defer the filters, since `--project` and `--json` already give the full data.
- **Settings.** `cf_scan_interval_seconds` and its CLI flag. D1 fixes the interval at 1.0, and nothing needs a different value. The injected clock already covers tests. A constant would do until a real need appears.
- **Documentation.** Updates to five contract docs plus a new one, in one slice. Restate only the deltas, and avoid re-describing 106's trigger convention or 102's process semantics.
- **Per-field type strictness (D4 rows 4 and 5).** Duplicate worktree ids, worktrees without ids, and wrong-typed projected fields each get an `unrecognized` outcome with a detail. Only the row that decides whether the linked entry can be parsed is clearly needed. The rest are cases the real file does not exhibit.

None of this conflicts with the architecture. The concern is effort and review surface, and dropping the items above would not remove any scope the plan assigns to 108.

### [NOTE] D7 is a pending decision that affects the default behavior

D7 is marked "needs PM confirmation". It decides that Amoeba ignores `CONTEXT_FORGE_DATA_DIR`, so a PM who relies on that variable and omits the flag will see `unreadable` or `missing`. That is visible, not silent, which fits "unknown is a value". The decision should still be confirmed before task breakdown, because the Verification Walkthrough and the end-to-end test both assume it.

### [NOTE] Architecture's Current State is stale relative to the observed CF shape

The architecture describes CF 0.14.x with project-level pointers only. The slice records CF 0.19.11, where the live pointers sit on worktrees, and its projection reads both levels. The slice flags this itself. The architecture's Current State should get a dated update, or point to `context-forge-contract.md`, so downstream initiatives (120, 160) don't design against the older shape.

### [NOTE] "Push, not poll" is met by file watching, and one transient-failure assumption is stated only implicitly

The architecture lists "Push, not poll" as a goal and also endorses watching `projects.json`, so a 1-second stat loop is acceptable. The slice would be clearer if it said that this is poll-by-stat of one file and not `cf next`. Two points are implicit and worth one sentence each:
- **Stat-then-read race.** A file replaced between the `stat` and the read is safe, because the remembered signature predates the read and the next tick rechecks. The doc doesn't say so.
- **In-place edits.** D4 says a non-JSON file "is a real finding, not a race", because CF renames atomically. A hand-edit or another tool that writes in place can produce a transient truncated file. That would put an `unrecognized` row and then an `observed` row with `changed: []` on the feed. State that this is accepted.

### Run Digest

- Response length: 6746 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 173989 / 88194 / 85789 / 4949 / not computed
- Duration: 41.9 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
