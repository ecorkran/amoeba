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
reviewedSha: 7e45a88a50dd56637c117f8065e25fc3e9671dbd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 351854
cachedTokens: 213821
cacheWriteTokens: 138025
completionTokens: 47730
durationSeconds: 212.0
costUsd: 0.140402
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: spec-coverage
    summary: "Live cases do not check the clean tree or the plan read after every run"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:210"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`read_reply` reports a wrong directory as `missing`"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:104"
  - id: F003
    severity: concern
    category: spec-gap
    summary: "The first required param is not stated, but the launch argv depends on it"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:121"
  - id: F004
    severity: concern
    category: ambiguity
    summary: "Task 7.1 says to move code into a file that already exists"
    location: "tests/live/answering/conftest.py"
  - id: F005
    severity: concern
    category: sequencing
    summary: "`BLOCKED:` lines are static, their clearing condition is unstated, and the failure branches are incomplete"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:191"
  - id: F006
    severity: concern
    category: ambiguity
    summary: "The write step has no instruction when the entry exists but the slice plan does not"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:130"
  - id: F007
    severity: note
    category: test-design
    summary: "The prompt-hygiene brace rule is stricter than the design"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:139"
  - id: F008
    severity: note
    category: git-workflow
    summary: "Task 1's planning edits land on the slice branch"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:66"
  - id: F009
    severity: note
    category: risk
    summary: "The commit guard's slice-plan glob depends on a param Squadron may not substitute"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:123"
  - id: F010
    severity: note
    category: success-criteria
    summary: "Task 9.3's success criterion is partly unobservable"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:206"
  - id: F011
    severity: note
    category: task-sizing
    summary: "Task 5.2 is the largest step"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:127"
  - id: F012
    severity: pass
    category: spec-coverage
    summary: "Success criteria and technical requirements are covered"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md"
  - id: F013
    severity: pass
    category: scope
    summary: "No scope leaks into 183 or 184"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md"
  - id: F014
    severity: pass
    category: sequencing
    summary: "Sequencing, commit markers and proportionality are sound"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:70"
---

# Review: tasks — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Live cases do not check the clean tree or the plan read after every run

The slice's Success Criteria (slice line 290) require that after every run there is at most one new commit touching only the two plan files, and no tracked or untracked change in the checkout. Case 1 asserts both. Case 2 asserts only that the commit touches the slice plan, with no `git status --porcelain` check. The harness in 9.3 (line 205) asserts after each run only the prompt file and that no I/O file is in the checkout. The slice's Mitigation (slice line 370) says the live tier checks the `cf list slices` read after every case. Case 2 has no such check. Have the harness assert a clean tree and at most one new commit after every run, and add `cf list slices <requests index> --json` to Case 2, expecting one new entry at the reply's index.

### [CONCERN] `read_reply` reports a wrong directory as `missing`

Task 4.1 says that when no file is present, the result is `missing`. It does not say what happens when the directory itself is absent or is not a directory. As written, a path error in 184 would come back as an ordinary model outcome (`ReplyProblem(missing)`), which is the silent fallback CLAUDE.md forbids. The slice's "never raises" rule (slice line 198) covers model output only. A missing directory is a programming error, like the refusals in `prepare_request_directory`. State that `read_reply` raises when the directory is absent, and add a test.

### [CONCERN] The first required param is not stated, but the launch argv depends on it

Task 5.1 says "two required params with no default" and gives no order. The slice design (line 265) makes `requests-index` the first required param, because the launch argv passes it as the positional target, and `model` goes in `-p`. An agent that declares `model` first produces a pipeline that 184's argv cannot launch. Task 5.3's params test would also still pass if it checks presence only. Add the order to 5.1 and assert it in 5.3.

### [CONCERN] Task 7.1 says to move code into a file that already exists

The file already exists. It defines `live_harness`, which takes `live_settings`, and imports `LiveHarness` and `LiveSettings`. Task 7.1 (line 163) says to move the collection-time read and the `live_settings` fixture "unchanged" into it, without saying to merge with existing content. Recreating the file would drop `live_harness` and break the answering tier. After the move, `tests/live/conftest.py` will also have unused `os`, `pytest` and `LiveSettings` imports, which fail the `ruff check` in 8.2. The `sys` and `Path` imports stay for the `sys.path` line. Tell the agent to append to the existing file, keep the `sys.path` insertion in the root conftest, and remove the unused imports.

### [CONCERN] `BLOCKED:` lines are static, their clearing condition is unstated, and the failure branches are incomplete

Task 9.1 says "`BLOCKED:` waits on a Squadron release", then "If it exits 0... continue." The file does not say who removes the line or when an agent should re-run the check. Line 48 says work "stops at Task 9.1" while the line holds, so an agent that reads the line stops without running the check that would release it. Also, a Squadron release is an external dependency, not something only the Project Manager can clear, which is the case `BLOCKED:` is defined for. The failure branches are also incomplete: 9.1 covers an unknown `commit` step or option, but not `sq` missing or any other non-zero exit. Have the agent run the check first. Write `BLOCKED:` only when the check fails with the named error, state that the check is re-run on resume and the line removed when it passes, and say what any other failure means.

### [CONCERN] The write step has no instruction when the entry exists but the slice plan does not

Task 5.2 creates the slice plan only when the initiative plan has no entry at the requests index. If the entry exists and the slice plan file is missing, the prompt says nothing. The slice design (line 142) says the agent creates the slice plan "to create it or add one entry", which covers this case. The task narrows the design without saying so. No live case exercises this branch: Case 1 creates both files, and Case 2 reuses them. State the case in the prompt and say which index the new entry takes.

### [NOTE] The prompt-hygiene brace rule is stricter than the design

Task 5.3 requires "every brace pair in the prompt is a real param name". The slice design (line 238) bars only a brace pair around a bare word. Read literally, any JSON reply example in the prompt fails the test. Task 5.2 (line 135) already asks for the reply shapes to be described in words, so the two are consistent, but either the test should use the design's rule or the task should say JSON braces are excluded on purpose.

### [NOTE] Task 1's planning edits land on the slice branch

Task 1.3 edits the architecture file and the dependency register. Its commit (line 70) lands on the slice branch, as line 44 requires for all implementation. The Git rules say planning artifacts commit directly to the integration target. Either way the change merges at Phase 7, but until then the target does not show the issue numbers. Decide which applies and state it in the task.

### [NOTE] The commit guard's slice-plan glob depends on a param Squadron may not substitute

Task 5.1 builds the slice-plan glob from `requests-index` and defers whether Squadron substitutes params in `paths` to Task 9.1. The design uses the same form (slice line 144), and neither says what the guard does if substitution is unsupported. A fixed wider glob would let the commit step touch any slice plan, which weakens the guard in D5. Name the fallback now. Widening the guard is a design change, not a task-level choice.

### [NOTE] Task 9.3's success criterion is partly unobservable

"The helper itself needs no model" is a property of the code, not an observable result. The other part, that a run which fails to start reports the `sq` output, is observable. Keep the observable part, or replace the first with a concrete check such as the harness reading no model settings.

### [NOTE] Task 5.2 is the largest step

One prompt covers about nine behaviors: scope, the two globs, initiative creation, the entry's index and form, the dependency rule, forbidden actions, the `cf list slices` loop, the already-met rule and the reply. It is effort 4 and is verified mainly by reading ("all items above are in the text"). It is one file, so splitting would add a commit boundary without an independent result. Keep it as one task, but give it a checklist, and have 5.3 test the checkable parts: both globs, the `cf list slices` command and the forbidden-write list.

### [PASS] Success criteria and technical requirements are covered

Real-run criteria map to 9.2 (validate), 9.4 (Cases 1 to 3) and the 9.3 harness. Unit-tier criteria map to 4.2 (`read_reply`), 6.2 (probe) and 1.2 and 1.3 (the issue and the register). Rendering and refusals map to 3.2 and 3.4, the names-match test to 5.3, the wheel to 5.3, collection to 7.2 and 7.3, format, lint and pyright to 8.2 and 9.6, the process contract to 8.1 and 9.5, and captured fixtures to 9.5. The gaps are the two in findings 1 and 2. The slice restates no NFR, so no load test is required.

### [PASS] No scope leaks into 183 or 184

Every item in the slice's Excluded list (slice lines 60–68) is absent from the tasks. The one wiring-related item, the probe's start-up call, is explicitly deferred to 184 (6.1). Each task traces to a design item.

### [PASS] Sequencing, commit markers and proportionality are sound

Dependencies run forward with no cycles: constants (2.1) before their users, input and reply before the probe, YAML (5.1) before its prompt (5.2) before its tests (5.3), and the live tier after the Squadron gate. Commit markers at lines 70, 98, 115, 144, 158, 174, 186, 200, 214 and 225 fall at tested points. Task 2.1 has no marker of its own and is committed with section 3, which is fine. Tests follow their implementation (3.2, 3.4, 4.2, 5.3, 6.2, 9.2, 9.4). The file has 26 tasks in 9 sections, which fits the roughly six new modules and eight or more test files the slice involves. It is a single file, so no split is needed.

### Run Digest

- Response length: 10593 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 351854 / 213821 / 138025 / 47730 / not computed
- Duration: 212.0 s
- Cost: $0.14 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
