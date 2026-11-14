---
docType: review
layer: project
reviewType: tasks
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/227-tasks.program-dependencies.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 2bf1fac346ca1520e4ae73a827fa9508ecb1d1ff
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
effort: xhigh
turns: 30
promptTokens: 955620
cachedTokens: 754345
cacheWriteTokens: 201261
completionTokens: 74651
durationSeconds: 318.7
costUsd: 0.297234
costBasis: provider
runId: run-20261114-p5-0e7feed2
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: design-rule
    summary: "Removed members' reports have no exit or cleanup, and the design calls them both bounded and unbounded"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:253"
  - id: F002
    severity: fail
    category: sequencing
    summary: "Task 2.2 breaks an exact-set test that no task edits, and the 6.3 diff check contradicts the fix"
    location: "tests/operations/test_decisions_request.py:102"
  - id: F003
    severity: concern
    category: size
    summary: "`wiring.py` is already over the 300-line limit, and 4.1 adds to it with no split"
    location: "src/amoeba/wiring.py"
  - id: F004
    severity: concern
    category: size
    summary: "Section 4 is one oversized unit with a red suite, and the renderer step can move out"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:142"
  - id: F005
    severity: concern
    category: clarity
    summary: "The live-test helper plan does not say both members must share one data directory and `AMOEBA_HOME`"
    location: "tests/live/pause/harness.py:89"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 0.1 checks 226 and 229 only, although its context says 224 and 228 are checked too, and it does not commit the planning documents before branching"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:57"
  - id: F007
    severity: concern
    category: clarity
    summary: "The section 4 preamble misquotes D7 and contradicts 4.1 and 6.3"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:144"
  - id: F008
    severity: note
    category: completeness
    summary: "Adoption in member repos is not scheduled and not marked out of scope"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:244"
  - id: F009
    severity: note
    category: clarity
    summary: "The flow test does not say how the block's commands are located or run"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:201"
  - id: F010
    severity: note
    category: coverage
    summary: "The two-worktree criterion is covered at the mechanism level only"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:135"
  - id: F011
    severity: pass
    category: coverage
    summary: "Every success criterion maps to at least one task"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:36"
  - id: F012
    severity: pass
    category: sequencing
    summary: "Test-with pattern, commit markers and file count are sound"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:90"
  - id: F013
    severity: pass
    category: scope
    summary: "Scope additions are required by existing code or tests"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:45"
  - id: F014
    severity: pass
    category: design-rule
    summary: "No deferral, no waiting on use, no hallucination traps, and the parent edits are in place"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:178"
---

# Review: tasks — slice 227

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Removed members' reports have no exit or cleanup, and the design calls them both bounded and unbounded

The end state says a removed member's reports "stay in the table ... no cleanup removes them ... the growth is slow, not bounded." Line 120 is headed "Rows are bounded," then says rows "grow with the member's merges and releases." Neither names a cleanup or a bound, which the Amoeba design rules require ("Anything the system writes either has a named cleanup or the design says why it is bounded"). These rows also have no exit. Task 2.4 runs `resolve_member` before the write (tasks:114), so `withdraw` returns `not_a_member` for a removed member, and `rm --pair` removes only pairs. The breakdown has no cleanup task, so an implementer would build this as written. Fix the design first, then add a task. Either name a cleanup at a named point (the codebase already runs a prune pass from `status` at `src/amoeba/operations/status.py:191`, keyed on `prune_after_days`; the design should say whether it covers releases of members with no pairs), or state a real bound and what happens when it is hit.

### [FAIL] Task 2.2 breaks an exact-set test that no task edits, and the 6.3 diff check contradicts the fix

`test_the_rejection_codes_are_the_three_the_design_names` asserts that the `RejectCode` values are exactly three codes. Task 2.2 adds `NOT_A_MEMBER` and `NOT_REPORTED` (tasks:101) and requires the four checks to pass at its commit (tasks:103, marker at :105). That test fails at 2.2. Task 4.1 (tasks:148) lists the only existing-test edits, and 6.3 (tasks:216) says the only existing tests edited are those in 4.1 and that `git diff {target} -- tests/operations/test_decisions*.py` is empty. The glob matches this file, so 6.3 fails once 2.2 is fixed. Fix: list this file under 2.2, update its expected set, and change 6.3 to name it as the one exception.

### [CONCERN] `wiring.py` is already over the 300-line limit, and 4.1 adds to it with no split

The file has 324 lines. The tasks state the limit (tasks:50: "split a module that grows past that"), yet 4.1 (tasks:149) adds two result types to `OperationResult`, two `invoke` cases and two `is_rejected` members, with no split step. `src/amoeba/mcp/tools.py` is at 260 lines, and 4.4's two rows with advice and descriptions could push it near 300. Add a split to 4.1 (for example, move the release cases into a module that `invoke` dispatches to), or record the exception and why it is acceptable.

### [CONCERN] Section 4 is one oversized unit with a red suite, and the renderer step can move out

Section 4 has five subtasks, about 17 bullets and about 15 files, with one commit at the end (tasks:176). The suite is red from 4.1 to 4.5 by design (tasks:144). Step 4.3 does not depend on the names: `render_result` picks the renderer by result type (`src/amoeba/cli/render/dispatch.py:56-70`). Moving 4.3 and the `OperationResult` union edit from 4.1 into a green group after section 3 gives a commit at a tested point and shrinks the red window to 4.1, 4.2, 4.4 and 4.5. The single commit for the names can stay.

### [CONCERN] The live-test helper plan does not say both members must share one data directory and `AMOEBA_HOME`

`build_world` places `cf-data` under `parent`, sets `CONTEXT_FORGE_DATA_DIR` and `AMOEBA_HOME` for that world, and adds the member with the module constants `PROGRAM_ID` and `CF_PROJECT_NAME` (lines 89–105). Task 6.2 (tasks:209) asks the implementer to extend it so a second member joins the same program, and leaves the method open. The consumer's `changes` must name the provider through `cf list projects` (tasks:210), which works only if both members share one Context Forge data directory and one `AMOEBA_HOME`. The task should state this and name the parameters to add (member name, data directory, `depends_on`). Otherwise a junior agent could build two separate stores and then debug a failure that belongs to the harness, not to the code under test.

### [CONCERN] Task 0.1 checks 226 and 229 only, although its context says 224 and 228 are checked too, and it does not commit the planning documents before branching

The context summary says "224, 226, 228 and 229 are merged (task 0.1 checks)" (tasks:44), but 0.1 confirms only 226 and 229 (tasks:57). I could not confirm any of these merges from this session. The only reflog match was the 229 merge. Line 56 also refers to "uncommitted deletions of this slice's own task and review files," but the git status at session start shows the slice design and task file as modified, not deleted. Nothing in 0.1 says to commit the planning documents to the target before `git checkout -b`. Otherwise those edits land in the first `feat:` commit at 1.3 (tasks:90), against the planning cadence. Fix: check all four merges in 0.1, and replace the deletions sentence with a step that commits the planning documents to the target first.

### [CONCERN] The section 4 preamble misquotes D7 and contradicts 4.1 and 6.3

Line 144 says "D7 says 226's stdio count is the one edit to a 226 test," then says the stdio test already counts `OperationName`. The design (`227-slice.program-dependencies.md:192`) says it already counts and needs no edit, and `tests/mcp_server/test_stdio_smoke.py:71` does count it. Task 4.1 (tasks:148) says it needs no edit. An implementer following the preamble would edit a test that needs no change, and 6.3 would then fail. Delete the first clause.

### [NOTE] Adoption in member repos is not scheduled and not marked out of scope

The Operator Walkthrough's Start step has an agent session in each provider and consumer repo paste the D6 blocks into its rules file and release skill, and install the tool. The stated Value depends on that adoption, yet no success criterion or task covers it. Add one sentence to the task file saying this is post-merge operator work in other repos, outside this breakdown, so the implementer does not read it as a gap.

### [NOTE] The flow test does not say how the block's commands are located or run

Task 6.1 says to extract "its two git commands" and run them. The second command (`git log --max-parents=0 --reverse --format=%aI | head -1`) contains a pipe, so it has to run through a shell or the pipe must be handled. The task does not say which, or how the commands are found in the block. Name the parse (by heading, as 5.2 does) and the run method.

### [NOTE] The two-worktree criterion is covered at the mechanism level only

"Two worktrees ... each see everything since their own point" is covered by the store/operation test "two since values each see everything after their own point." No test uses two real worktrees. D4 stores no read marker, so the mechanism test is the one that matters, and no change is needed.

### [PASS] Every success criterion maps to at least one task

Criterion 1 is covered by 1.3, 3.2 and 6.1. Criterion 2 by 1.2 (`add_version`), 1.3 and the 6.1 release case. Criterion 3 by 1.3 (correction), 2.4 (withdraw), 3.2 and 6.1. Criterion 4 by 3.2 and the 6.1 window and rebase cases. Criterion 5 by 2.4, 3.2, 4.2, 4.4 and 6.2. Criterion 6 by 3.2 (warning) and 4.2 (exit 3). Criterion 7 by 6.3 and the docs in 4.5 and 5.3. Criterion 8 by 6.1 and 6.2.

### [PASS] Test-with pattern, commit markers and file count are sound

Each implementation step is followed by its tests, and contract-doc tests move with the docs. Seven plain-line `**Commit**:` markers sit at section ends (tasks:90, :105, :122, :140, :176, :195, :219), not after each task. One task file suits six sections. The 2.2 marker's "checks pass" depends on the fix in the second FAIL. The live tier is excluded from a bare run (`pyproject.toml:64`), and 6.2 runs it explicitly.

### [PASS] Scope additions are required by existing code or tests

The MCP `INSTRUCTIONS` entries, the per-row timeout advice and the README command list are not design items, but they are not scope creep. `test_instructions_name_every_tool` (`tests/mcp_server/test_instructions.py:12`) requires every tool to be named. `ToolSpec.timeout_advice` is a required field (`src/amoeba/mcp/tools.py:74`), so each new row needs a value. `README.md` exists at the root.

### [PASS] No deferral, no waiting on use, no hallucination traps, and the parent edits are in place

The consumer and provider blocks use `<time>`, `<full hash>` and `<tag name>` placeholders with no sample value near a fetched value, and 5.2 checks that neither block contains a 40-hex string. Nothing waits on the PM or on real use. The pipeline step is outside 227's scope in the parent (`220-slices.program-tool.md:162-172` does not list it). The "Pending Planning Edits" are present in the parents (`220-arch.program-tool.md:107`, `:111`, `:202`; `220-slices.program-tool.md:167-171`).

### Run Digest

- Response length: 11506 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 30
- Tokens — prompt / cached / cache write / completion / reasoning: 955620 / 754345 / 201261 / 74651 / not computed
- Duration: 318.7 s
- Cost: $0.30 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
