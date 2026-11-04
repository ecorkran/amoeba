---
docType: review
layer: project
reviewType: tasks
slice: live-walkthrough
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/186-tasks.live-walkthrough.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 97a2f674fd761bda547f7d6f83a352e02f834f6a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: xhigh
turns: 13
promptTokens: 516273
cachedTokens: 360984
cacheWriteTokens: 155279
completionTokens: 63525
durationSeconds: 279.1
costUsd: 0.187528
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Rerun path is circular: Task 9.1 and Task 10.1 gate each other"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:231"
  - id: F002
    severity: concern
    category: documentation
    summary: "Dangling reference to Task 9.3"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:200"
  - id: F003
    severity: concern
    category: commit-cadence
    summary: "Task 5's fix commit contradicts the commit cadence"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:163"
  - id: F004
    severity: concern
    category: junior-completability
    summary: "Branch name and block-resolution command have no stated source"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:216"
  - id: F005
    severity: concern
    category: safety
    summary: "Isolation from the real registry is checked only at the end"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:158"
  - id: F006
    severity: concern
    category: junior-completability
    summary: "Tree documents are placed in the wrong directory by the literal text"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:93"
  - id: F007
    severity: concern
    category: dependencies
    summary: "Dependencies omit 144, which Task 12.1 writes into"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:6"
  - id: F008
    severity: concern
    category: commit-cadence
    summary: "Commit markers leave the live evidence uncommitted until the end"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:283"
  - id: F009
    severity: note
    category: scope
    summary: "Setup-time `applied` check is dropped, and the LLD still says the opposite"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:214"
  - id: F010
    severity: note
    category: duplication
    summary: "Config write may duplicate 145's template"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:139"
  - id: F011
    severity: note
    category: junior-completability
    summary: "Some stop conditions are vague"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:193"
  - id: F012
    severity: note
    category: process-rule
    summary: "The merge sub-item sits in a task file"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:216"
  - id: F013
    severity: note
    category: coverage
    summary: "Coverage, test-with pattern and references check out"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md"
  - id: F014
    severity: note
    category: nfr
    summary: "No load test is needed, and the size is proportionate"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md"
---

# Review: tasks — slice 186

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Rerun path is circular: Task 9.1 and Task 10.1 gate each other

Task 9.1 says a model-judgement outcome in case 2 should be "record it and rerun once on a fresh notes-cli index" (line 231). Line 58 puts that rerun at the next index after 102, which is 103, and the slice design says "a slice is ready only when the next lower index is done" (slice design line 137). So the rerun cannot start until 102 is done. Task 10.1 is the step that drives 102, and it requires "Task 9.1 complete" (line 241). Task 9.1 cannot complete until its rerun does. The loop is 9.1 → 103 → 102 → 10.1 → 9.1.

The same rule blocks a case 1 rerun. A rerun of 100 at index 103 waits on 102, which waits on 101, which waits on the failed 100. The slice design also says "Each case runs once" (slice design line 228) while its body allows a rerun, and the task file inherits that conflict.

Fix: decide where a rerun sits in the order. For example, a rerun is driven after Task 10.2, and it does not gate 10.1. Restate the readiness rule for reruns.

### [CONCERN] Dangling reference to Task 9.3

Line 200 says "drive 101 only after Task 9.3", and line 48 places the PM merge at "Task 9.3". The file has no Task 9.3. The merge is sub-item 8.3 (line 216), and Task 9.1's prerequisite is correctly 8.3 (line 228). A reader following the reference won't find the gate. Change both references to Task 8.3.

### [CONCERN] Task 5's fix commit contradicts the commit cadence

Line 163 says a fix to Task 2 or 4 found in Task 5 is "committed on its own as `fix: {summary}`". The project rules say implementation commits only at the task file's `**Commit**:` markers, and a bug in the slice's own code is part of the slice, not a separate fix. The change should ride the next marker, which is Task 6 (line 181). Remove the separate-commit clause.

### [CONCERN] Branch name and block-resolution command have no stated source

Line 216 tells the PM action to merge `700-slice.<name>` into `main`, but nothing says where `<name>` comes from. Notes-store's request run chooses that name. The 183 design gives the branch as `{cf.index}-slice.{cf.slice_name}` (183 design line 211). The step should say how to find the branch, for example with `git -C D/checkouts/notes-store branch --list '700-slice.*'`, and check that it is the head the done node recorded. Line 218 says "resolve it as the PM" without naming the command. Name the command and check its flags with `--help`.

### [CONCERN] Isolation from the real registry is checked only at the end

The slice design requires that the real registry and supervisor directory are never written (slice design line 38), and that nothing is written outside `D` (line 306). Task 5.1 checks only that the scratch registry lists three projects. Task 4.4's stubs do not assert that every spawned `cf`, `sq` or `amoeba` carries `CONTEXT_FORGE_DATA_DIR=D/cf` and `AMOEBA_STORE_DIR=D/store` (slice design line 223). The only real-registry check is 11.1 (line 257), which runs after all the live spend.

Add to 5.1 a `cf project list` with `CONTEXT_FORGE_DATA_DIR` unset, confirming no scratch project is listed. Add to 4.4 an assertion over the stub call log that each call carries the scratch environment.

### [CONCERN] Tree documents are placed in the wrong directory by the literal text

Line 93 says the tree documents go "under `project-documents/user/` as in `scripts/answerer_walkthrough/project/`". In that tree, the concept and initiative plan are under `project-documents/user/project-guides/`, and the architecture and slice plan are under `project-documents/user/architecture/`. 145's `CF_ARTIFACTS` (`scripts/answerer_walkthrough.py:35-39`) uses the same layout. A junior following the literal text would put the concept directly under `user/`, and `cf set concept` would point at the wrong file. Name the two subdirectories.

### [CONCERN] Dependencies omit 144, which Task 12.1 writes into

The frontmatter lists 145 and 180 to 185. Task 12.1 writes into 144's `tests/live/answering/fixtures/question_tails.json` and runs `test_question_tails_fixture.py`. The five live variables come from 140 and 144 (slice design line 79). Both files exist, and the entry schema (`question`, `run_id`, `captured`, `source`) matches what 12.1 says to write. Add 140 and 144 to the dependencies, and have Task 0.1 (lines 69 to 73) confirm the fixture file and the live variables.

### [CONCERN] Commit markers leave the live evidence uncommitted until the end

Markers sit at Tasks 1, 3, 4, 6 and 12. Tasks 7 to 11 (lines 185 to 259) produce the run ids, edge rows and journal evidence the slice exists to record, and none has a marker. That evidence stays uncommitted until Task 12. Task 12's commit also bundles fixes to the tree and script (line 58 says tree changes "ride in the Task 12 commit"), the LLD amendment (12.3), the captured fixtures and the results, all under `docs:`. Add a marker after Task 11 for the results, and commit code or tree fixes separately with their own type.

### [NOTE] Setup-time `applied` check is dropped, and the LLD still says the opposite

Slice design line 214 (D5) and line 311 require setup to stop unless the registration is `applied`. The task file deviates (line 54), and 145's tasks already record that submissions are applied only by the resident process (`145-tasks` line 121). The deviation is correct, and Task 7.1 (line 193) checks `applied` after start, so the intent is covered. The LLD amendment sits in 12.3 (line 278), so the LLD disagrees with the build for its whole length. Move the amendment into Task 4.3.

### [NOTE] Config write may duplicate 145's template

145's `CONFIG_TEMPLATE` (`scripts/answerer_walkthrough.py:55-68`) already writes the answerer block. Task 4.3 writes a three-project file and does not say whether to extend that template or copy it. Say which. Copying would duplicate the answerer block.

### [NOTE] Some stop conditions are vague

Task 7.1 stops on a member "not readable after a few ticks", which gives no number. Task 5.1 sets the five variables to "the values the earlier live tiers use" without saying where those values are. Give a tick count and name the source.

### [NOTE] The merge sub-item sits in a task file

The project rules say never to write a merge as a task or sub-item. Task 8.3's merge runs in a throwaway checkout, and slice design D4 (line 163) mandates it, so the carve-out is reasonable. The Branch paragraph states the carve-out but cites the non-existent Task 9.3. Once that reference is fixed, the carve-out holds.

### [NOTE] Coverage, test-with pattern and references check out

- Case 1 is covered by 8.1 to 8.3, case 2 by 9.1, and case 3 by 10.1 and 10.2.
- `inspect program` readable is covered by 7.1, final checks by 11.1, docs and LLD by 6.1, 6.2 and 12.3, and captures and fixtures by 12.1 and 12.2.
- D9's edge id is in 183's design (slice 183 line 292), and 0.1 checks it.
- Test-with: 3.1 follows the trees, 4.4 follows the script, and 1.1 keeps 145's test green.
- The cited files exist: `.claude/rules/python.md`, 145's helpers and tests, and the #241 and #284 references (180 and 140 designs).
- Task 0.1 will stop now because 180 to 185 are designed but not merged (projectState, line 14). That is the intended gate.

### [NOTE] No load test is needed, and the size is proportionate

The slice design restates no NFR, and the change touches no simulation, network, concurrency or environment-layer code. No `tests/load/` task or CI gate is needed. The test surfaces (the fixture test, the script test, and 145's test kept green) each map to a criterion. Twelve top-level tasks in one file is proportionate for three live cases.

### Run Digest

- Response length: 10295 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 516273 / 360984 / 155279 / 63525 / not computed
- Duration: 279.1 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
