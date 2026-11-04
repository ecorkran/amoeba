---
docType: review
layer: project
reviewType: tasks
slice: program-concept-as-a-source
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/182-tasks.program-concept-as-a-source.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: db223c27dab1112efb2890695d3423cf401e7802
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
effort: xhigh
turns: 23
promptTokens: 717669
cachedTokens: 576359
cacheWriteTokens: 141296
completionTokens: 40961
durationSeconds: 219.0
costUsd: 0.160541
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Preamble says no task needs a live model or key, but Task 8.3 does"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:53"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 8.3's live run sits before the commit for 8.1 and 8.2"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:253-257"
  - id: F003
    severity: concern
    category: proportionality
    summary: "`passages.py` is already at its size cap, and Task 4.1 adds to it"
    location: "src/amoeba/runner/answering/passages.py"
  - id: F004
    severity: concern
    category: test-strategy
    summary: "The \"no load test\" decision is not supported by the testing rules"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:55"
  - id: F005
    severity: concern
    category: consistency
    summary: "The design and the task disagree on where `ProgramContext` lives and on `read_program_sources`'s signature"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md:200"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Thirteen commit markers, and one commit that is not yet reachable"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:74"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task 5.4 bundles too many test groups under one effort-4 task"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:170-177"
  - id: F008
    severity: note
    category: coverage
    summary: "Task 6.4 gives no caller search for `AnsweringStage`"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:212-216"
  - id: F009
    severity: note
    category: coverage
    summary: "The D3 timeout path has no test"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:170-177"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md"
  - id: F011
    severity: pass
    category: sequencing
    summary: "The 181 precondition gate matches 181's amended design"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:63-67"
  - id: F012
    severity: pass
    category: test-strategy
    summary: "The purity-check refinement is sound"
    location: "tests/runner/purity.py"
---

# Review: tasks — slice 182

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Preamble says no task needs a live model or key, but Task 8.3 does

Line 53 says "No task needs a model, a key, live CF or `sq`." Task 8.3 (lines 253-255) runs three live answering test files and needs `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD`. I confirmed those names in `tests/live_settings.py`. The design's Integration Requirements (design line 320) require those fixtures to pass. Correct the preamble to name 8.3 as the one task that needs live access.

### [CONCERN] Task 8.3's live run sits before the commit for 8.1 and 8.2

The `**Commit**` marker at line 257 comes after 8.3. If a live variable is unset, 8.3 writes `BLOCKED` and stops, so the finished 8.1 and 8.2 work is never committed. Move the marker to after 8.2, and treat 8.3 as a verification step with its own marker or none.

### [CONCERN] `passages.py` is already at its size cap, and Task 4.1 adds to it

The file is 360 lines today. Task 2.1 sets a limit of "about 375" (line 95), which is already above the ~300-line guideline in CLAUDE.md. Task 4.1 (lines 128-134) adds the program branch of `assemble`: ordering, id assignment and the size rule. Only Task 9.2 measures size, and it says to split "only if clearly over." Design line 99 says `passages.py` "grows only by the member field and one render line," but the design's own component table (line 94) puts the `assemble` change in that file. Move the program ordering and size composition into `program_passages.py` or a helper, and measure the file after 4.1.

### [CONCERN] The "no load test" decision is not supported by the testing rules

The task's factual claim holds: `tests/load/` has no answering coverage. The one "answer" hit in `test_crash_loop.py` is an unrelated stub comment. The rule in `.claude/rules/python.md` (Testing & Quality) requires a load test for code on environment-layer paths, and it says unit and integration tests cannot catch budget overruns. The concept read adds one `cf` call and four git subprocesses per member question, inside the tick. Task 5.4 checks that refused calls return `None`, which tests refusal, not a bound. Either add one `tests/load/` test that asserts the program-side call count and the tick budget for a realistic program, or record why the trigger does not apply. CI already runs `tests/load` as its own step (`.github/workflows/ci.yml:54`), so the task should say the gate already exists rather than leave it implicit.

### [CONCERN] The design and the task disagree on where `ProgramContext` lives and on `read_program_sources`'s signature

Design D7 (line 200) puts `ProgramContext` in `program_passages.py`. The task moves it to `program_sources.py` (lines 48-51). The task's reason is correct: `io_use` in `tests/runner/purity.py` flags a `pathlib` import, and `ProgramContext` holds a `Path`. The design's API sketch (lines 250-252) also omits the `asker` argument that D3's asker case (line 159) needs. The task records both changes, but only in its own preamble. Design line 289 says 185 "reads `ProgramContext` to name a provider," so 185 would look in the wrong module. Amend D7 and the API contract when this lands.

### [CONCERN] Thirteen commit markers, and one commit that is not yet reachable

The file has 10 groups, 26 numbered tasks and 13 `**Commit**` markers, for a slice the design rates at relative effort 2. Two of the markers are weak:
- The 5.1 rig commit has no production change of its own. Fold it into the 5.4 commit.
- The 6.2 commit ("assemble program passages for a program member") is not reachable by a real tick until 6.4/6.5 wire the context. Fold 6.2 into the 6.5 commit.

Folding 8.3 into 8.2 (see the earlier finding) gives about 10 markers.

### [CONCERN] Task 5.4 bundles too many test groups under one effort-4 task

Task 5.4 covers the happy path, commit pinning, committed-only content, target-branch reads, dates, five `read_member` reasons, a failing `cf` read, a failing `git show`, non-UTF-8, size, call counts and budget refusals, all in one commit. Split it into three tasks: (a) happy path, pinning, committed-only and date; (b) failures; (c) size, call count and budget refusals. The "exactly `max_chars`" case in line 175 is not in the design, and the rendered-size rule in 4.2 already owns size, so drop it or move it there.

### [NOTE] Task 6.4 gives no caller search for `AnsweringStage`

Task 6.4 changes the stage's constructor and `run` signature ("both required, no defaults"). Tasks 6.1 and 6.3 give a `grep` for their callers, and 6.4 does not. Add `grep -rn "AnsweringStage(" src tests`.

### [NOTE] The D3 timeout path has no test

Design D3 (line 161) says timeouts follow 143's rules. Task 5.4 tests a failing `git show` but no timeout. Add one timeout case to the failure group, using the same rig.

### [PASS] Success criteria are covered by tasks

- Concept passages dated by the last commit, with uncommitted and untracked files excluded: 5.3, 5.4, 2.2.
- A project in no program is unchanged: 0.2 and 7.1, with the store absent and with an unrelated program.
- `sources_missing`, `sources_unreadable` for each `read_member` reason, and git failures: 5.4 and 6.2.
- No other-member passages (visibility): 7.2, with an allowed-set assertion.
- Size rule, with program passages never trimmed: 4.1 and 4.2.
- Purity of `program_passages.py`: 3.1 and 3.2.
- Budget refusal of each of the five calls returns `None`: 5.4.
- Docs and CHANGELOG: 9.1. Lint and typecheck: 9.2. Live fixtures against the new instructions: 8.1 to 8.3.

Test-with ordering holds, with tests following each implementation task or sharing its commit.

### [PASS] The 181 precondition gate matches 181's amended design

181's design (line 354) and its Task 5.1 (line 191) both keep `Readable`'s checkout and CF project id, so the `BLOCKED` gate in 0.1 is the right check. The slice design (line 68) records 181 as not implemented. I did not check the target branch's code, so the gate is still the only verification of that.

### [PASS] The purity-check refinement is sound

`io_use` flags `pathlib` imports and `open`/`read_text` calls in the module's own AST. Task 3.2 calls it correctly, and the task's reason for moving `ProgramContext` out of `program_passages.py` holds.

### Run Digest

- Response length: 8471 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 717669 / 576359 / 141296 / 40961 / not computed
- Duration: 219.0 s
- Cost: $0.16 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Resolution

- **Preamble says no task needs a live model or key, but Task 8.3 does:** fixed. The Order paragraph now says only Task 8.3 needs live access (models and keys).
- **Task 8.3's live run sits before the commit for 8.1 and 8.2:** fixed. The commit marker now follows 8.2; 8.3 is marked verification only with no commit of its own, so a `BLOCKED` there cannot strand the 8.1 and 8.2 work.
- **`passages.py` is already at its size cap, and Task 4.1 adds to it:** fixed with a measurement. Task 4.1 now requires `wc -l` on `passages.py` (360 before the slice) to be at most 400, and if not, a pure move of the citation check into `citations.py` in the same commit. I did not move the program ordering into `program_passages.py`: it would import `passages` while `passages` imports it, and the ordering is a few lines in `assemble` that reuse `_committed_passages`.
- **The "no load test" decision is not supported by the testing rules:** fixed by reversing the decision. New Task 7.3 adds `tests/load/test_program_passages_load.py` (20 members, a concept of about 100 sections, 30 questions; asserts one `cf` and four git calls per question, the budget stop, and a wall-time bound set from a measured run). The preamble now says CI already runs `tests/load` as its own step.
- **The design and the task disagree on where `ProgramContext` lives and on `read_program_sources`'s signature:** fixed in the design. The LLD's component table, D7, API Contracts and Development Approach now put `ProgramContext` and `AskerReads` in `program_sources.py` and give `read_program_sources` the `asker` argument. The task's refinement note became a one-line alignment note.
- **Thirteen commit markers, and one commit that is not yet reachable:** fixed. The 5.1 rig marker is folded into the 5.4 to 5.6 commit and the 6.2 marker into 6.5's. The 8.3 marker went with the earlier finding. Markers are now 11, counting the new 7.3 test, which shares 7.2's marker.
- **Task 5.4 bundles too many test groups under one effort-4 task:** fixed. Split into 5.4 (success paths), 5.5 (failures) and 5.6 (size, call count, order, budget refusals), with the asker task renumbered 5.7 and its references updated. The "exactly `max_chars`" case is dropped; Task 4.2 owns the rendered-size limit.
- **Task 6.4 gives no caller search for `AnsweringStage`:** fixed. Task 6.4 now gives a `grep` for `AnsweringStage(` and the `run` call sites.
- **The D3 timeout path has no test:** fixed. Task 5.5 adds a timeout case for the `cf` call and one for a git call, each expected `sources_unreadable` with the member prefix.
- **Success criteria are covered by tasks (pass):** no change needed.
- **The 181 precondition gate matches 181's amended design (pass):** no change needed.
- **The purity-check refinement is sound (pass):** no change needed.
