---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: b5da659741742529433c377b91c455da5186e39a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 49.4
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Section 11 maps to the slice's closing requirements"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:21-120"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 11.2 is large, and its acceptance check can pass without exercising the scenario"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:43-58"
  - id: F003
    severity: concern
    category: success-criteria
    summary: "Task 11.1 does not run the script it writes, and its refusal test is vague"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:23-39"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 11.3 and Task 11.4 are documentation-only with weak verification"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:62-99"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 11.5 bundles several unrelated checks into one task, and the final criterion is open-ended"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:103-120"
  - id: F006
    severity: note
    category: coverage
    summary: "Several Functional Requirements have no named test in this file"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:386-409"
  - id: F007
    severity: note
    category: sequencing
    summary: "Test-with pattern and commit cadence are satisfied"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:21-120"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Section 11 maps to the slice's closing requirements

Task 11.1 covers the demo script from the Verification Walkthrough. Task 11.2 covers the Integration Requirement's end-to-end CLI scenario and names `tests/cli/test_detection_end_to_end.py`, the file walkthrough step 9 runs. Task 11.3 covers `docs/feed-contract.md` and its listed contents. Task 11.4 covers the Technical Scope's contract-update bullet and the D8a correction to the 103 forward reference. Task 11.5 covers walkthrough steps 1–9 and the Technical Requirements checks. The invariant test (step 9's other file) is in file 1 at line 432.

### [CONCERN] Task 11.2 is large, and its acceptance check can pass without exercising the scenario

One test must drive a ten-step subprocess sequence, including a follower, `kill -9`, and restarts. It must also make four assertions, among them follower-vs-`inspect` agreement, no duplicate verdicts or ledger rows, and `--after` resume. Effort 4 is the highest in the file, and a junior AI could easily get stuck mid-way. Consider splitting it into two tasks. The first would cover the sequence and its agreement and no-duplicate assertions. The second would cover the `--after` resume and `node_status_changed` assertions, so each can be committed on its own. The step list also never says to apply a `resolution` submission, yet the assertions require the follower to see `node_status_changed` for one. The demo script seeds the blocked node, but nothing says to submit the resolution. Add the step and the `blocked_state_id` lookup, as walkthrough step 2 does.

### [CONCERN] Task 11.1 does not run the script it writes, and its refusal test is vague

The success criteria only require `tests/test_writer_guard.py` to pass, which proves the allow-list edit and says nothing about the script. Add a criterion that the script prints two space-separated ids, slice node first, so that `read SLICE_NODE BLOCKED_NODE` in the walkthrough works. The third step ("Extend or add a small test") doesn't say where the test lives or which harness it uses. The task also lacks a test that the seeded slice node's `cf.slice_name` is the one the attribution rule matches. 11.2 would catch that, but the failure would then be far from its cause.

### [CONCERN] Task 11.3 and Task 11.4 are documentation-only with weak verification

Task 11.4 touches seven files and has six sub-steps. Its only success criterion is that "each contract states the change". That is hard to check, and it risks the 120 requirements (D5 points 3 and 5, and the attribution rule) being dropped from `evidence-contract.md`. Consider splitting it into the store/inbox/process contracts and the evidence-contract/CHANGELOG/103 edit. Each half would get a checkable criterion, such as a grep for the listed names. Task 11.3 requires "every name exists in `src/`", which is good. Task 11.4 should have the equivalent check.

The 103 edit says "line near 319" and "edit only that sentence". The slice cites line 319 as the location of the `applied_seq` reference, but the task should tell the implementer to locate the sentence by its content, since line numbers drift.

### [CONCERN] Task 11.5 bundles several unrelated checks into one task, and the final criterion is open-ended

The task combines the full suite, a nine-step manual walkthrough, a file-size audit, an import-boundary grep, and a requirement-to-test audit across about 25 Functional Requirements. The last item is the least bounded: "add a missing test if any has none" could add substantial work to a task rated effort 2. Consider moving the requirement-to-test map into its own task before 11.5, with its output written to a file, and leaving 11.5 as the run-and-confirm gate. The import-boundary check could also become a permanent test, such as an AST import check in the store test suite, rather than a one-off grep. That would keep the Technical Requirement enforced after this slice.

The walkthrough's draft output is also known to be provisional ("refined with real output when Phase 6 completes"). The task says to record differences for the PM instead of editing the LLD, which fits the project's rule against guessing. It should still state where the PM report goes, such as a named file or the final commit message.

### [NOTE] Several Functional Requirements have no named test in this file

The end-to-end test and the invariant test cover only part of the Functional Requirements list. These behaviors belong to files 1–2, so I did not verify them:
- unreachable and `baseline_pending` watches
- bounded store failure with a `failed` listing
- the file-deleted race
- the `SQ_RUN` defer rule
- `runner_issued` skipping
- the `recorded_since` flag after a manual ingest
- the `source_document` series separation
- the 5 → 6 upgrade test

Task 11.5's audit is the safety net for these. Ideally the audit table would be built progressively, or its result recorded in the task, so that gaps surface before the last task.

### [NOTE] Test-with pattern and commit cadence are satisfied

The test task 11.2 follows its dependency 11.1, and the docs tasks follow the test. Each of 11.1–11.4 ends with a semantic commit step, and 11.5 ends with a commit of any remaining changes. Nothing is batched. The "no merge performed" criterion in 11.5 matches the branch rules.

### Run Digest

- Response length: 6948 chars
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
- Duration: 49.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
