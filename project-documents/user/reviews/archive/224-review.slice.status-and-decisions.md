---
docType: review
layer: project
reviewType: slice
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/224-slice.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: b501ad750daffc45a6d5a921bba5302818ad64ff
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 512510
cachedTokens: 401002
cacheWriteTokens: 111496
completionTokens: 6099
durationSeconds: 52.7
costUsd: 0.547939
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Read-don't-mirror and layer boundaries hold"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Architecture"
  - id: F002
    severity: concern
    category: scope-deferral
    summary: "Slice-state scope from the plan entry is dropped"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Technical Scope (Excluded)"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "`wrong_checkout` is write-side scope inside a read-side slice, and it depends on #303 landing"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D9"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Two enforcement mechanisms in the schema test where one meets the requirement"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D10"
  - id: F005
    severity: concern
    category: failure-modes
    summary: "`project_of` call count scales with Amoeba's own answering runs, and the design says it is a \"handful\""
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D4, #Special Considerations"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D1, #D4, #D6, #D7"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "\"Never dropped\" and the one-definition design match the architecture"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D3, #D4"
  - id: F008
    severity: note
    category: external-dependency
    summary: "Slice completion is gated on an external change that 225 does not otherwise need"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D1 (What waits on #303)"
  - id: F009
    severity: note
    category: consistency
    summary: "`status` and `decisions` scope defaults differ on purpose"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D2, #D5"
---

# Review: slice — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Read-don't-mirror and layer boundaries hold

Run state, checkpoint kind and working directory are read from Squadron on each call. Member names are read from Context Forge on each call. The only write is `pm_marker.last_seen_seq`. D10 turns "nothing mirrored" into a schema test, which the plan's success criteria require. The import direction (`cli → operations → store, config, upstream`) matches 222. `status` reads the store first and runs no subprocess inside a transaction. The `status`, `decisions` and `mark_read` rows of the architecture's operations table are matched, including the single marker across all programs.

### [CONCERN] Slice-state scope from the plan entry is dropped

The 224 plan entry assigns this slice "slice state from Context Forge, never copied into the store". The design excludes slice-state display and calls this "a deliberate change to the plan entry". The reasoning is sound: the architecture's `status` row lists no slice state, and neither 225 nor 226 consumes it. Dropping assigned scope is still a CONCERN under the review rules. The plan entry and the design now disagree, and nothing says the plan will be updated. Edit the plan entry in the same commit as this design so it drops the slice-state clause and keeps only the "never stored" rule that D10 enforces.

### [CONCERN] `wrong_checkout` is write-side scope inside a read-side slice, and it depends on #303 landing

The plan entry for 224 is "the read side". D9 changes `handle_pause`'s skip behavior, adds `SkipReason.wrong_checkout`, adds a new run-file schema version to `read_run_facts`, and edits `docs/squadron-hook.md`. None of this is needed by `status`, `decisions` or `mark_read`. All of it waits on #303's real output. 223 D3 deferred the check to #303, not to 224. Cut D9 from this slice and ship it as a small `feat:` after #303 lands. That removes the work from the critical path, and it takes about a third of the "waits on #303" tasks out of this slice's completion gate. The `classify_pause` extraction (D3) is justified, because `status` needs the shared definition. It does not need `wrong_checkout`.

### [CONCERN] Two enforcement mechanisms in the schema test where one meets the requirement

The plan requires "a test checks the schema". D10 pins a full `(table, column)` inventory with four reason categories mirrored in `docs/store-contract.md`. It also keeps a separate forbidden-names list of 11 suffixes. The pinned inventory already fails on any new column until a reviewer updates it, so the name list is redundant. The name list also checks by naming convention only, so a mirrored column named `state` or `phase` would slip past it. Keep the inventory with its reasons and drop the forbidden-names list, or keep the list and drop the four-reason documentation. Don't keep both.

### [CONCERN] `project_of` call count scales with Amoeba's own answering runs, and the design says it is a "handful"

Placement makes one `project_of` (a `cf get`) call per distinct run directory. Every answering run has its own scratch directory under `$AMOEBA_HOME/answering/<id>/`. 223 keeps these directories and never prunes them. Any answering run that is still resumable, meaning paused, failed or orphaned, appears in the default listing and takes a `cf` call that returns `CFProjectNotFound`. Special Considerations says this is "a handful of calls". It isn't, once answering runs accumulate. The calls run one after another, each bounded by the `cf` timeout, and one timeout aborts the whole `status` call (D4, exit 3). So an unrelated stuck answering run can make `status` fail. Skip directories under `answering_dir()` before any `cf` call, since Amoeba's own scratch space is never a member. This removes the calls and the failure path. Alternatively, state the bound and the behavior explicitly.

### [PASS] Failure modes for the new I/O paths are enumerated

Each new path has a stated outcome:
- **`sq runs list`:** timeout, non-zero exit, non-JSON output and missing fields are a `RunListProblem` raised as `SquadronError` (exit 3). An old Squadron without `--json` gets a message that names #303.
- **`cf` calls:** a failure raises `ContextForgeError` and never silently unplaces or hides a run.
- **Missing member name:** raises an error that names the member id.
- **Unreadable run file:** the run shows as `run_file_unreadable` and the others still list.
- **Concurrent `mark_read`:** `BEGIN IMMEDIATE` plus a `MAX` update gives a monotonic marker.

Every subprocess is bounded by an existing timeout value. No NFR with a numeric target in the architecture applies to this slice.

### [PASS] "Never dropped" and the one-definition design match the architecture

The principle "a question that can't be handled stays visible in `status` with the reason" is implemented. Every `waiting_on_pm` question is listed whatever state its run is in, and `moved_on` or `not_listed` questions carry no `next`. D3's cross-check test, which asserts that anything `status` calls a missed hook is something `handle_pause` will act on, directly addresses the architecture's "catching up" flow. `read_through` is null for narrowed or time-based listings. That stops an agent from marking unseen records read, and it fits the architecture's single-marker rule.

### [NOTE] Slice completion is gated on an external change that 225 does not otherwise need

The architecture and the slice plan list #303 as required for missed-hook catch-up and per-member run state, so the dependency itself is correct. The design handles it well: the code is written against the proposed shape, and a `BLOCKED:` line is added if #303 hasn't landed. The sequencing cost is that 225 depends on all of 224 and the trial only needs #302. Splitting off D9, as suggested above, helps. The PM may also want to let 225 start once `decisions` and `mark_read` are done and `status` is passing on fixtures. That would be a plan change, not something this design can decide.

### [NOTE] `status` and `decisions` scope defaults differ on purpose

`status` from inside a member narrows to that member's program. `decisions` from the same place does not narrow. D5 gives the reason, which is the single marker. The difference is documented, but an agent wrapper in 226 should carry the distinction in its tool descriptions so callers aren't surprised.

### Run Digest

- Response length: 7558 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 512510 / 401002 / 111496 / 6099 / not computed
- Duration: 52.7 s
- Cost: $0.55 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
