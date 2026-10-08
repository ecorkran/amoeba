---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 09bac3db0e57a00b11f0c97aa0f222f08bef0dd4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 111.6
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 8.4 omits its dependency on the payload inverse"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:208-221"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 8.5 forward-references Task 8.6 and may need a node it doesn't need"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:234"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "The conditional file split in Task 4.1 is ambiguous and likely"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:327"
  - id: F004
    severity: concern
    category: documentation
    summary: "Task 8.6 creates a harness file that its Files to Create list omits"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:255-262"
  - id: F005
    severity: note
    category: sequencing
    summary: "Task 7.4's keep-list could be read as deleting the new fixture constants"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:130"
  - id: F006
    severity: note
    category: process
    summary: "Task 1.2 sends repository content to an external provider"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:74-85"
  - id: F007
    severity: note
    category: test-with-pattern
    summary: "Task 2.2 commits a refactor before its direct test"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:142-177"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F009
    severity: pass
    category: nfr
    summary: "No NFR, so no load-test or CI-gating task is required"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:376-392"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing, commit cadence and the external gate are well handled"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:28"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 8.4 omits its dependency on the payload inverse

Task 8.4 calls `verdict_to_payload`, which Tasks 6.1 and 6.2 deliver. Its only listed dependency is Task 8.3. Task 8.1 is marked "Task 5.5 (independent of Section 7)" and never mentions Section 6. A junior AI that follows the stated dependencies could reach 8.4 with Section 6 unfinished. Add Task 6.2 to the dependencies of Task 8.4, or of Task 8.1.

### [CONCERN] Task 8.5 forward-references Task 8.6 and may need a node it doesn't need

The D7 check in Task 8.5 says to "seed a node (`scripts/demo_evidence.py`, as in Task 8.6)". Task 8.6 comes after 8.5, so the instruction points forward.

Ingest opens no store and `submit()` is fire-and-forget, so the stopped-process test never needs a real node. A literal node id string is enough to show that stderr prints both the node and the review's slice, and that the file is still submitted. Either drop the seeding or state why it is needed. If it stays, say where the seeding helper lives, since the shared harness is only created in Task 8.6.

### [CONCERN] The conditional file split in Task 4.1 is ambiguous and likely

Task 4.1 says to split `review.py` into `review_json.py` and `review_artifact.py` "if `review.py` is now past ~300 lines". By that point `review.py` holds the types, the errors, the frontmatter helpers, the artifact reader, the shared finding helper and the JSON reader. Tasks 5.1 and 5.3 add the digest and composition afterwards. The split is therefore nearly certain, and the later additions could push the file over again with no checkpoint.

A conditional refactor inside a size-3 implementation task is a poor fit for a junior AI. It also moves the helpers that Task 3.2 and Task 3.4 placed in `review.py`. Decide the layout up front, either by creating the split files in Task 3.1 or by adding an explicit split task before Task 4.1. Task 9.3's `wc -l` check is the only later safeguard.

### [CONCERN] Task 8.6 creates a harness file that its Files to Create list omits

A step in Task 8.6 creates the shared helper `tests/cli/ingest_e2e_harness.py`. That file is missing from the task's "Files to Create" list, which names only `test_ingest_end_to_end.py`. Task 8.6 also does three things at once: it builds the harness, writes the subprocess scenario and checks standings after a `kill -9`. Add the harness file to the list. Consider extracting the harness into its own small task so the failure surface is smaller.

### [NOTE] Task 7.4's keep-list could be read as deleting the new fixture constants

Task 7.4 says to keep "`SQ_REVIEWS` and the four `ROUND_*` paths". Tasks 1.1 to 1.3 add several more path constants to `tests/review_fixtures.py`, and the later tests import them. The explicit delete-list protects them, but the keep-list reads as exhaustive. Say "keep all path constants, including those added in Section 1".

### [NOTE] Task 1.2 sends repository content to an external provider

Running `sq review slice 105 --model glmflash` sends the slice design to an external model provider and needs a key and network access. The task already stops and asks the PM when `sq` or a key is missing. It does not ask for confirmation before the outbound call. Consider adding "confirm with the PM before running" to the first step. The task does handle the failure case well, and the gating is contained and clear.

### [NOTE] Task 2.2 commits a refactor before its direct test

Task 2.2 (a pure refactor, no behavior change) commits separately from Task 2.3, which holds the direct test. This is acceptable because 104's existing rejection tests cover the behavior, and the task says so. Note that the single-definition guarantee is only enforced from Task 2.3 onward.

### [PASS] Success-criteria coverage is complete

Each criterion maps to tasks:
- **Fixtures:** the per-file expectations map to Tasks 1.1 to 1.3 and 3.5.
- **Provider-failure files:** Tasks 3.5 and 5.4 cover both.
- **Findings Not Parsed:** covered by Tasks 3.5 and 1.3.
- **PR review:** covered by Task 3.5.
- **0.15.0 stamp and `sq_run_id`:** covered by Task 3.5.
- **Stdout rules:** the `fallback_used` branches, `requested_model` and trailing-line tolerance are in Task 4.2.
- **File/stdout pair:** Tasks 4.2 and 5.2 for pair equality, 8.8 for D5.
- **Record id:** invariance is in Task 5.2.
- **Error cases:** Tasks 3.5, 4.2 and 5.4.
- **`verdict_to_payload` round trip:** Task 6.2.
- **Test migration:** Section 7.
- **CLI paths:** Tasks 8.3 and 8.5 to 8.8.
- **D6 and D7:** Tasks 8.3, 8.5 and 8.7.
- **Single definitions and import direction:** Tasks 2.3 and 5.5.
- **Docs:** Section 9.

I found no gaps. I also found no scope creep. Even Task 9.3's walkthrough edit is authorized by the slice design.

### [PASS] No NFR, so no load-test or CI-gating task is required

The slice states no performance or scale NFR. Task 9.3 notes that no load test is added and runs the existing `tests/load` suite only as a regression check. That suite exists in the repo. Nothing needs a new load test or CI gate.

### [PASS] Sequencing, commit cadence and the external gate are well handled

- Dependencies are acyclic.
- PyYAML moves before the first `yaml` import.
- Each implementation task commits with its test task, and the others commit alone, so commits are spread throughout.
- Task 8.2's stub returns a failure code and never `OK`, so no interim commit reports false success.
- The Task 1.2 dependency is isolated by the `blocked on 1.2` marker, and Task 9.3 refuses to close the slice while any item is still blocked.
- Fixture expectations are written from the files, not from parser output.
- Real-format tests guard against silent parser failures, as the project parsing rules require.

### Run Digest

- Response length: 7355 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 111.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
