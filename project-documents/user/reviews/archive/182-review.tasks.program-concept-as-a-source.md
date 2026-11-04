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
reviewedSha: a36e78ce9edd06b72e378c134191bc50f53dce41
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 742538
cachedTokens: 590870
cacheWriteTokens: 151654
completionTokens: 61257
durationSeconds: 371.7
costUsd: 0.209682
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: clarity
    summary: "Task 0.1 says change nothing, then tells the implementer to change 181's code"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:62-64"
  - id: F002
    severity: concern
    category: coverage
    summary: "No task runs the live answering fixtures that the criterion names"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:232"
  - id: F003
    severity: concern
    category: consistency
    summary: "Nothing assigns the `member` label to cut concept passages"
    location: "src/amoeba/runner/answering/passages.py:121"
  - id: F004
    severity: concern
    category: coverage
    summary: "The rig spec does not produce every reason that 5.4 tests"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:139"
  - id: F005
    severity: concern
    category: clarity
    summary: "The no-program baseline in 7.1 is undefined"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:212"
  - id: F006
    severity: concern
    category: consistency
    summary: "The CHANGELOG instruction rests on a rationale the project does not use"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:243"
  - id: F007
    severity: note
    category: sequencing
    summary: "Slice 181 is not on main, so Task 0.1 will stop at its gate"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:61"
  - id: F008
    severity: note
    category: clarity
    summary: "Eight implementation groups have no success line"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:99"
  - id: F009
    severity: note
    category: clarity
    summary: "The size limit is applied to raw text in one place and to rendered text in another"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:152"
  - id: F010
    severity: note
    category: clarity
    summary: "Task 5.5 leaves the helper shape open, and 6.1 does not use it"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:168"
  - id: F011
    severity: note
    category: clarity
    summary: "\"One passage per section\" does not say what happens to front matter"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:90"
  - id: F012
    severity: note
    category: coverage
    summary: "The walkthrough asserts call order and early stop, and 5.4 does not"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:155-162"
  - id: F013
    severity: note
    category: coverage
    summary: "The load-test rule may apply to the new subprocess reads"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:195-198"
  - id: F014
    severity: note
    category: proportionality
    summary: "Some steps prescribe mechanism that the slice leaves open"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:197"
  - id: F015
    severity: pass
    category: coverage
    summary: "Functional and technical criteria map to tasks; decisions and exclusions are respected"
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md"
---

# Review: tasks — slice 182

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 0.1 says change nothing, then tells the implementer to change 181's code

Line 62 says to read 181's files and "change nothing". Line 63 says that if `Readable` lacks the checkout and CF id, add those fields to `Readable` and `read_member`, with a test in 181's suite. Line 64 says "Do not edit 181's design." The slice (line 76) says 181's design "is amended to say so", but no task owns that amendment. As written, 182's branch would carry a change to 181's module, and nothing says who writes the design change. Move this change into 181's task list, since 181 owns `read_member`, and make 0.1 verify-only: it writes BLOCKED if the fields are missing. The effort 1 label also does not fit a code change plus a test.

### [CONCERN] No task runs the live answering fixtures that the criterion names

The slice's Integration Requirements (line 320) require that "140's live answering fixtures still pass against the updated instructions." Task 8.2 runs only the live-tier tests that are "runnable offline". `test_live_tier_rules.py` tests settings parsing, not the model-backed answering fixtures. The file does not say whether 9.2's `pytest -q` includes them; I did not verify that. Live runs are pre-authorized, so add a step after 8.1 that runs the live answering fixtures against the new instructions. If the PM wants that check to belong to 186, the slice criterion and this task should both say so.

### [CONCERN] Nothing assigns the `member` label to cut concept passages

`cut_passages(text: str) -> tuple[str, ...]` returns plain strings, so it cannot set `member`. Task 2.1 copies `source.member` in `_committed_passages` (task line 84). Task 2.2 says `cut_passages` yields passages "each carrying the member" (line 90). Task 4.1 says the concept is "cut by cut_passages" (line 120). The slice says `cut_passages` is unchanged (slice line 148). No task says which function builds a member-carrying `Passage` from the concept `SourceFile`. Name one helper that builds passages from a `SourceFile`, copying `member` from it, and use it on both the committed path and the program path. Correct the wording in 2.2.

### [CONCERN] The rig spec does not produce every reason that 5.4 tests

Task 5.1's success line lists four `read_member` reasons: `store_missing`, `unlinked`, `snapshot_missing` and `checkout_unresolved`. Task 5.4 (line 159) needs all five, including `store_unreadable`, and says the rig is how each is produced. 5.1 does not say how to make a store unreadable. Its self-test also duplicates 5.4's per-reason failures and 181's own `read_member` tests. Either make the rig produce all five and say how, or cut 5.1's self-test to the `Readable` case and let 5.4 cover the rest.

### [CONCERN] The no-program baseline in 7.1 is undefined

Task 7.1's third setup is "the baseline built the 144 way". The test must assert identical `passages.md`, `cf` and git call lists, and `passage_index` (success criterion, slice line 304). Task 6.2 points to an existing expected-output fixture, which covers `passages.md` only. Nothing supplies the baseline call list or `passage_index`. A junior AI cannot build this leg as written. Name the fixture file for `passages.md`, and say how the call list and `passage_index` are pinned, whether captured before the change or stored as expected data.

### [CONCERN] The CHANGELOG instruction rests on a rationale the project does not use

Task 9.1 says no "behavior change" line is needed because "no config key is added". `CHANGELOG.md` uses that label for changes with no config key: slice 122 recovery (line 67), slice 127 submitters (line 44), and slice 132 pre-dispatch check (lines 148-149). This slice changes what the answerer reads for every member project, so member projects' answers change. Have 9.1 add one behavior-change line for member projects, and keep "a project in no program is unchanged" (slice line 36).

### [NOTE] Slice 181 is not on main, so Task 0.1 will stop at its gate

A search of `src/amoeba` finds no `ProgramStore`, `read_member`, `Readable` or `ProgramStage`. Task 0.1 will therefore write BLOCKED. That matches the slice (line 68: 182 starts after 181 merges), so the breakdown itself is correct.

### [NOTE] Eight implementation groups have no success line

Tasks 3.1, 4.1, 5.2, 5.3, 6.1, 6.3, 6.4 and 8.1 have no success line. The test task after each one covers its behavior, so this is a clarity point only. Adding a one-line success such as "pyright passes, existing runner tests pass" would help the implementer know when to stop.

### [NOTE] The size limit is applied to raw text in one place and to rendered text in another

Task 5.3's early stop compares raw concept text to `max_chars`. Task 6.1 computes `remaining` from raw project-file text. Task 4.1 (line 121) and slice D5 (line 185) measure rendered passages, which include headers and metadata. The early stop is conservative, so no wrong outcome occurs. But the one-character-margin test in 5.4 can pass while assembly's rendered total still fails. Pin one unit, or state that assembly is the authority at the boundary.

### [NOTE] Task 5.5 leaves the helper shape open, and 6.1 does not use it

Task 5.5 says to expose `without_path(files, path)` "or a field on the result". Task 6.1 says to drop the concept path from `committed.files`, without referencing either. Pick the `without_path` function and have 6.1 call it.

### [NOTE] "One passage per section" does not say what happens to front matter

`cut_passages` cuts before every level 1–3 heading outside fenced code (`passages.py:121-122`). The concept fixture has front matter before its first heading. Task 2.2 does not say whether that text becomes its own passage. Pin the expected count in the test.

### [NOTE] The walkthrough asserts call order and early stop, and 5.4 does not

Verification step 1 (slice line 330) expects "the concept read's order" and "early stop on size". Task 5.4 checks counts and the one-character margin. It does not check the order commit → listing → date → text, or that no read follows the size stop. Add one assertion for each.

### [NOTE] The load-test rule may apply to the new subprocess reads

`.claude/rules/python.md` requires a load test for code on environment-layer paths. The concept read runs git subprocesses and a `cf` call inside the tick's answering launch, which appears to fit. The slice restates no NFR, so the NFR rule does not force a load test here. The file should still say whether existing load coverage reaches this path or why none is needed. I did not check what `tests/load/` covers.

### [NOTE] Some steps prescribe mechanism that the slice leaves open

Task 6.4 prescribes `dataclasses.replace(launch, program=context)` and per-launch construction. Task 8.1 offers a YAML anchor. The slice fixes the contracts (D1, D7, D8), not these mechanics. Low priority, but cutting the mechanics would leave the junior AI room to choose.

### [PASS] Functional and technical criteria map to tasks; decisions and exclusions are respected

- Five functional criteria map to 4.1–4.2, 5.4–5.5, 6.2, 7.1 and 7.2. The two gaps above are the exceptions.
- Technical requirements map to the `io_use` check in 3.2, the call count in 5.4, the rig in 5.1, docs in 9.1, and the full validation in 9.2.
- Each decision D1–D8 has a task. Excluded items (185, edges, issue #27, per-member descriptions) have none, so there is no scope creep.
- Every implementation group is followed by its tests.
- Twelve plain-line `**Commit**:` markers sit at tested points, with no checkboxes: after 1.1, 2.2, 3.2, 4.2, 5.1, 5.4, 5.5, 6.2, 6.5, 7.2, 8.2 and 9.2.
- The dependency order has no cycles.
- Names the tasks rely on exist in `src/amoeba` and `tests/runner`: the 1.1 helpers, `Listings.of`, `read_target`, the git read helpers, `io_use`, `CountingBudget`, `STORE_FAILURES`, the `SourcesProblemKind` members, `passages.py` at 360 lines. The `read_program_sources` signature differs from the slice, but the file documents that refinement.

### Run Digest

- Response length: 11411 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 742538 / 590870 / 151654 / 61257 / not computed
- Duration: 371.7 s
- Cost: $0.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
