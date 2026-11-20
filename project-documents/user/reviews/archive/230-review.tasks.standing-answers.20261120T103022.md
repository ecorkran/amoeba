---
docType: review
layer: project
reviewType: tasks
slice: standing-answers
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/230-tasks.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 3732abfd94ad21941973f9f1df61724e428d250e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
effort: xhigh
turns: 32
promptTokens: 1419114
cachedTokens: 1230690
cacheWriteTokens: 188402
completionTokens: 63168
durationSeconds: 272.3
costUsd: 0.300857
costBasis: provider
runId: run-20261120-p5-ebc0a23b
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Section 3 cannot pass its checks: OperationName gains two members before their CLI, docs, dispatch or tool row exist"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:102-105"
  - id: F002
    severity: fail
    category: sequencing
    summary: "Section 5 breaks the prompt tests: `PassageKind` gains STANDING_ANSWER before the prompts name it"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:145-148"
  - id: F003
    severity: concern
    category: consistency
    summary: "The \"must pass unchanged\" instruction for test_parser_names is false, and the named-edit reference points at a missing task"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:204"
  - id: F004
    severity: concern
    category: consistency
    summary: "Standing's optional directory conflicts with the MCP directory-tool invariant"
    location: "tests/mcp_server/test_tools.py:97"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Test task 4.4 is not next to the implementation it tests"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:126-139"
  - id: F006
    severity: concern
    category: coverage
    summary: "Two stated outcomes have no pause-level test"
    location: "tests/operations/test_pause_context_gather.py:218"
  - id: F007
    severity: concern
    category: coverage
    summary: "The \"binds values with `?`\" criterion has no verifying task"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:227"
  - id: F008
    severity: concern
    category: consistency
    summary: "Design line 203 will contradict the code after task 5.1"
    location: "project-documents/user/slices/230-slice.standing-answers.md:203"
  - id: F009
    severity: note
    category: sequencing
    summary: "The 0.1 precondition does not hold for the current tree"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:56"
  - id: F010
    severity: note
    category: consistency
    summary: "Two conditionals leave decisions to the implementer"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:158"
  - id: F011
    severity: note
    category: scope
    summary: "No \"no deferral\" violation: the 231 items are a scope split, not a deferral"
    location: "project-documents/user/slices/230-slice.standing-answers.md:41"
  - id: F012
    severity: note
    category: scope
    summary: "Proportion is right; no NFR, so no load test"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md"
  - id: F013
    severity: pass
    category: consistency
    summary: "The named modules, tests and fixtures exist"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:41"
---

# Review: tasks — slice 230

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Section 3 cannot pass its checks: OperationName gains two members before their CLI, docs, dispatch or tool row exist

Task 3.1 adds `OperationName.STANDING` and `WITHDRAW`, then requires pyright clean, and 3.3 and 3.5 require the full checks to pass. The existing suite requires every `OperationName` to have a CLI command (`tests/cli/test_parser_names.py:36`), a tool row (`tests/cli/test_parser_names.py:41`), a name in `docs/cli-contract.md` (`tests/test_contract_docs.py:143`), and a backticked name in `docs/mcp-server.md` (`tests/test_contract_docs.py:329`). `src/amoeba/wiring.py:258` is an exhaustive `assert_never(name)` over `OperationName`, so pyright fails until the `case` arm exists. Those surfaces land in 4.1 to 4.2 and 8.1, after the section 3 commit marker at line 119. Fix: add each new `OperationName` member in the same task as its wiring arm, parser entry, contract-doc names and MCP tool row. That means either moving the tool rows into section 4 or moving the names into section 8.

### [FAIL] Section 5 breaks the prompt tests: `PassageKind` gains STANDING_ANSWER before the prompts name it

Task 5.1 appends `PassageKind.STANDING_ANSWER`. `tests/answering/test_pipeline_yaml.py:156` requires the exact `KIND_SENTENCES` text in both prompts, `:157-158` requires every `PassageKind` value to appear in both prompts, and `:161-164` requires the kind list to equal the enum order. The yaml and `KIND_SENTENCES` change only in 6.1 and 6.2 (lines 168-173), which come after the 5.3 "checks pass" gate at line 156. Fix: move 6.1 and 6.2 ahead of 5.1, or make the enum addition and the prompt edits one task.

### [CONCERN] The "must pass unchanged" instruction for test_parser_names is false, and the named-edit reference points at a missing task

Task 8.2 says `tests/cli/test_parser_names.py` "must pass unchanged". Adding two `OperationName` members breaks its pinned name set (`tests/cli/test_parser_names.py:52-69`), its `minimal` command dict (`:117-142`), and its set equality over every command (`:138`). The Context Summary (line 49) lists "operation and tool name lists in 7.4 and 8.2" as the allowed edits, but there is no task 7.4. The name-list edit needs to be named in the task that adds the names, and the "must pass unchanged" wording removed.

### [CONCERN] Standing's optional directory conflicts with the MCP directory-tool invariant

Design D2 makes `directory` optional for `standing`, since only `--member` needs it. Task 8.1 (line 198) gives the `standing` tool a `directory` argument. `test_exactly_these_tools_take_a_directory` (`:97`) requires the tools that take a directory to equal `DIRECTORY_TOOLS`. `test_directory_is_required_exactly_for_the_three_directory_tools` (`:132`) requires the directory to be required for exactly those tools. Adding `standing` breaks one of them, and an optional directory contradicts the 226 contract. Decide during planning whether `standing` requires a directory, like `add`, or whether that invariant changes. Task 8.2 (lines 203-205) names only "added functions" for `test_tools.py`, so this edit is not named.

### [CONCERN] Test task 4.4 is not next to the implementation it tests

The test-with pattern breaks in section 4. Tasks 4.2 (CLI) and 4.3 (list view) both come before 4.4, which tests both. Split 4.4 so the CLI tests follow 4.2 and the list-view tests follow 4.3.

### [CONCERN] Two stated outcomes have no pause-level test

The success criterion "when rules and standing answers do not fit the cap, the question waits as `sources_too_large` and the detail gives both shares" is covered only at `assemble` (5.3). Task 5.5 extends `test_pause_context_gather.py`, which already has `test_over_the_limit_is_sources_too_large` at `:218`, but names no assertion that standing answers push a question over the cap, that the question waits, or that the detail carries both shares. Design D10 (line 180) also says a busy or failed store in `handle_pause`'s reach read is exit 3 with no claim written. No task tests that. Add both as named assertions in 5.5.

### [CONCERN] The "binds values with `?`" criterion has no verifying task

The design's technical requirement that every statement binds values with `?` has no check in the task file. The only grep in 10.2 is for `except Exception`. The members AST test (`tests/store/test_members_queried_in_one_place.py`) checks only table names. Add a grep to 10.2 for f-string SQL in the new store modules, and require that new SQL binds values through `?`.

### [CONCERN] Design line 203 will contradict the code after task 5.1

Integration Points says "The `StandingAnswer` type lives in `answering/passages.py`". Task 5.1 puts it in `answering/standing_passages.py`. Task 0.2 amends Component Structure and State Management but does not list this line, so the design stays wrong. Either add it to 0.2's list, or make the design amendments now in the planning commit and drop 0.2. That second option keeps design edits off the slice branch.

### [NOTE] The 0.1 precondition does not hold for the current tree

0.1 requires the design and this file to be committed "with no other uncommitted change". At session start the task file was modified and the review archive `230-review.slice.standing-answers.md` was untracked. The planning commit must land before Phase 6 starts. This rests on the start-of-session git snapshot, since I could not re-check git status.

### [NOTE] Two conditionals leave decisions to the implementer

Task 5.4 splits out `standing_sources.py` "if it passes ~300" lines. `pause_context.py` is already 289 lines and the change adds to it, so decide now. Task 5.5 says to follow the transaction-counting style "if they do; otherwise assert one `store.read()` call". Name the assertion.

### [NOTE] No "no deferral" violation: the 231 items are a scope split, not a deferral

Non-agent pauses are named as out of scope and assigned to 231 by the architecture. That is a split, not a deferral of in-scope behavior. The dead-end note at line 275 says the same thing. No change needed.

### [NOTE] Proportion is right; no NFR, so no load test

About 11 sections, 60 checkboxes and 35 files cover ten design decisions, a new table, two operations, a view, a prompt change, an `rm` hook, MCP tools, docs and a live test. That is proportionate and needs no split beyond the fixes above. The design restates no NFR, so no load-test task is required.

### [PASS] The named modules, tests and fixtures exist

Verified against the repo: migrations 001 to 009 and `EXPECTED_SCHEMA_VERSION: Final = 9` (`src/amoeba/store/migrations.py:25`); `assemble` at `src/amoeba/answering/passages.py:327`, `wiring.py` at 320 lines, `mcp/tools.py` at 262 and `pause_context.py` at 289, matching the departure figures; `apply_removal`, `get_program`, `get_member`, `project_of`, `place_message`, `ListSubject`, `list_view`, `members_view`, `KIND_SENTENCES`, the named answer-settle test, the live pause harness, `asks_question.yaml`, and `scripts/update_live.py`. The one stale reference is "7.4", covered in the parser-test finding above.

### Run Digest

- Response length: 11649 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 32
- Tokens — prompt / cached / cache write / completion / reasoning: 1419114 / 1230690 / 188402 / 63168 / not computed
- Duration: 272.3 s
- Cost: $0.30 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
