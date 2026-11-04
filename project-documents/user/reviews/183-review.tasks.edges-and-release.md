---
docType: review
layer: project
reviewType: tasks
slice: edges-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/183-tasks.edges-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 90ad0c0185ada97640a4c9321301b459be78e29e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 561485
cachedTokens: 384205
cacheWriteTokens: 177270
completionTokens: 79799
durationSeconds: 405.8
costUsd: 0.252909
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Release loop iterates over a set that never holds satisfied-only nodes"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:218"
  - id: F002
    severity: concern
    category: design-consistency
    summary: "A coordinator-resolved block closes open edges, which the transition rule forbids"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:210"
  - id: F003
    severity: concern
    category: requirements-coverage
    summary: "The release line for a from-release commit target is undefined"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:207"
  - id: F004
    severity: concern
    category: requirements-coverage
    summary: "Precedence of `read_failed` against `awaiting_release` is unstated for from-release edges"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:196"
  - id: F005
    severity: concern
    category: load-testing
    summary: "No load test covers per-tick edge observation cost"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:273"
  - id: F006
    severity: concern
    category: verifiability
    summary: "Walkthrough steps 1 and 2 omit files and selectors they claim to prove"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:439"
  - id: F007
    severity: concern
    category: verifiability
    summary: "Step 4's crash variants are excluded, and step 5 has no setup"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:237"
  - id: F008
    severity: concern
    category: sequencing
    summary: "Three tasks ship an empty placeholder into `tick.py`"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:145"
  - id: F009
    severity: concern
    category: task-scope
    summary: "Two tasks are too large to review as one step"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:133"
  - id: F010
    severity: note
    category: task-scope
    summary: "Some test items duplicate others or go beyond the criteria"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:253"
  - id: F011
    severity: note
    category: sequencing
    summary: "181 is not on the target, so Task 0.1 will stop"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:63"
  - id: F012
    severity: note
    category: task-scope
    summary: "`tick.py` is already over the size guideline"
    location: "src/amoeba/runner/tick.py:1"
  - id: F013
    severity: pass
    category: requirements-coverage
    summary: "Functional and technical criteria are covered by tasks"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:16"
  - id: F014
    severity: pass
    category: verifiability
    summary: "Code claims in the task file match the repository"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:16"
  - id: F015
    severity: pass
    category: commit-cadence
    summary: "Commit markers sit at working, tested points"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:72"
---

# Review: tasks — slice 183

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Release loop iterates over a set that never holds satisfied-only nodes

Task 7.3 (lines 214–215) defines `waiting` as the node ids with an `open` edge, and its test says `waiting` "holds only `open` edges". Task 7.4 (line 218) then says "for each waiting node whose edges are all `satisfied`: `submit_release`". A node whose edges are all satisfied has no open edge, so it is never in `waiting` and the loop body never runs. Criterion F5 (slice design line 410) cannot happen. The slice design has the same wording at line 136 beside `waiting = node ids with an open edge` at line 138. Fix: have 7.4 iterate over the nodes of `edges_waiting(project_id, {open, satisfied})`, grouped by node, and release a node when none of its edges is `open`. Keep `waiting` open-only for readiness (slice design line 182). Add a 7.4 test that fails if the loop reads `waiting`.

### [CONCERN] A coordinator-resolved block closes open edges, which the transition rule forbids

Task 7.2 applies "resolved by coordinator: released" to every "open or satisfied" edge. Task 1.5 (line 94) makes "released straight from open" raise, following D1 (slice design line 173). So an open edge on a coordinator-resolved block makes the stage raise. The slice design's D9 (line 254) has the same contradiction. The coordinator branch exists only to finish a crash after step 2, and step 2 requires satisfied edges. Fix: limit the coordinator branch to `satisfied` edges, and make an `open` edge on a coordinator-resolved block an explicit error, not a guessed transition.

### [CONCERN] The release line for a from-release commit target is undefined

Task 7.1 says "one line per satisfied edge by its target kind and mode" and asks for the text of "each of the three line shapes". Four combinations can be satisfied: ProvidingSlice × from_source, ProvidingSlice × from_release, ProvidingCommit × from_source, and ProvidingCommit × from_release. The slice design's D7 (lines 232–234) covers the first three. The fourth is reachable: task 6.2 tests "commit target with and without confirmation" (line 186). But shape 2 reads "now on its target <target>", and a from-release edge has no target (`satisfied_target` is None, D4). Fix: define the fourth line, or a rule for which shape applies.

### [CONCERN] Precedence of `read_failed` against `awaiting_release` is unstated for from-release edges

Task 6.4 says a failed head read makes the edge "wait `read_failed` meanwhile". Task 6.2 makes an unconfirmed from-release edge on a done slice wait `awaiting_release`. For an unconfirmed from-release edge whose head read failed, the D10 order (slice design line 262, with `awaiting_release` at line 269) puts `awaiting_release` first. The D10 row for `branch_head_missing` (line 268) reads "Done with no recorded commit", which also matches a failed read. Task 6.1 correctly adds "and missing". Fix: state the precedence in 6.4 and add a from-release case to 7.9. Line 240 says "with no PM step", which suggests only the from-source case was meant.

### [CONCERN] No load test covers per-tick edge observation cost

The slice design restates a per-tick cost bound (slice design lines 508–509): one program-store read per member, plus one read-only open, one `cf` call and one git call per open edge after `done`, all under the tick budget. Task 9.1 runs three existing load tests, and none creates an edge, so none exercises this new cost. Add a task for `tests/load/test_program_edges_load.py` that runs a realistic number of open edges and bounds per-tick subprocess calls and elapsed time under the budget. CI needs no new wiring: `.github/workflows/ci.yml:54` runs `uv run pytest tests/load`, so the new file is gated. The task should say so rather than leave it implicit.

### [CONCERN] Walkthrough steps 1 and 2 omit files and selectors they claim to prove

Step 1's expected output includes `resolve_edge` applied and each rejection, and `member_referenced` over edges. Those tests live in `tests/store/test_program_apply_resolve_edge.py` (task 2.2, line 115) and `tests/store/test_program_reject_program.py` (task 1.6, line 102). Neither is in step 1's path list. Step 2's expected output includes "an applied resume resolution produces no `ResumeRun`". Task 4.1 (line 149) puts that test in `tests/runner/resolutions/`, which step 2 does not run. Step 2's `-k "waiting or external"` depends on test names no task prescribes. If nothing matches, pytest runs no tests, and 9.2 shows nothing. Fix: add the two files to step 1, add `tests/runner/resolutions` to step 2, and have tasks 2.2 and 4.1 name their tests so the `-k` filter selects them. Task 9.2 (line 276) should state the file and selector lists.

### [CONCERN] Step 4's crash variants are excluded, and step 5 has no setup

The slice design's step 4 (line 466) lists "a crash after each release write" among the variants in `test_release_scenario.py`. Task 7.8 (line 237) says the crash points "are not repeated here", so that file won't show them. Task 9.2 (line 276) runs step 5 against the directory the scenario keeps, but never says to run the scenario with `AMOEBA_KEEP_SCENARIO_DIR` set first, so there is no directory to inspect. Fix: add the crash variants to 7.8, or amend the walkthrough step. In 9.2, run `AMOEBA_KEEP_SCENARIO_DIR=$(mktemp -d) uv run pytest tests/runner/program/test_release_scenario.py` before step 5.

### [CONCERN] Three tasks ship an empty placeholder into `tick.py`

Tasks 4.1 (line 145), 5.3 (line 165) and 5.4 (line 172) pass `frozenset()` from `tick.py` as a placeholder, to be replaced in 7.5. An empty set means "no providing slices", so head recording would be skipped without error if the placeholder were left in. CLAUDE.md forbids silent fallbacks. The cause is ordering: the `ProgramView` that yields `providing` (7.2) comes after the tasks that consume it. Fix: move the `ProgramView` skeleton (`program`, `waiting`, `providing`) from 7.2 to just before 4.1, so the tick reads a real view from the first commit that needs one.

### [CONCERN] Two tasks are too large to review as one step

Task 3.3 (effort 4) bundles `submit_release`, the new `AnsweredBy` value, and three pins on 140 readers (the answer limit, the precedent source, and finish settlement). The reader pins touch three other modules and fail for different reasons. Split them into a task 3.4 after 3.3. Task 7.7 (line 232) is effort 5 and builds the two-store support module, the fake `sq` setup, the kept-directory hook and the whole main path in one step. Split the support module and the kept-directory hook into a step that ships first, so 7.8 and 7.9 reuse a verified fixture.

### [NOTE] Some test items duplicate others or go beyond the criteria

- Task 3.2 (line 128) asserts `slice_heads` is absent from the program schema. Task 8.2 (line 252) adds the same check to the locality proof. Keep one.
- Task 8.2 (line 253) adds negative tests of the oracle. Criterion-wise, the proof must cover `edges` and `slice_heads`, which a positive check covers. Cut these or keep them on purpose.
- Task 4.1 (line 147) asks for a deliberate import to be reverted to show the boundary test fails. That checks the test, not a criterion.
- Task 2.1 (line 111) repeats blank-value and missing-flag behavior that the generic submit flags already have. Keep only the `resolve-edge` command test unless the existing tests lack that coverage.
- Task 5.1 (line 155) is effort 1 and one function. Merging it into 5.2 removes a group with no commit of its own.

### [NOTE] 181 is not on the target, so Task 0.1 will stop

`src/amoeba/**/*program*` matches no files, so `program/`, `store/program_schema/` and `runner/program/` are absent, as `projectState` says. Task 0.1 will write BLOCKED. That is correct behavior and not a defect in the file. It does mean every 181 name in this file is unverified, and the file cannot start until 181 merges. The slice design says 182 may merge first. If it lands before 0.2 (line 67), the pinned baseline literals may need re-pinning, so 0.1 should check 182's status too.

### [NOTE] `tick.py` is already over the size guideline

`tick.py` is 311 lines against the ~300 guideline. Task 7.5 (line 222) extracts a helper only "if this grows `tick.py`", but 183 adds call sites in at least four tasks (4.1, 5.3, 5.4, 7.5). Make the extraction a required step in 7.5.

### [PASS] Functional and technical criteria are covered by tasks

Each of the 13 functional criteria (slice design lines 406–418) maps to a task: readiness and no-write resume (4.1, 7.5); `done` heads on both paths (3.2, 5.3, 5.4); from-source reachability (6.3); from-release confirmation (2.2, 6.2); release and `COORDINATOR` (3.3, 7.4, 7.7); supersession (7.2, 7.8); the resume-failed payload (7.6); crash points (7.4); `member_referenced` (1.6); `program-blocked` (8.1); write-on-change (1.5, 7.3, 7.9); `read_failed` retry (6.4, 7.9); no-program regression (0.2, 7.5). Technical criteria are covered too: call counts and budget refusals (6.3), git-backed fixtures (5.2, 6.3), purity (7.1), locality (8.2), and the three contract docs plus CHANGELOG (8.3–8.5, 9.3). Dependencies are acyclic.

### [PASS] Code claims in the task file match the repository

Verified: schema head is 015 (`store/schema/015_answering_run.sql`); `LifecycleTree.ready_slices` takes no argument (`runner/lifecycle/tree.py:96`); `current_slices(tree, index)` takes two (`runner/intent/governance.py:73`); `AnsweredBy` has only `ANSWERER` and `PM`; `record_runner_report` has no `branch_head`. These exist as the tasks use them: `COUNT_ANSWERER_ANSWERS_IN_RUN`, `ANSWER_DECISION`, `_write_resolution`, `SubmissionWriter`, `read_target`, `is_ancestor_args`, `PARAM_CHECKOUT`, `STORE_FAILURES`, `SUBMISSION_REFUSED = 9`, `add_payload_flags`, `log` in the git allowlist, `AMOEBA_STORE_DIR`. `resolve_checkout` is still in `runner/dispatch/checkout.py`, which 181 moves. The bare pytest run excludes `tests/load` (`pyproject.toml:66`), as 9.1 says. Task 7.5 names `tick_rig.py` without its path, which is `tests/runner/dispatch/tick_rig.py`.

### [PASS] Commit markers sit at working, tested points

Markers follow each working, tested group, and every top-level task is covered by one: 0.2, 1.5, 1.6, 2.2, 3.2, 3.3, 4.1, 5.3, 5.4, 6.2, 6.4, 7.5, 7.9, 8.2, 8.5, 9.2 (conditional), 9.3. Test steps directly follow their implementation. Line 255 has no blank line before its marker, so it renders inside the 8.2 bullet. Add a blank line.

### Run Digest

- Response length: 13209 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 561485 / 384205 / 177270 / 79799 / not computed
- Duration: 405.8 s
- Cost: $0.25 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
