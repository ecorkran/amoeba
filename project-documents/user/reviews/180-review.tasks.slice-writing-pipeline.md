---
docType: review
layer: project
reviewType: tasks
slice: slice-writing-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/180-tasks.slice-writing-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 66aba15f946af7bf43689b82f26e1d8690fcf55d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 483041
cachedTokens: 345324
cacheWriteTokens: 137707
completionTokens: 55085
durationSeconds: 245.7
costUsd: 0.16967
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria, technical requirements and walkthrough steps all map to tasks"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies and commit markers are sound"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:48"
  - id: F003
    severity: concern
    category: accuracy
    summary: "Task 4.1 cites a Task 3.3 that does not exist"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:105"
  - id: F004
    severity: concern
    category: completability
    summary: "The reply parser is built and tested on hand-written fixtures, and the real format arrives after the live gate"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:110"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 9.1 exports a placeholder model, which defeats the Task 9.3 gate"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:204"
  - id: F006
    severity: concern
    category: completability
    summary: "Task 9.4 copies replies from runs whose I/O directories are not kept"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:227"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task 7.3 repeats rule tests that the answering tier already has"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:176"
  - id: F008
    severity: note
    category: accuracy
    summary: "Task 2.1's \"no literal elsewhere\" criterion contradicts the YAML"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:83"
  - id: F009
    severity: note
    category: accuracy
    summary: "Task 1.4 would leave a false \"nothing here blocks Amoeba\" claim"
    location: "project-documents/user/notes/001-squadron-dependencies.amoeba.md:41"
  - id: F010
    severity: note
    category: sequencing
    summary: "Task 9.5 has no prerequisite line"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:230"
  - id: F011
    severity: note
    category: completability
    summary: "Two values are left open for the implementer"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:57"
  - id: F012
    severity: note
    category: proportionality
    summary: "Task 9.1 changes six files in one task"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:196"
---

# Review: tasks — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria, technical requirements and walkthrough steps all map to tasks

Real-run criteria (design lines 287–291) map to 9.1 (validate and reject an unknown key), 9.2 (every-run checks) and 9.3 (Cases 1–3). Unit-met criteria (295–297) map to 4.2, 6.2 and 1.2–1.4. Technical requirements (301–306) map to 3.2, 4.2, 5.5, 7.1–7.3, 8.2 and 9.4, with 8.1 and 9.4 covering the process contract. Integration (310–311) is covered by 9.2 (prepare, launch, `poll_run`, parse) and 9.3 Case 1 (`cf list slices`). Walkthrough steps 1–6 map to 8.2, 5.5, 9.1, 6.2, 9.3 and 9.5. No task adds 184 work. The slice restates no NFR, so no load-test task is required.

### [PASS] Sequencing, dependencies and commit markers are sound

Constants in 2.1 come before every task that imports them. The path function in 5.1 comes before its consumers in 5.5 and 6.1. Tasks 1–8 need no Squadron, and Section 9 is gated by a `BLOCKED:` protocol on 9.1 and a prerequisite chain 9.2 → 9.3 → 9.4. Markers sit after 1.3, 1.4, 3.2, 4.2, 5.5, 6.2, 7.3, 8.2, 9.1, 9.3 and 9.5, each at a tested point. Unmarked work (1.1–1.2, 2, 9.2, 9.4) rides with the next marker, which the file allows. Test tasks follow their implementation tasks, and the file is proportionate to the slice as a single task file.

### [CONCERN] Task 4.1 cites a Task 3.3 that does not exist

"as in Task 3.3" refers to a task that is not in the file. Section 3 ends at 3.2. The intended reference is probably 3.1, where `prepare_request_directory` raises on a missing directory. An implementer following the reference will look for a task that is not there. Correct the number.

### [CONCERN] The reply parser is built and tested on hand-written fixtures, and the real format arrives after the live gate

4.2 uses fixtures "hand-written from D7". Real `reply.json` files first appear in 9.3, and 9.4 captures them. The project's parser rule requires fixtures in the format production will consume. The file also has no step for a real reply that does not match D7's shape. 9.3 says to record a finding and not loosen the test, but nothing says to revise `read_reply` or its fixtures. Add that step: when a captured reply fails D7, `read_reply` and its fixtures are revised in 9.4 and the failed 9.3 case is re-run.

### [CONCERN] Task 9.1 exports a placeholder model, which defeats the Task 9.3 gate

9.1 says to "export both variables first, any model value". 9.3 blocks only when `AMOEBA_LIVE_REQUEST_MODEL` is unset in the session's environment. After 9.1 it is always set, so 9.3 would run paid cases against a placeholder alias and fail, instead of stopping on `BLOCKED:`. Set both variables inline on the 9.1 command only, so the session environment stays unset until a real alias is available.

### [CONCERN] Task 9.4 copies replies from runs whose I/O directories are not kept

9.2 places the I/O directory under `tmp_path`, and 9.3 does not say to keep it. 9.4 then says to copy `reply.json` "from passing runs", which leaves the implementer guessing where those files are. The design's walkthrough runs with `--basetemp=/tmp/request-live` for this reason (design line 339), and the task omits it. Name that flag in 9.3, or state where the harness keeps each I/O directory.

### [CONCERN] Task 7.3 repeats rule tests that the answering tier already has

The request reader reuses `require_variable` and the cost rule (design D10). `tests/runner/answering/test_live_tier_rules.py:35-43` already covers blank-counts-as-missing and rejects `abc`, `0`, `-1`, `nan` and `inf` through that shared rule. 7.3 asks for the same cases again. Keep one parametrized test per request variable (a missing variable is named, and a bad cost names `AMOEBA_LIVE_REQUEST_MAX_COST_USD`) plus the source-text check, and drop the repeated rule cases.

### [NOTE] Task 2.1's "no literal elsewhere" criterion contradicts the YAML

The YAML has to spell out the paths, the commit message, the param names and the step names. 5.1 copies them from `pipeline_file.py`, and 5.5 asserts they match. Reword the criterion to exempt `slice_writing.yaml`, which 5.5 pins to these constants.

### [NOTE] Task 1.4 would leave a false "nothing here blocks Amoeba" claim

The Net line begins "**nothing here blocks Amoeba.**" Once S16 gates 184, that sentence is false. 1.4 says only to "update … to say S16 gates 184". Say to replace the first sentence.

### [NOTE] Task 9.5 has no prerequisite line

9.2–9.4 each name their prerequisite, and the file's rule says later Section 9 tasks do. 9.5 does not. The file order makes it correct, but add "Prerequisite: 9.4 is checked." for consistency.

### [NOTE] Two values are left open for the implementer

1.1 does not say how a run param is written inside a `paths` entry. The file's brace convention suggests `{requests-index}`, but nothing confirms it, and 1.1 is the task that checks it. 2.1 asks for "a nominal cost cap" without a value, and the walkthrough uses 1. Name the syntax to try first and the cap value.

### [NOTE] Task 9.1 changes six files in one task

9.1 edits the YAML, `pipeline_file.py`, the probe, two test files and the process contract, and adds a live test. Its shape depends on the shipped syntax, so it is hard to size in advance. It is not required, but if a session finds it too large, the natural split is (a) finalize the syntax and re-run the unit tests, and (b) the live validation test and removing the provisional marking.

### Run Digest

- Response length: 7876 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 483041 / 345324 / 137707 / 55085 / not computed
- Duration: 245.7 s
- Cost: $0.17 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Resolution

- [pass] Success criteria, technical requirements and walkthrough steps map to tasks: no change needed.
- [pass] Sequencing, dependencies and commit markers are sound: no change needed.
- [concern] Task 4.1 cites a Task 3.3 that does not exist: changed the reference to Task 3.1.
- [concern] Reply parser built on hand-written fixtures: partly accepted. The real format cannot exist before the live gate, so no reordering. Task 4.2 now says the fixtures are hand-written from D7. The live cases (9.4) parse real replies with `read_reply`, and Task 9.5 adds captured replies and says to fix `read_reply` if one does not parse.
- [concern] Task 9.1 exports a placeholder model, defeating the 9.3 gate: the placeholder values are now set inline on the pytest command only (Task 9.2, and the collect-only check in 9.3), with an explicit "do not export". Task 9.4's gate now checks the shell's own environment.
- [concern] Task 9.4 copies replies from runs whose I/O directories are not kept: the live cases (now 9.4) run with `--basetemp=/tmp/request-live`, note the path, and Task 9.5 copies from those kept directories.
- [concern] Task 7.3 repeats rule tests the answering tier has: `_read_cost` is made to take the variable name so both readers share it (7.2). Task 7.3 now tests only the missing-variable naming and one invalid cost for the new variable.
- [note] Task 2.1's "no literal elsewhere" criterion contradicts the YAML: reworded to cover Python files outside `pipeline_file.py`. The YAML repeats the names and Task 5.5 asserts they agree.
- [note] Task 1.4 would leave a false "nothing here blocks Amoeba" claim: Task 1.4 now says to rewrite the Net line, with S16 gating slice 184 and nothing else blocking.
- [note] Task 9.5 has no prerequisite line: added to the final check (now 9.6).
- [note] Two values left open: Task 1.1 names `{requests-index}` as the first form to try in `paths`. Task 2.1 fixes the commit message, the option names (`--io-dir`, `--max-cost`) and the probe cap (1 USD).
- [note] Task 9.1 changes six files: split into 9.1 (release check, YAML, constants, probe argv, two test files) and 9.2 (live validation test and the contract's final argv), each with its own commit marker. Section 9 is renumbered to 9.1 to 9.6 and the references are updated.
