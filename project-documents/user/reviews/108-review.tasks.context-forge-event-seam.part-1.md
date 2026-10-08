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
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 95aff093a99aecc6276d9fd65207b9a720969886
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 62.5
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "The combined record-and-state store method is unnamed and sits outside the writer guard"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:276"
  - id: F002
    severity: concern
    category: requirements-traceability
    summary: "Version-label task wording is inconsistent and departs from the LLD without amending it"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:79-101"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 6.1 and Task 6.3 are on the large side"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:28-90"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Task 6.6 leaves the error class to catch unspecified"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:141"
  - id: F005
    severity: note
    category: sequencing
    summary: "Extra dependency edges"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:393"
  - id: F006
    severity: note
    category: scope
    summary: "Added scope is flagged and mostly well bounded"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:395"
  - id: F007
    severity: pass
    category: ci-gating
    summary: "No load test or CI gate is required, and CI wiring for real `cf` is present"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:91"
  - id: F008
    severity: pass
    category: coverage
    summary: "Requirement coverage and test-with sequencing"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:37-407"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] The combined record-and-state store method is unnamed and sits outside the writer guard

Task 3.6 adds "one method that records a snapshot and sets the watch state in a single transaction" without naming it. The tenant calls this method in Task 6.3. Other tasks refer to it only as "the Task 3.6 combined method" or "the combined record-and-state method" (Tasks 3.7, 6.3, 6.6).
- **Writer guard gap:** the guard in Task 6.3 covers only `record_cf_snapshot` and `set_cf_watch_state`. The method the tenant actually calls for recording is not covered, so it can be called from anywhere without the guard noticing.
- **Equality assertion:** if the tenant calls only the combined method for recording, the "set equals `{process/cf_watch.py}`" check still passes. That is only because the tenant also calls `set_cf_watch_state` for `ok` and `missing`.
- **Doc gap:** the method is not in the LLD API table. Task 8.3's "six new store methods" for `store-contract.md` omits it, and the contract would miss a public writer.

Fix: name the method in Task 3.6 and add it to the guarded set in Task 6.3 and to the Task 8.4 check. Also list it in Task 8.3 and Task 8.6 as an addition to the LLD API table.

### [CONCERN] Version-label task wording is inconsistent and departs from the LLD without amending it

Task 6.3 says `capture_label` is "called once per recording", which can mean once per snapshot. Task 6.4 says "at most once per file read, and only when a snapshot is about to be recorded." One read can record several snapshots, across projects or watches, so a junior could implement either.

Both readings differ from the LLD, which says the label is re-captured when the file signature changes, and also says "no tick starts a subprocess". The tasks acknowledge the conflict and defer it to the PM report in Task 8.6, so code gets written against a contradiction. Tasks 1.1 and 6.4 already require reporting this before or during coding, but no task makes amending the LLD a blocker.

Fix: use one phrase in both tasks ("once per file read that records at least one snapshot, shared by all snapshots from that read"). Make the PM's answer on the LLD amendment a precondition of Task 6.4, not only a closing report.

### [CONCERN] Task 6.1 and Task 6.3 are on the large side

Both are effort 4.
- **Task 6.1** bundles the interval gate, a per-project cache with a revision-driven refresh, dirty-flag semantics, signature computation, and six test scenarios.
- **Task 6.3** bundles an AST writer-guard test (an unrelated artifact), the per-watch diff and recording, and a real-`cf` test file with five scenarios, each also asserting the feed.

Fix: move the writer-guard test into its own small task, or into Task 3.6/Task 8.4 with a "tenant calls it" assertion added in 6.3. Optionally split the watch cache from the signature and idle logic in 6.1. This is not blocking.

### [CONCERN] Task 6.6 leaves the error class to catch unspecified

The task says to catch "the store's error base class and `sqlite3.Error`". It does not name the class or where it is defined, and Task 1.1 records locations only for `AttemptsSidecar` and `write_durably`. Under CLAUDE.md's exception-handling rule, a junior who guesses wrong will either miss real failures or widen the catch.

Fix: add the base error class to the locations Task 1.1 records, and name it in Task 6.6.

### [NOTE] Extra dependency edges

- Task 5.1 lists Task 4.4 as a dependency, but settings need only Task 2.1.
- Task 1.3 depends on Task 1.2, but the harness does not use the fixture.
- Task 3.1's header says it depends on Task 1.1 but is "sequenced after Section 2".

None of these is harmful, since they only over-constrain order. Tidy them if the file is touched again.

### [NOTE] Added scope is flagged and mostly well bounded

Three items go beyond the LLD text, and each is reported to the PM in Task 8.6:
- The `--cf-max-attempts` flag: small and consistent with the sibling flags. The `--cf-scan-interval-seconds` flag is in the LLD only through "with CLI flags".
- The `cf_watch_revision` counter (Tasks 4.3 and 4.4): it implements a mechanism the LLD requires but does not specify, and the rollback-safety task is warranted.
- The `cf_layout.py` module, which keeps the sidecar path defined once.

Task 6.7's per-scan sidecar existence check for `failed` watches is a bounded exception to the one-`stat` idle guarantee. Task 8.3 documents it in the process contract. The Task 7.2 process test and the Task 8.1 end-to-end test overlap somewhat, but the LLD requires the end-to-end one.

### [PASS] No load test or CI gate is required, and CI wiring for real `cf` is present

The LLD sets no throughput or latency requirement. The idle-tick guarantee is functional and is pinned by assertions, so no `tests/load/` task is needed. Task 1.3 adds a CI step that installs `cf`, with a `cf --version` check, so the real-`cf` tests cannot silently skip or fail only in CI.

### [PASS] Requirement coverage and test-with sequencing

- **Reader and diff:** Tasks 2.1–2.3 cover location, errors, and the `IGNORED_KEYS` rule, with real fixtures from Task 1.2.
- **Schema and feed:** Tasks 3.2–3.7 cover migration 008, the trigger tests, the invariant extension, and the dropped-trigger case.
- **Inbox and settings:** Tasks 4.1–4.4 cover the `watch_cf` kind and the revision counter. Task 5.1 covers settings and flags.
- **Tenant and wiring (file 2):** Tasks 6.1–6.7 cover the idle path, file-level states, snapshots, absence and catch-up, bounded failure, and retry. Tasks 7.1–7.2 cover the listings and the `start` wiring.
- **End-to-end and docs:** Task 8.1 is the end-to-end test. Tasks 8.2–8.3 cover docs. Task 8.4 pins boundaries. Task 8.5 runs the walkthrough. Task 8.7 traces every requirement to a named test.

I found no LLD success criterion without a task, and no task without a traceable LLD source apart from the flagged additions above. The dependencies have no cycles.

### Run Digest

- Response length: 7330 chars
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
- Duration: 62.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
