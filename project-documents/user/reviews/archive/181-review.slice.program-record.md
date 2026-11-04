---
docType: review
layer: project
reviewType: slice
slice: program-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/181-slice.program-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: b5366e905d19999c67ddae8e993fc7eda9fac52f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 112952
cachedTokens: 11162
cacheWriteTokens: 101786
completionTokens: 6666
durationSeconds: 57.2
costUsd: 0.475768
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's layering, dependency direction and the unreadable-member rule"
    location: "project-documents/user/slices/181-slice.program-record.md#Architecture"
  - id: F002
    severity: concern
    category: failure-modes
    summary: "The stated remedy for a wrong registration does not work, and \"outside Amoeba's API\" breaks the sole-writer rule"
    location: "project-documents/user/slices/181-slice.program-record.md#D10 — What is deferred"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Proportionality: the slice carries five refactors of shared foundations plus a new subsystem at \"Relative Effort: 3\""
    location: "project-documents/user/slices/181-slice.program-record.md#Implementation Notes"
  - id: F004
    severity: concern
    category: integration
    summary: "Prepending a `queue` column to the existing `inbox` listing changes a published listing"
    location: "project-documents/user/slices/181-slice.program-record.md#D8 — Inspection"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "The architecture contradicts itself on program-store failure, and the slice resolves it in favor of the explicit rule"
    location: "project-documents/user/slices/181-slice.program-record.md#D7 — The program stage"
  - id: F006
    severity: note
    category: scope
    summary: "One-program-per-project is a design decision the architecture does not make"
    location: "project-documents/user/slices/181-slice.program-record.md#D3 — Two bodies, both upserts that never remove; one program per project"
  - id: F007
    severity: note
    category: under-specification
    summary: "Unresolved shorthand references in the design"
    location: "project-documents/user/slices/181-slice.program-record.md#D5"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated"
    location: "project-documents/user/slices/181-slice.program-record.md#Data Flow"
---

# Review: slice — slice 181

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture's layering, dependency direction and the unreadable-member rule

The design matches the architecture on the points that matter for this slice:
- Coordination stays in the Runner's tick, with no new tenant or process.
- The program stage sits after intents and resolutions and before readiness.
- The program store lives in its own subdirectory, so it cannot collide with a project store.
- `amoeba.program` imports only `amoeba.store` and `amoeba.upstream`, so `inspection` does not import `amoeba.runner`.
- A member that cannot be read is a blocked-list reason, not a process failure (D6). Only the program store's own failure exits the process (D7).
- 181 stays read-only and consumer-first, as the slice plan's "behavior between slices" note requires.
- D4 moves the requests initiative index into the member registration. The architecture's "Request slices live in one requests initiative" principle already says this, and so does the slice plan's 181 entry, so the amendment is already reflected in the parents.

### [CONCERN] The stated remedy for a wrong registration does not work, and "outside Amoeba's API" breaks the sole-writer rule

D3 makes both bodies upserts that never remove. D10 then says a wrong registration "is corrected by re-registering; a project that must leave is a PM action outside Amoeba's API".
- **Re-registering cannot remove a member.** A typo in a member `project_id` (a member "need not have a store yet") stays in `program_members` permanently. `UNIQUE(project_id)` keeps it there. It shows as `store_missing` on `program-blocked` forever.
- **The fallback breaks the architecture's writer model.** State Management says "Nothing outside the process opens it read-write", and D9 makes the resident process the only read-write opener. Hand-editing the SQLite file contradicts that, so the escape hatch is not a real one.
- **Why this matters now.** 181 is the only slice where removal is safe, because no edges or requests reference members yet. The deferral only makes sense once 183 and 184 add references.

Pick one of these:
- Make `register_program` replace the member and override set while the program has no dependents. That is trivially true until 183.
- Check that a member has a store at registration, or reject on a typo-class error.
- Admit that 181 ships with no recovery path for a wrong member id, and say so in D10.

### [CONCERN] Proportionality: the slice carries five refactors of shared foundations plus a new subsystem at "Relative Effort: 3"

The slice plan entry for 181 is effort 3. The design adds six work steps on top of the plan's scope:
- parameterizing `migrations.py`
- lifting the connection helpers
- extracting `inbox_drain.py`
- moving `resolve_checkout`
- moving the path rule
- changing the locality proof

The Risk Assessment itself says a regression in these refactors "breaks everything". The mitigation (pure refactors committed on their own) is sound, but the effort figure and the plan are not updated to match.

Candidates to cut or defer:
- **Path-rule move.** `validate_repo_relative_path` could stay in `project_config` and be imported, or be duplicated for one caller, until 182 needs it. Only `concept_path` validation in `register_program` uses it.
- **`links_ambiguous` as a separate vocabulary entry.** It could fold into `unlinked` with a detail string. The slice plan lists only unlinked, store, snapshot and checkout.
- **`ProgramView` held on the tick.** Nothing reads it until 183. The stage could return only a boolean or the program id for now.

At a minimum, re-state the effort (the real size is closer to 4–5) in the slice plan, or split the foundation refactors into their own slice.

### [CONCERN] Prepending a `queue` column to the existing `inbox` listing changes a published listing

D8 makes `queue` the first column of `inbox`. The same slice says the server serves listings at `/v1/listings/{name}` from the registry, and 160 is a named downstream consumer of these listings. Consumers that read rows positionally, and every existing `inspect inbox` test, would break. The doc claims "No other listing changes" and "The project inbox is unchanged for submitters", but it never says that `inbox` consumers stay compatible.

Either append `queue` as the last column, or add a `program-inbox` listing and leave `inbox` untouched. If the change stays, state which consumers and tests change.

### [NOTE] The architecture contradicts itself on program-store failure, and the slice resolves it in favor of the explicit rule

The architecture's Design Goals say a project in no program "behaves exactly as it does after 140, whatever happens to any program". Its Technical Considerations also say a program store failure "is a store failure and exits the process". D7 handles this openly. It states that every project's tick reads the program store, so a corrupt program store stops projects in no program. It also states that the explicit failure rule wins.

That is a defensible reading, and the slice documents it. The "whatever happens" sentence in the architecture should be narrowed to match. The slice's own success criteria are consistent with D7.

### [NOTE] One-program-per-project is a design decision the architecture does not make

The architecture says only that both shapes are disjoint today. D3 turns that into a hard `UNIQUE(project_id)` constraint with a rejection code. The reasoning (a single "which program" lookup for every later slice) is sound. Because every later slice depends on it, record it in the architecture. Also record that moving a project between programs is deferred.

### [NOTE] Unresolved shorthand references in the design

D5 and D6 cite "(#25)" and "(#26)", and D4 cites "D10", without saying what those point to. No numbered items 25 or 26 exist in the slice plan or architecture. Replace each with the slice name or the decision it refers to, or drop it.

### [PASS] Failure modes for the new I/O paths are enumerated

- **Program inbox:** validation failure is refused at submit and quarantined when hand-written. A crash after commit and before delete is a no-op through first-wins on the submission id. A store failure is counted beside the file, stops the process below `inbox_max_attempts`, and parks the file at the limit.
- **Store creation:** atomic build-under-`.creating`-then-rename.
- **Member reads:** each failure maps to a closed reason with a specific-exception catch (D6), and the busy-timeout bound is stated.
- **Program store failure:** at the stage or at the tenant, it exits as a store failure. At start it is `STARTUP_FAILED`.
- **Verification:** the walkthrough exercises each of these paths.

No architecture NFR applies to these paths, so none needs restating.

### Run Digest

- Response length: 7736 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 112952 / 11162 / 101786 / 6666 / not computed
- Duration: 57.2 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
