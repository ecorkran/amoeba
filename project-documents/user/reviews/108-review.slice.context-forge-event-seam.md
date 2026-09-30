---
docType: review
layer: project
reviewType: slice
slice: context-forge-event-seam
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.context-forge-event-seam.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 55f4ecc6d61f6d677e089c037c54049e261ce3a6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Writer model, layering, and CF 220 ownership match the architecture"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md#Architecture"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with explicit handling"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:192-198"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Pseudocode contradicts the \"re-read only when the signature changes\" rule"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:114-134"
  - id: F004
    severity: concern
    category: provenance
    summary: "Version label is captured at start-up, so snapshot provenance can go stale"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:138"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Opaque CF id is used as a filesystem path component"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:198"
  - id: F006
    severity: concern
    category: scope
    summary: "Ignored keys are top-level only, but `worktrees` overlays may carry free text or churn"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:51,72,167-171"
  - id: F007
    severity: note
    category: nfr
    summary: "Idle-tick claim (\"one stat and no read\") ignores the per-tick store query"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:116-119,275"
  - id: F008
    severity: note
    category: error-handling
    summary: "Whole-file rejection on a duplicate or malformed id has a wide blast radius"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:223,270"
  - id: F009
    severity: note
    category: contract
    summary: "Feed payload details to pin down"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:186,242,312"
  - id: F010
    severity: note
    category: dependencies
    summary: "Migration ordering couples 108 to 107"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:59,64"
---

# Review: slice — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Writer model, layering, and CF 220 ownership match the architecture

The tenant lives in the resident process, and the only external write is the `watch_cf` inbox kind. The store never imports `amoeba.upstream`. Snapshots are "observed state with provenance", not a competing truth, and `projects.json` is only read, never written. This matches the arch's Writer model, Reference-don't-duplicate, and CF 220 ownership sections (arch lines 89 and 83). D2 (record snapshots, don't write nodes) and the gate-state exclusion keep the substrate free of decision logic, which is the same line 105 D4 drew.

### [PASS] Failure modes are enumerated with explicit handling

The design covers a missing file, an unrecognized file, a linked id that was never present, an id that vanished, and a store failure. Each has a named state, a log level, a recovery trigger, and a bounded-failure path reusing 106's sidecar. Nothing is left as TBD. The arch states no numeric NFR for this path. The slice restates the 2s scan interval and the idle-tick cost as its own targets.

### [CONCERN] Pseudocode contradicts the "re-read only when the signature changes" rule

The `ProjectsFileUnrecognized` branch returns at line 122, before `last_sig = sig` is set at line 123. As written, an unrecognized file is re-read and re-parsed every tick. That contradicts line 195 ("Retried only when the signature changes") and the success criterion at line 270. The `sig = stat(...)` line also has no defined behavior when the file is missing. Set `last_sig` on the unrecognized path (safe, because a changed signature or a new watch still forces a read). Make the missing-file `stat` failure an explicit branch to `unreachable`.

### [CONCERN] Version label is captured at start-up, so snapshot provenance can go stale

The arch requires "Provenance on every ingested fact" and "Every ingested record stores the upstream version it was parsed from". Snapshots get the `cf --version` label from process start. If CF is upgraded while the process runs, which is likely for a resident process, later snapshots carry the old label. That is wrong in exactly the case the label exists for, since CF's wire values have changed between versions. The design should either re-capture the label when the file signature changes (one subprocess, not per tick) or record the label as "as of process start". The `unavailable` marker case should also be stated in the snapshot contract.

### [CONCERN] Opaque CF id is used as a filesystem path component

D3 says the id is an opaque string whose format is not parsed, and the `watch_cf` payload only requires it to be non-empty. Line 198 then puts it into a path: `{store_dir}/cf/attempts/{project_id}/{cf_project_id}.attempts.json`. An id containing `/`, `..`, or other path-special characters escapes the directory or fails to write. That would break the bounded-failure path itself. Fix it by keying the sidecar on a hash or encoded form of the id, or by validating the id at submit time. Either way, state it in the design.

### [CONCERN] Ignored keys are top-level only, but `worktrees` overlays may carry free text or churn

`customData` and `updatedAt` are excluded to keep noise and pasted summaries out of the store. The `worktrees` overlays are stored whole and compared as a whole. The doc describes them only as carrying `developmentPhase`, `activeSlice`, `activeTaskFile` "and so on". If an overlay carries its own `customData` or timestamps, the design stores the free text it meant to exclude. It would also record noise snapshots, which breaks the "only updatedAt or customData moved records nothing" criterion. The observed-shape section should list the overlay keys for CF 0.18.0. Then either apply `IGNORED_KEYS` recursively into overlays or state why it isn't needed.

### [NOTE] Idle-tick claim ("one stat and no read") ignores the per-tick store query

The first gate is "no active watch in any open project", and detecting a "new watch" also needs store state. Both require a query against each open project store every tick. This is cheap SQLite, but the success criterion should say "one stat, no file read" or cache watch state in memory.

### [NOTE] Whole-file rejection on a duplicate or malformed id has a wide blast radius

One entry without a string `id`, or one duplicate `id`, in an unlinked project blinds every watch. Line 72 notes that older records carry retired keys, so a legacy oddity is plausible. The choice to refuse to guess is defensible and visible through `unrecognized`. Consider failing only when the bad entry is a linked id, or record the trade-off explicitly.

### [NOTE] Feed payload details to pin down

- The trigger's `json_object('present', new.present)` yields `1`/`0`, but the walkthrough and payload table show `true`/`false`. Confirm 106's convention for booleans.
- The synthetic `"present"` entry in `changed` shares a namespace with CF's own keys. If CF ever adds a `present` field, the two are indistinguishable. A reserved marker would avoid this.

### [NOTE] Migration ordering couples 108 to 107

The slice takes migration 008 on the assumption that 107's 007 lands first, yet it lists 107 as "not needed". The ordering is stated openly and is fine. If the slice order changes, the migration numbers will need renumbering, so keep that visible in the slice plan.

### Run Digest

- Response length: 6687 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
