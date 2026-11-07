---
docType: review
layer: project
reviewType: slice
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/223-slice.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 8bea4a1019265ed50a96e49e68fb2eaae77c26ee
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
effort: high
turns: 4
promptTokens: 225082
cachedTokens: 112008
cacheWriteTokens: 113068
completionTokens: 10695
durationSeconds: 86.6
costUsd: 0.571276
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "The answering run's self-skip depends on an unverified Context Forge behavior"
    location: "project-documents/user/slices/223-slice.pause-handling.md:239"
  - id: F002
    severity: concern
    category: failure-modes
    summary: "The consequence of a wrong-checkout call is asserted, not verified"
    location: "project-documents/user/slices/223-slice.pause-handling.md:202"
  - id: F003
    severity: concern
    category: scope-boundary
    summary: "The Squadron run-file read runs before the membership checks"
    location: "project-documents/user/slices/223-slice.pause-handling.md:185-198"
  - id: F004
    severity: concern
    category: proportionality
    summary: "The design carries a mechanism the architecture doesn't call for"
    location: "project-documents/user/slices/223-slice.pause-handling.md:342"
  - id: F005
    severity: note
    category: architectural-alignment
    summary: "The claim-last ordering reverses the architecture's step order, and it is justified"
    location: "project-documents/user/slices/223-slice.pause-handling.md:143"
  - id: F006
    severity: note
    category: integration
    summary: "The slice adds a new request to Squadron, #303"
    location: "project-documents/user/slices/223-slice.pause-handling.md:178"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D6 — The answering run"
  - id: F008
    severity: pass
    category: dependency-direction
    summary: "Layering, dependency direction and consumer integration match the architecture"
    location: "project-documents/user/slices/223-slice.pause-handling.md#Architecture"
---

# Review: slice — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] The answering run's self-skip depends on an unverified Context Forge behavior

Architecture step 5 starts the answering run "always with the hook's opt-out". D6 defers that flag until #302 ships. Until then it relies on the answering run's hook call being skipped as `not_a_project`, "because the scratch directory is no Context Forge project" (D3 repeats the claim).

- **Unverified resolution.** The design never checks how Context Forge resolves a directory. If it resolves upward, `$AMOEBA_HOME/answering/<id>` can resolve to a project. That happens whenever `$HOME` or a test `AMOEBA_HOME` sits inside a repo, and dotfile repos are common.
- **Consequence.** The answering run's own pause would be treated as a member question, which starts another answering run. Spend is capped per run, but the recursion has no limit.
- **Cheap fix.** Add a skip reason that doesn't depend on Context Forge or #302. For example, skip when the run id equals any `questions.answering_run_id`, or when the working directory is under `answering_dir()`. The first is a structural check on the store and doesn't use a label. Slice 225 relies on the hook, so this safeguard should be in place before it.

### [CONCERN] The consequence of a wrong-checkout call is asserted, not verified

D3 accepts that, until #303, a hand call from the wrong checkout of the same program can claim the question. It says the resume "would then start in that repo, and its run lock and Squadron's run lookup would decide what happens", and adds no mechanism.

- **Likely outcome.** The architecture says all worktrees of a repo are one member, so a sibling worktree passes every check. The slice's own Squadron facts say run files are global (`~/.config/squadron/runs/<run_id>.json`) and carry no directory. A lookup by id would therefore succeed from any checkout. The likely result is that the work run resumes and edits the wrong worktree, not a refusal. The doc doesn't show that either is the case.
- **Where the exposure is.** Catch-up calls (`status` in 224, then `handle_pause`) have no verified directory until #303.
- **What to do.** State the verified resume behavior, or record it as an assumption with a test in the live tier. If the harm is real, add a minimal guard. For example, have the result and `status` show the recorded checkout, and make `docs/squadron-hook.md` say that hand calls must run in the run's own checkout. "No mechanism is added" should be a conclusion from evidence.

### [CONCERN] The Squadron run-file read runs before the membership checks

D3's order puts `prompt_only`, which needs the run-file read from D2, ahead of `not_a_project` and `not_in_program`. D2 makes any `RunFileProblem` an operational error (exit 3), including a different `schema_version` after a Squadron upgrade.

- **Effect.** A question pause in a repo outside any program would produce an error and a call-log entry instead of being ignored. The architecture says "a repo in no program is ignored" and lists "optional everywhere" as a goal.
- **Fix.** Reorder so the checks that need only the working directory run first: `not_a_project`, `not_in_program`, then `prompt_only`. This also matches the Data Flow, which places member resolution at step 3 although D3 lists `not_a_project` among the eligibility checks.

### [CONCERN] The design carries a mechanism the architecture doesn't call for

The per-call JSONL log (D13) is the clearest cut.

- **Why it can go.** The architecture has no call log. Its answer for a missed hook is that `status` shows the paused run and an agent calls `handle_pause`. D13 itself says a skip writes nothing by design. The log exists to explain why a hook call was missed. That is useful diagnostics, but it adds a file format, an append path, a before-home-resolution error case and a test surface to the largest slice in the plan.
- **What to do.** Defer it until 225's trial shows missed hooks that need explaining. Operational errors already exit 3 with stderr.
- **Smaller trims.**
  - "Interfaces Required" restates module-by-module inventories of 221 and 222 that the audit and 222 already record.
  - Walkthrough steps 8 and 9 repeat the D15 unit tests for `not_delivered` and `refused`.

### [NOTE] The claim-last ordering reverses the architecture's step order, and it is justified

The architecture claims first (step 3) and then works out context (step 4). D4 inserts the claim after gathering context and creating the scratch directory. The stated reason is that one insert can then record either the answering run id, which the architecture requires on the claim, or the context failure.

- **Why it's acceptable.** The reversal is named and the cost is stated (a losing racer repeats the reads). The unique `(run_id, paused_at)` insert still decides the winner, and the answering run starts only after the insert, so no duplicate spend is introduced.
- **Small gap.** A process that dies between scratch creation and the insert leaves an orphan scratch directory. That is harmless, and the doc already says nothing is pruned.

### [NOTE] The slice adds a new request to Squadron, #303

The architecture scopes #303 to the working directory in the run file and JSON from `sq runs list`. D2 adds a comment asking for `params` and `execution_mode` in `sq runs wait --json`, and keeps the run-file reader behind a schema-version check until that lands. The coupling is contained in one module and fails loudly, which matches "fail where someone can see it". The architecture's #303 row should be updated at the next planning edit.

### [PASS] Failure modes for the new I/O paths are enumerated

Each new subprocess and store path has an explicit outcome.

- **Answering run:**
  - spawn error → `answering_launch_failed`
  - scratch `OSError` → `waiting_on_pm`
  - wall-clock timeout → process-group terminate and `answering_run_stalled`
  - `PollFailure` after the run → `answering_run_failed`
- **Dead claims:** D7 maps every `poll_run` result to an action.
- **Resume:** D8 distinguishes `running`, moved past, child exited and timeout.
- **Store writes:** compare-and-set guards cover races, and "no transaction held across a subprocess" is asserted by a test.

### [PASS] Layering, dependency direction and consumer integration match the architecture

- **Dependency direction:**
  - `cli → operations → store, config, upstream, answering` is kept.
  - `answering` stays free of store, config and operations imports, enforced by a boundary test (D11).
  - D12 keeps `Path.home` in `home.py`.
- **Operations:**
  - `handle_pause` and `answer` match the architecture's operation table.
  - One resume path serves both operations.
  - Nothing is pushed or retried in the background.
- **Authorize list:** it reaches the answer and check steps through a prompt file, and the screen stays a backstop.
- **Consumers:**
  - 224 gets the question states, waiting reasons and resume columns with no new columns needed.
  - 226 gets the operations with a shared `deps` bundle.
  - 225 gets the hook doc.
- **Scope against the plan:**
  - The plan's 223 criteria and the audit-restored live tests are all covered.
  - Program passages from 182 are in scope, as the plan notes.
  - Cross-program precedent sharing and `status`, `decisions` and `mark_read` are correctly excluded.

### Run Digest

- Response length: 8592 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 225082 / 112008 / 113068 / 10695 / not computed
- Duration: 86.6 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
