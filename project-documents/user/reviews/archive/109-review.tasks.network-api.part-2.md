---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: e3175941e3b9b62b982951f504ae9c54428c3817
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 35.0
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 5.8 needs a subprocess server that doesn't exist yet"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:315"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The drain verification comes after the stall bound it validates"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:292-321"
  - id: F003
    severity: concern
    category: commit-checkpoints
    summary: "Three tasks share one commit, and a failing check leaves 5.7 uncommitted"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:303-339"
  - id: F004
    severity: note
    category: task-sizing
    summary: "Task 3.9 covers a lot but stays coherent"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:45-61"
  - id: F005
    severity: note
    category: nfr-coverage
    summary: "No load test or CI gate, with a stated reason"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:347"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success Criteria coverage for this file's scope"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and error-table discipline"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:24-356"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.8 needs a subprocess server that doesn't exist yet

Task 5.8 requires measuring the server's resident memory with `ps -o rss= -p <pid>`, and says to "run the server as a subprocess for this test so the pid is its own". The only launcher available at that point is the Task 5.5 harness, which runs `uvicorn.Server` in a thread of the test process. The pid would then be pytest's, and the RSS reading would be meaningless. `amoeba serve` is not built until Task 7.1, and the task says nothing about a launcher script or a subprocess mode for the harness. This test is also the stop-and-ask gate on the slice's riskiest assumption. A junior would have to invent the launcher. Add a step that extends `tests/serve/server_harness.py` with a subprocess variant, for example a tiny entry module that builds the app and runs uvicorn, and have it return the pid and port. Alternatively, say explicitly how the pid is obtained.

### [CONCERN] The drain verification comes after the stall bound it validates

The slice's Development Approach says the drain verification "must pass before the rest of the stream work". Task 5.7 builds the cap and the stall bound first, and Task 5.8 then checks that uvicorn's `send` can make the stall bound fire. If 5.8 fails, the stall-bound half of 5.7 is wasted. The test needs a stall bound to observe, so some order is forced. Consider splitting 5.7 into the cap and the stall-bound send wrapper. Then run the verification right after the stall bound and before the cap work. At minimum, tell the executor to commit 5.7 or hold it locally so a failed 5.8 leaves a clear state. The 5.8 text "Commit with Task 5.9 only if it passes" does not say what happens to 5.7's work if it fails.

### [CONCERN] Three tasks share one commit, and a failing check leaves 5.7 uncommitted

Tasks 5.7, 5.8 and 5.9 are one commit ("includes Tasks 5.7–5.8"). That commit includes a stop-and-ask check that may halt the work. Everything else in the file commits every one or two tasks. Under the failure path, the stall and cap implementation is left in the working tree while the PM decides. Commit 5.7 separately, as `feat: bound stream slots and stalled sends`, or state explicitly that the work stays uncommitted on a 5.8 failure.

### [NOTE] Task 3.9 covers a lot but stays coherent

Task 3.9 holds six test groups: registry-wide parity, snapshot, size bound, busy and schema errors, status codes, and the writer-guard extension. It is rated effort 4 and the groups are independent. The writer-guard and file-bytes check could be its own small task if the executor struggles. That is optional.

### [NOTE] No load test or CI gate, with a stated reason

The slice restates one latency bound (`follow_interval_seconds` plus delivery time) and sets no throughput target. Task 5.10 covers it with a timing test in the default suite and says no `tests/load/` task or CI gate is needed. That is consistent with the slice, and the default suite already runs in CI. The three-consecutive-runs flakiness check is a good guard. The 5.10 instruction to "tell the PM" if the latency test is flaky, rather than skip it, matches project rules.

### [PASS] Success Criteria coverage for this file's scope

- **Listing parity, `change_head` snapshot, `listing_too_large`, `store_busy`, writer guard:** Tasks 3.8 and 3.9.
- **`locate` and the status-race criterion:** Tasks 4.1, 4.2 and 4.6 (new→quarantine, new→failed, apply-and-delete).
- **422 reason parity, retry with the same id, 408 and 413 while reading, no-store quarantine:** Tasks 4.3 to 4.5.
- **Stopped-process submission becoming `applied`:** Task 4.6.
- **SSE order, resume and transcript equality:** Task 5.6.
- **Heartbeat:** Task 5.6.
- **Cap and slot freeing:** Task 5.9.
- **Thread counts, backpressure and stall:** Tasks 5.8 and 5.9.
- **Checkpoint `busy = 0` and latency:** Task 5.10.

No task is scope creep. The server harness is justified by the streaming tests.

### [PASS] Sequencing, test-with pattern and error-table discipline

Dependencies are linear with no cycles, and the Group B read checkpoint (Task 3.10) sits before the writes begin. Each implementation task is immediately followed by its test task: 3.8→3.9, 4.1→4.2, 4.3→4.4, 5.1→5.2, 5.3→5.4, 5.5→5.6. Tasks instruct the executor to route statuses through the single error table and to reuse existing helpers, such as the 103 filename helpers, the 106 attempts-sidecar helper and `change_as_json`, rather than redefine them. That matches project rules on DRY and single-definition values.

### Run Digest

- Response length: 5822 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
