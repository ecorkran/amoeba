---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: bfdc52b46eb603ad59837542cc3201017c382925
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 41.7
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Group A covers the LLD Migration Plan and Technical Requirements with byte-comparison proof"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:62-347"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Test-with pattern and commit cadence are sound"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:29"
  - id: F003
    severity: pass
    category: nfr-coverage
    summary: "Load tier and CI gating are handled"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:21"
  - id: F004
    severity: concern
    category: task-scoping
    summary: "Gate task 1.1 bundles too many independent activities and has a hard stop mid-task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:39-58"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "Group A tasks depend on module names that are unknown until Task 1.1 runs"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:141-199"
  - id: F006
    severity: concern
    category: task-scoping
    summary: "Task 2.9 is a six-part umbrella with an open-ended module count"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:275-294"
  - id: F007
    severity: concern
    category: sequencing
    summary: "Task 2.6 combines implementation with a transitional run_listing rework, and its commit depends on a later task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:218-236"
  - id: F008
    severity: concern
    category: task-scoping
    summary: "Task 3.5 (`query_from_params`) is not scoped to a single clear test boundary and lacks a commit-with-test pairing note"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:438-450"
  - id: F009
    severity: concern
    category: task-clarity
    summary: "Task 3.4 mixes the error table with HTTP-handler behavior; the exception mapping depends on 101–104 classes not yet read"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:404-420"
  - id: F010
    severity: concern
    category: coverage
    summary: "Success criterion \"change_head from the same snapshot\" and `max_listing_rows`/`store_busy` for project reads have no task in this file's section 3 range"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:33"
  - id: F011
    severity: note
    category: design-consistency
    summary: "Deviation from the LLD Component Structure is flagged"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:95"
  - id: F012
    severity: note
    category: sequencing
    summary: "Task 3.5a pulls the writer-guard and layering tests forward"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:454-471"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Group A covers the LLD Migration Plan and Technical Requirements with byte-comparison proof

Task 1.2 builds the byte-comparison baseline before any move. It covers every registry entry in both table and `--json` forms, and a missing baseline file fails the test. Tasks 2.1–2.5d relocate the modules unchanged. Tasks 2.6–2.10 then add `ListingQuery`, `abbreviated_columns` and `encode_rows`, converting one module per commit. Task 2.11 moves `change_as_json`. Task 2.10 adds the layering tests: no argparse or `amoeba.cli` under `inspection`, and `store` imports nothing from the new packages. Task 2.12 covers the `process-contract.md` update.

### [PASS] Test-with pattern and commit cadence are sound

Implementation tasks are followed immediately by their test tasks (2.6→2.7, 3.2→3.3, 3.4→3.4a, 3.6→3.7), and each pair is committed together. Commits are spread through the file, and in Group A each relocation commits only after the byte comparison. The lettered tasks (2.5a–d, 3.4a, 3.5a) are explicitly ordered. The `uses_query` temporary field in 2.6 is created and later removed in 2.10, which keeps every commit green.

### [PASS] Load tier and CI gating are handled

The slice's latency bound and concurrency bounds are covered. Task 8.1c in file 3 adds `tests/load/test_serve_streams.py`. The context summary states that `ci.yml` already runs `tests/load` as a separate gating step. Task 8.1c has the implementer confirm that no workflow change is needed. CI gating is therefore explicit rather than implicit.

### [CONCERN] Gate task 1.1 bundles too many independent activities and has a hard stop mid-task

Task 1.1 covers branch creation, a two-part gate across four slices, locating the durable-write routine, recording the 106 symbol names, collecting five PM rulings, and a baseline run. Several of its steps stop and ask the PM. Effort is rated 2, which understates the work. Consider splitting it into (a) branch and gate, (b) discovery notes, and (c) PM rulings and baseline. Task 1.1 also produces no artifact. The "notes" it asks for are referenced by 2.4–2.5c, 2.11 and 6.1, but no durable place for them is named. Have it write them to a notes file or a section of this task file, so later tasks don't depend on session memory.

### [CONCERN] Group A tasks depend on module names that are unknown until Task 1.1 runs

Tasks 2.4, 2.5a, 2.5b, 2.5c and 2.9c–f refer to "the module(s) named in Task 1.1" and "each 105/107/108 module". Their steps and success criteria cannot be checked until Task 1.1 runs. Their effort is 1 and they contain no concrete file lists. A junior can complete them, since the recipe is mechanical, but Task 2.5c's success criterion ("`ls src/amoeba/cli/inspect_*.py` shows only `inspect.py`") is the only objective end-state check. Add the same end-state check to 2.5a and 2.5b. For example: no `inspect_*` module for that slice remains and its listing names are still in `LISTINGS`.

### [CONCERN] Task 2.9 is a six-part umbrella with an open-ended module count

Task 2.9 is rated effort 4. It bundles sub-steps 2.9a–2.9f, with an unknown number of modules in 2.9d–f, each with its own commit. The sub-steps are independently verifiable and are ordered, but they are tracked as a single checkbox group. Promote them to separate tasks (2.9a–2.9f), as was done for 2.5. Then progress, commits and the byte comparison per module can be checked off individually. Sub-step 2.9b also embeds a non-trivial behavior move (the `args.json` key truncation to `abbreviated_columns`). It deserves its own success criterion, namely that table and `--json` output for `findings` and `changes` match the baseline.

### [CONCERN] Task 2.6 combines implementation with a transitional run_listing rework, and its commit depends on a later task

Task 2.6 adds `ListingQuery` and `build_query`, plus `query_from_namespace` in `cli/inspect.py`. It also adds the `uses_query` field to `Listing` and changes `run_listing` to branch on it. The `run_listing` change alters existing behavior paths (all `False` at that point), and its testing is only indirect, through the byte comparison. Task 2.7 tests only `ListingQuery` and `build_query`. Add an explicit check that `query_from_namespace` equals the expected query for each option type, or add that to 2.7. Without it, `query_from_namespace` is first exercised only when 2.8 flips the first listing.

### [CONCERN] Task 3.5 (`query_from_params`) is not scoped to a single clear test boundary and lacks a commit-with-test pairing note

Task 3.5 combines implementation and tests in one task, unlike the neighbouring pairs. That is acceptable for the size, but it does not follow the numbered implementation/test split used elsewhere. It also sits in the "Group B Skeleton" section although it belongs to `amoeba.inspection`, and it modifies `query.py` from Task 2.6. A note on whether the `LISTINGS` iteration test in 3.5 is redundant with the one in 2.7 would help. Also, the LLD says unknown parameters are `400 invalid_query`, but the task never ties `ListingQueryError` to that status. The link is made in the 3.4 exception table, so add a pointer to it.

### [CONCERN] Task 3.4 mixes the error table with HTTP-handler behavior; the exception mapping depends on 101–104 classes not yet read

Task 3.4 defines the code→status table, the exception→code table, headers, the body shape, and the Starlette handler with a 500 path. Effort is rated 3, which is on the high end for one task. It tells the implementer to "read the 101 `StoreError` hierarchy first and map each subclass explicitly". The mapping depends on classes whose names the task does not list (`StoreBusyError`, `InvalidSubmissionError`, `SubmissionWriteError`, `VerdictNotFoundError` are named; the schema-mismatch and unreadable-store subclasses are not). `unknown_project`, `listing_too_large`, `request_too_large`, `request_timeout`, `unknown_listing`, `unknown_submission`, `principal_mismatch`, `too_many_streams`, `auth_unavailable`, `unauthenticated` and `insufficient_scope` are raised directly as `ApiError`, not mapped from exceptions. This is correct but not stated. Add one line saying so, so a junior doesn't hunt for exceptions to map.

### [CONCERN] Success criterion "change_head from the same snapshot" and `max_listing_rows`/`store_busy` for project reads have no task in this file's section 3 range

Per the section map, the project listing endpoints are in Tasks 3.8–3.10 in file 2, so this is likely covered there. I did not verify it, since this file ends at 3.7. Confirm that file 2 includes `read_transaction()` for the `change_head` snapshot, `listing_too_large` and `store_busy`, along with the registry-wide parity test (server rows equal `amoeba inspect --json`). Task 3.7's reliance on `seed_all_listings` also means 3.7 cannot be fully verified until Task 1.2's helper holds the project data.

### [NOTE] Deviation from the LLD Component Structure is flagged

Task 2.1 puts the listing types in `inspection/types.py` rather than `registry.py`, to avoid an import cycle. It says to report this in Task 8.5. This is a sensible and well-justified deviation.

### [NOTE] Task 3.5a pulls the writer-guard and layering tests forward

Task 3.5a adds `amoeba/serve` to the writer-guard scan, and adds a no-`process`/`cli` import test from the first `serve` commit. This puts mechanical safeguards in place from the beginning. It is good sequencing, and it also introduces the `ENDPOINT_SCOPES` mechanism before `TokenAuth` (Task 6.3), which keeps scope enforcement from being bolted on later.

### Run Digest

- Response length: 9055 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 41.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
