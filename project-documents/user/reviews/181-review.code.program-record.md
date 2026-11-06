---
docType: review
layer: project
reviewType: code
slice: program-record
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/181-slice.program-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261105
dateUpdated: 20261105
reviewedSha: d4fc3082bb2356af09f7c68b037abab118a0c014
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 362506
cachedTokens: 16579
cacheWriteTokens: 345923
completionTokens: 2873
durationSeconds: 31.4
costUsd: 1.484113
costBasis: provider
squadronVersion: 0.24.22
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "Member store is opened and read twice per member in `program-blocked`"
    location: "src/amoeba/inspection/program.py#program_blocked_rows"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Reserved hook and enum member with no behavior"
    location: "src/amoeba/store/_program_writer.py#_referenced_rejection"
  - id: F003
    severity: note
    category: consistency-rot
    summary: "Payload parsing is repeated between inbox and store"
    location: "src/amoeba/store/_program_specs.py"
  - id: F004
    severity: note
    category: consistency-rot
    summary: "Listing row carries a key that is not a declared column"
    location: "src/amoeba/inspection/program.py:122"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "Broad catches log and re-raise or follow existing precedent"
    location: "src/amoeba/process/project_stores.py#open_program_store"
  - id: F006
    severity: pass
    category: test-debt
    summary: "Locality, write-path and read-only guarantees are enforced mechanically"
    location: "tests/test_writer_guard.py"
---

# Review: code — slice 181

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Member store is opened and read twice per member in `program-blocked`

For each member, `_member_node_rows` opens the member's store read-only and reads its blocked nodes. `_unreadable_reason` then calls `read_member`, which opens the same store again. The member's state can change between the two reads, so a node row and an unreadable row can disagree. The docstring on `_member_node_rows` admits the split, saying it leaves the open failure to `read_member`. The same pairing means `program_rows` also depends on `read_member` alone. Consider having `read_member` return, or accept, the opened store, or computing the member's state once per member and passing it to both steps.

### [CONCERN] Reserved hook and enum member with no behavior

`_referenced_rejection` always returns `None`, and its body is `del program_id, dropped`. `ProgramRejection.MEMBER_REFERENCED` is never produced. The project's guidance is to resist adding complexity that isn't needed yet. Slices 183 and 184 can add the check and the enum member when the edges and requests tables exist. If you keep it, nothing mechanical pins the reserved value to the schema or to a test.

### [NOTE] Payload parsing is repeated between inbox and store

The inbox's Pydantic models already validate the payload. The store then re-parses it by hand with `cast` calls and `_field`, so the shape rules live in two places. This follows from `amoeba.store` not importing `amoeba.inbox`. The test that pins the field-name constants to the models limits the drift. The re-parse also gives the apply path its own `ValueError` guard.

### [NOTE] Listing row carries a key that is not a declared column

`program_submission_rows` emits `"payload"`, but `PROGRAM_SUBMISSION_COLUMNS` does not list it. `inbox.py:41` and `inbox.py:79` do the same, so this is consistent with existing listings.

### [NOTE] Broad catches log and re-raise or follow existing precedent

`open_program_store` catches `Exception`, logs it with `logger.exception`, and re-raises as `StartupFailedError`, which satisfies the exception-handling rule. The new `close_all` branch swallows close errors after logging them, the same as the project-store loop above it. I'd keep both unchanged.

### [PASS] Locality, write-path and read-only guarantees are enforced mechanically

The writer guard now covers `ProgramStore.open`. The oracle checks that program and project tables stay separate. Schema tests pin the enums and the initiative range to the SQL `CHECK` constraints. `read_member` and the program stage have per-reason, precedence and no-write tests. The load tests cover the program inbox's apply path and the tick's program read, with measured bounds documented. That meets the load-test requirement for the concurrency paths this slice touches.

### Run Digest

- Response length: 3591 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 362506 / 16579 / 345923 / 2873 / not computed
- Duration: 31.4 s
- Cost: $1.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
