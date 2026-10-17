---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: ea7825b57979f2aad8bd2b6679a9d958035e1260
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 366367
cachedTokens: 270025
cacheWriteTokens: 96332
completionTokens: 6163
durationSeconds: 57.8
costUsd: 0.474647
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Migration and snapshot criteria are covered and gated"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:291-307"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Open item for the PM blocks the whole slice, but only affects Task 8.1"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:43,66"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 2.8 is a likely no-op and is too granular"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:30,275-287"
  - id: F004
    severity: concern
    category: ci-gating
    summary: "CI gating of the new load tier is implicit"
    location: ".github/workflows/ci.yml:53-54"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Tasks 2.5 and 2.6 form a large red-suite window"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:204-253"
  - id: F006
    severity: note
    category: scope
    summary: "Task-level additions go beyond the design but are justified"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:45-49"
  - id: F007
    severity: note
    category: proportionality
    summary: "Step detail is heavy but mostly traceable"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:105-108,317-321"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Migration and snapshot criteria are covered and gated

- **Byte-identical migration:** Task 1.3 captures the baseline once and generates the commands from `LISTINGS`. Task 2.9 diffs the output, including `--help`, before any server code lands. This matches the slice's Technical Requirements, first bullet, and "Behavior preserved".
- **Snapshot consistency:** Tasks 3.1–3.4 cover `read_transaction()`, `change_head()` and `as_of_seq`. Task 3.4's mid-read commit test maps directly to the functional requirement on one snapshot.
- **Layering and the writer guard:** Task 2.7 adds the inspection layering rule, and the writer-guard check runs with no allow-list change.

### [CONCERN] Open item for the PM blocks the whole slice, but only affects Task 8.1

- The `ServeRefusedError` mapping question is stated as gating Task 1.1. Task 1.1 step 3 tells the junior to stop and wait for the PM, even though nothing before Task 8.1 depends on the answer.
- Move the gate to Task 8.1, or to the start of Section 8. Sections 1–7 can then proceed while the PM decides.
- The task file also departs from the slice design without a fix to the design. The design says the error is "mapped … in `cli/main.py`", and the tasks assume `cli/serve.py`'s `run_serve` maps it. Once the PM answers, add a step to correct the slice design, or record the delta in Task 9.3. Otherwise the two documents keep contradicting each other.

### [CONCERN] Task 2.8 is a likely no-op and is too granular

- The Context Summary already records that no contract doc references the moved module paths (grep, 20261017). Task 2.8 then asks for the same grep, with a "none, skip commit" branch.
- Fold the grep into Task 2.6's success criteria (next to the existing `grep` for `amoeba.cli.inspect_`). Alternatively fold it into Task 9.3, which edits those docs anyway.
- A separate task adds a sequencing hop and a checkpoint with nothing to commit.

### [CONCERN] CI gating of the new load tier is implicit

- The slice's Technical Requirements specify a load tier in `tests/load/test_serve_load.py`. Task 9.2 in file 3 creates it.
- CI already has a separate "Load tests" step running `uv run pytest tests/load` (ci.yml:53-54), so the new file would be picked up. No task in files 1–3 says so. The task file never mentions `ci.yml`, whether the default `uv run pytest` step also collects `tests/load`, or whether the real-uvicorn tests need a loopback port on the runner.
- Add one step to Task 9.2 to confirm the existing step covers the file and that the default step does not run it twice. If either check fails, this slice needs a small CI change.
- This finding rests on files 2–3 only through my grep of Task 9.2, so please confirm against that task.

### [NOTE] Tasks 2.5 and 2.6 form a large red-suite window

- Both tasks have effort 3 and commit together: six module moves, the registry move, `read_listing`, CLI rewiring, four test moves and the boundary test.
- This is reasonable for an unavoidable atomic migration, and the file says why. The risk is a junior stuck mid-way with nothing committed.
- If it seems too large, 2.5 could land `core.py` and the registry types first, using a temporary adapter. That would add complexity, so I would only do it if the PM wants smaller checkpoints.

### [NOTE] Task-level additions go beyond the design but are justified

- `FlagOption`, the `inspection/listing.py` types split, and `tests/inspection_harness.py` are not in the slice design. Each is documented with a reason.
- They trace to the design's "What changes shape" (options gaining a `name`), the import-cycle problem, and the shared seeded store for the baseline and parity tests.
- Task 2.2's "both or neither row function raises `ValueError`" test assumes `Listing` already has that validation. The design does not require it, so confirm it exists, or drop the assertion if it would mean adding new behavior.

### [NOTE] Step detail is heavy but mostly traceable

- Task 1.3 prescribes shell mechanics such as `mktemp`, and Task 3.1 prescribes the `BEGIN`/`ROLLBACK` handling and constant names.
- Most of this follows from verified facts in the Context Summary, such as `sqlite3` not opening a transaction for a `SELECT`. It is acceptable for a junior-AI audience.
- The three-file split fits this slice's size, at 16 tasks in this file alone, so I am not flagging it as overweight.

### Run Digest

- Response length: 5468 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 366367 / 270025 / 96332 / 6163 / not computed
- Duration: 57.8 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
