---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: fc660a6040b82597a1cda97452f62011ffa226c7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 47.3
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Watch-cache \"dirty\" rule is ambiguous for reactivation"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:35"
  - id: F002
    severity: concern
    category: process
    summary: "Hallucination trap: example package name next to a \"confirm\" instruction"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:89"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Tenant skips `failed` watches only after Task 6.6, but Task 6.5 commits first"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:113-149"
  - id: F004
    severity: note
    category: requirements
    summary: "Slice design contradiction on subprocess use is resolved, and disclosed"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:140"
  - id: F005
    severity: note
    category: testing
    summary: "No load test, and no CI gate beyond `cf` installation"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:275"
  - id: F006
    severity: note
    category: dependencies
    summary: "Unverified references in the tasks"
    location: "src/amoeba/store/schema"
  - id: F007
    severity: note
    category: granularity
    summary: "Tasks 8.5 and 8.6 are non-code and could be merged"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:311-340"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and test-with sequencing"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:342-370"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Watch-cache "dirty" rule is ambiguous for reactivation

Task 6.1 says "A refresh that finds an active watch not in the previous cache marks the tenant dirty." A reactivated watch was already in the cache, as inactive, so a literal reading never marks it dirty. If the file signature hasn't moved since the watch went inactive, the dispatch is skipped and no snapshot is recorded. That breaks the slice design requirement that a reactivated watch records one snapshot covering everything that changed while it was inactive. The rule should read "an active watch that was not active in the previous cache". Task 6.4's reactivation test only passes if CF also changes after reactivation, so add a case with an unchanged file after reactivation.

### [CONCERN] Hallucination trap: example package name next to a "confirm" instruction

Task 1.3 tells the implementer to run `npm install -g @context-forge/cli` and then to "confirm the package name against the one installed locally (`npm ls -g --depth=0`)". The project's CLAUDE.md names this pattern as a hallucination trap: an example value placed next to a retrieval instruction. If the lookup comes back empty or ambiguous, the example gets used and CI breaks. Reword it so the name comes only from `npm ls -g`, with an explicit stop if it can't be found. The hardcoded Node "22" is a smaller version of the same problem.

### [CONCERN] Tenant skips `failed` watches only after Task 6.6, but Task 6.5 commits first

Task 6.5 parks a watch as `failed`, but nothing skips it until Task 6.6. Between those two commits, every dispatch retries the parked watch and keeps incrementing its sidecar past the limit. The slice design's cadence rule (no commit holds unfinished behavior) is arguably broken here. Either merge 6.5 and 6.6, or give 6.5 a minimal skip-while-sidecar-exists check and leave only the retry transition to 6.6.

### [NOTE] Slice design contradiction on subprocess use is resolved, and disclosed

The slice design says `cf --version` runs "per detected change", and also says "No tick starts a subprocess". Task 6.3 resolves this by capturing the label only when a snapshot is about to be recorded, so a read that records nothing starts no subprocess. Task 8.6 reports the choice to the PM. This is reasonable. I suggest the PM amend the slice design wording.

### [NOTE] No load test, and no CI gate beyond `cf` installation

The slice design states no quantified non-functional requirement. The nearest are "within about two scan intervals" and the one-`stat` idle guarantee. The idle guarantee is pinned by spy-based unit tests in Tasks 6.1 and 6.3, so a `tests/load/` task isn't required. Task 1.3 does edit `.github/workflows/ci.yml` so the real-`cf` tests run in CI, which covers the CI-wiring check.

### [NOTE] Unverified references in the tasks

The `schema/` directory currently holds only 001–005. Tasks 1.1 and 3.2 depend on 106's `006` and 107's `007` being merged, and Task 1.1 stops if they aren't. `settings.cf_timeout_seconds`, which Task 7.3 uses, does exist in `src/amoeba/process/settings.py:57`.

### [NOTE] Tasks 8.5 and 8.6 are non-code and could be merged

Task 8.6 (effort 1) only restates items for the final message, and Task 8.5 already produces that message. Merging them removes a task with nothing to check. Leaving them separate does no harm.

### [PASS] Success-criteria coverage and test-with sequencing

Each slice design requirement maps to a task and a named test, and Task 8.7 re-checks the full list. The functional criteria map as follows: first snapshot, `cf set`, noise, and unlinked changes to 6.3; absence, restore, catch-up, and reactivation to 6.4; `unreachable` and `unrecognized` to 6.2; bounded failure to 6.5 and 6.6; the idle tick to 6.1. The technical criteria map as follows: single definitions and import boundaries to 8.4, the 7→8 upgrade to 3.3, the feed invariant to 3.7, and the contract docs to 8.2 and 8.3. Dependencies run one way with no cycles, and each deferred commit ("committed with Task N.M") pairs an implementation task with the test task that follows it immediately.

### Run Digest

- Response length: 5427 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 47.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
