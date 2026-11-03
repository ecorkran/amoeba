---
docType: review
layer: project
reviewType: tasks
slice: live-walkthrough
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/145-tasks.live-walkthrough.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 9808f35d584e6572344895b4392542bf435a973f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 101132
cachedTokens: 8831
cacheWriteTokens: 92297
completionTokens: 5442
durationSeconds: 46.1
costUsd: 0.42534
costBasis: provider
runId: run-20261103-p5-6d56c562
squadronVersion: 0.24.16
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md"
  - id: F003
    severity: concern
    category: testing
    summary: "Fixture-test negative assertion is ambiguous and exceeds the slice's test spec"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:93"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 6 is a near-duplicate validation pass"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:163-170"
  - id: F005
    severity: concern
    category: completeness
    summary: "D7 recovery paths are only partly carried into the case tasks"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:174-227"
  - id: F006
    severity: concern
    category: completeness
    summary: "Slice node ids needed to drive the cases may not be available"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:120"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task 11.2 test scope is slightly heavy for the criterion"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:242-244"
  - id: F008
    severity: note
    category: conventions
    summary: "`BLOCKED:` lines used for sequencing, not only for external blockers"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:192,206,209,221"
  - id: F009
    severity: note
    category: sequencing
    summary: "3.5 success defers to a later task"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:121"
---

# Review: tasks — slice 145

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Cases 1–4:** tasks 7–10.
- **Fixture test without `sq` or a model:** task 2.
- **Script refusals and subprocess failures:** tasks 3.1, 3.2 and 3.6.
- **Strict lint and typecheck:** tasks 3.6, 6 and 12.3.
- **Doc and `process-contract.md` link:** task 5.
- **Tails fixture and live-tier collection:** task 11.
- **Registry-isolation and no-outside-writes check:** tasks 5.1 and 12.1.
- **Issues linked from task notes:** 9.2 and 11.3.

No NFR is restated in the slice, so no load-test or CI-gating task is needed. Nothing under `src/` is touched, which matches the exclusions.

### [PASS] Sequencing and commit markers

- **Dependencies:** the tree, then the fixture test, then the script and its tests, then the start-up check, then the doc, then the live cases in dependency order. No circular dependencies.
- **Test-with pattern:** 3.6 follows the script, and 11.2 follows 11.1.
- **Markers:** they sit at working, tested points. Live-result notes ride along with the task 11 commit, which respects the rule against notes-only commits.

### [CONCERN] Fixture-test negative assertion is ambiguous and exceeds the slice's test spec

- **Beyond the spec:** task 2.2 asserts "no passage in the tree states a date format or license header". The slice's fixture-test spec (D6) lists only three checks: the four plan files are found, a passage contains "JSON Lines", and a passage contains the merge sentence.
- **Likely to fail:** by task 1.3's own design, the forcing sentences for slices 102, 103, 104 and 105 contain the phrases "date format" and "license header". A naive substring assertion fails against them. A junior implementer has no way to tell "mentions" from "states an answer".
- **Fix:** drop the assertion. The "nothing answers it" property is a content rule that task 1.3's search check already enforces. If it stays, define it concretely, for example by excluding the forcing sentences.

### [CONCERN] Task 6 is a near-duplicate validation pass

- **Redundant:** the commit-cadence note already requires format, lint and typecheck before the markers in tasks 1–3 and 5. Task 12.3 repeats the full validation at the end.
- **Empty commit risk:** task 6 adds a `chore:` commit that the file itself says to skip if nothing changed. That is conditional busywork.
- **Fix:** fold the full pytest run into the task 5 marker, or drop task 6.

### [CONCERN] D7 recovery paths are only partly carried into the case tasks

- **Fixture-cause fix scope:** D7 says a fixture-cause fix changes the tree, and the tree lives in the repository. Task 8.1 only adds an entry to the scratch plan and commits it in the scratch checkout. Task 9.2's rerun ("a fresh index") says nothing about the repository tree. If the repository tree is not updated, the next walkthrough run will not reproduce the fix. The repository tree and the doc would drift from what was run.
- **Environment and product causes:** the D7 "Environment" path (design run `failed` or `orphaned`, resolve with `stop`, repeat once) appears in no task. The "Product cause" path (file an issue, mark `BLOCKED:`) is explicit only in 9.2. Tasks 8.1, 10.2 and 10.3 do not mention it.
- **Unplanned questions:** the PM answering them when declined (Special Considerations) is not mentioned either.
- **Fix:** add one sentence to the intro or to each live task: "On any other outcome follow D7, and mirror any tree fix into `scripts/answerer_walkthrough/project/`."

### [CONCERN] Slice node ids needed to drive the cases may not be available

- **Unclear source:** task 3.5 prints "the node ids if the CLI prints them". Tasks 5.1 and 7–10 need the exact `submit intent drive` command for each of the six slices, so they depend on those ids.
- **Missing step:** no task creates the six slice nodes or says how to obtain their ids. The risk is a task 5 doc that can't be written, or live tasks that stall.
- **Fix:** have task 3.4 or 3.5 read `uv run amoeba submit --help` and `inspect` to establish how slice nodes appear. State in 3.5 how the script gets each slice's node id for the doc, and stop with an error if it can't.

### [CONCERN] Task 11.2 test scope is slightly heavy for the criterion

- **Over-specified:** the success criterion only requires that every captured tail is in the JSON with run id and date, and that the live tier still collects. Asserting unique run ids is dubious: one run could legitimately produce two questions, and 11.1 says to include reruns. A uniqueness assertion could fail on valid data.
- **Fix:** drop the uniqueness assertion, or key uniqueness on (run_id, question). Keep the four-key and non-empty checks.

### [NOTE] `BLOCKED:` lines used for sequencing, not only for external blockers

Tasks 8.1, 9.1, 9.2 and 10.1 carry "BLOCKED: same condition as task 7.1, and task N complete". The Squadron-release part is a genuine external blocker. The "task N complete" part is plain ordering, which the intro's "work tasks in file order" already states. This is harmless but dilutes the `BLOCKED:` signal.

### [NOTE] 3.5 success defers to a later task

Task 3.5's success criterion ("loads under Amoeba's loader") is verified in 3.6, not in 3.5. It is acceptable inside one task and one commit, but the check belongs to 3.6's success line.

### Run Digest

- Response length: 6483 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 101132 / 8831 / 92297 / 5442 / not computed
- Duration: 46.1 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
