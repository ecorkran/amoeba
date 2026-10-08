---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: c4b926e479bff0342f550112a9bb5fcb7c841b84
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 41.4
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pairing and commit cadence"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:27"
  - id: F003
    severity: note
    category: nfr
    summary: "No load test or CI gate required"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:21"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 4.3 is the largest and riskiest single task"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:350-366"
  - id: F005
    severity: concern
    category: scope
    summary: "Task 6.3 knowingly departs from the LLD on label capture"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:80"
  - id: F006
    severity: note
    category: consistency
    summary: "Hard-coded migration number in test and file names"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:211-226"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 5.1 dependency is only transitive"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:372-375"
  - id: F008
    severity: note
    category: scope
    summary: "`cf_max_attempts` flag is added beyond the LLD text"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:376"
  - id: F009
    severity: pass
    category: testing
    summary: "Real-input and no-silent-skip discipline"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:59-100"
---

# Review: tasks — slice 108

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria map to tasks

Each LLD functional and technical requirement has a task and a named test:
- **Reader, location rule and diff:** Tasks 2.1–2.3.
- **Migration, trigger, 7→8 upgrade and feed invariant:** Tasks 3.2, 3.3 and 3.7.
- **`watch_cf` kind and the idle-tick cache:** Tasks 4.1–4.3 and 6.1.
- **Settings:** Task 5.1.
- **Tenant behaviour (file states, snapshots, absence, bounded failure, retry):** file 2, Tasks 6.2–6.6.
- **Listings, `start` wiring and end-to-end:** Tasks 7.1, 7.2 and 8.1.
- **Docs and requirement tracing:** Tasks 8.2–8.7.

I found no uncovered criterion and no task without a criterion behind it.

### [PASS] Sequencing, test-with pairing and commit cadence

- **Dependencies:** they run forward with no cycles.
- **Test pairing:** each implementation task is committed with its test task or carries its own tests (3.2→3.3, 3.5→3.6, 4.1→4.2).
- **Commits:** they are spread across every section, not batched at the end.
- **Writer guard:** the writer-guard test is deliberately moved to Task 6.3, where it can fail meaningfully.

### [NOTE] No load test or CI gate required

The LLD states no throughput NFR. "An idle tick performs one `stat`" is a behavioural guarantee, and Tasks 6.1 and 6.3 pin it with assertions. The file explicitly records that no `tests/load/` task or CI gate is planned. That is consistent with the review criteria. Task 1.3 does add a CI step to install `cf`, which the real-`cf` tests need.

### [CONCERN] Task 4.3 is the largest and riskiest single task

The revision counter is a mechanism the LLD does not spell out (effort 4). It needs a pending flag set by the effect, a bump after the `with` block exits, clearing on every apply and on any exception, and no bump on REJECTED. This touches `apply_submission`, the core inbox path. The steps and tests are detailed, but a junior could easily get the commit-timing semantics wrong. Consider splitting it into (a) the counter and flag mechanics on the mixin with unit tests, and (b) the `apply_submission` hook. At minimum, the task should point the implementer to `store/inbox.py`'s transaction structure up front. The task already routes the choice to the PM through Task 8.6.

### [CONCERN] Task 6.3 knowingly departs from the LLD on label capture

This is in file 2 but it comes from the Section 1–5 design context. The LLD says the version label is re-captured on each signature change. It also says "no tick starts a subprocess". The task resolves the conflict by capturing once per recording read, and it flags the conflict for the PM in Task 8.6. This is a sound reading, but it is an unapproved deviation that is only reported at the very end (Task 8.6). Ask the PM to settle it before Phase 6 reaches Task 6.3, or amend the LLD first, so the tenant is not built on a contested reading.

### [NOTE] Hard-coded migration number in test and file names

Task 1.1 allows the migration to be `007` if 107 is unmerged. Task 3.3 hard-codes `tests/store/test_migration_008.py`, "version-7" and the previous-version wording. Task 3.2 does say to use the number from Task 1.1, and the intro says to use the actual number wherever "008" appears. Still, Task 3.3's Files to Create and Task 8.7's `test_migration_008` reference should say "named for the actual migration number" to avoid a mismatch.

### [NOTE] Task 5.1 dependency is only transitive

Task 5.1 declares a dependency on Task 4.3, but its real code dependency is Task 2.1 (`resolve_cf_data_dir`). The ordering is satisfied transitively, so there is no defect. Declaring Task 2.1 would be more accurate.

### [NOTE] `cf_max_attempts` flag is added beyond the LLD text

The LLD lists `--cf-data-dir` as the only flag. The task adds `--cf-max-attempts` and `--cf-scan-interval-seconds` for consistency with the existing flags. This is minor, low-risk scope growth, and it is flagged for the PM in Task 8.6. I checked the referenced helpers: `AttemptsSidecar` (`src/amoeba/inbox/sidecars.py`), `write_durably` (`src/amoeba/inbox/durable.py`), `capture_version_label` (`src/amoeba/process/observers/cf_readback.py`) and `cf_timeout_seconds` (`src/amoeba/process/settings.py`) all exist.

### [PASS] Real-input and no-silent-skip discipline

Tasks 1.2 and 1.3 meet the parser-fixture rule in CLAUDE.md: a byte-real `projects.json` fixture plus a harness that fails rather than skips when `cf` is missing. Task 1.3 refuses to guess the npm package name for CI and stops to ask the PM instead.

### Run Digest

- Response length: 5682 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 41.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
