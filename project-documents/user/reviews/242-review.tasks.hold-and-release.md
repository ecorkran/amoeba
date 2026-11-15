---
docType: review
layer: project
reviewType: tasks
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/242-tasks.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: a6f03ba561734676a563c103d69b27961f6d7bc6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 49
effort: xhigh
turns: 50
promptTokens: 2327483
cachedTokens: 2114242
cacheWriteTokens: 213211
completionTokens: 88885
durationSeconds: 410.4
costUsd: 0.528674
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "The live tier can pass without the automatic resume running"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:203-208"
  - id: F002
    severity: concern
    category: timing
    summary: "`status` and `list` gain start-trigger waits under a deadline the plan treats as inapplicable"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:170-176"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Section 1's commit fails `tests/test_contract_docs.py`"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:75-77"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 2.3 adds logic to `answering/passages.py`, which the Context rule forbids"
    location: "src/amoeba/answering/passages.py:356"
  - id: F005
    severity: concern
    category: verification
    summary: "10.2's \"edited existing tests\" check cannot be met as written"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:240"
  - id: F006
    severity: concern
    category: verification
    summary: "Task 4.1 cites \"the 223 `pause_claim` tests,\" which do not exist"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:127-128"
  - id: F007
    severity: concern
    category: rules-compliance
    summary: "The start trigger is a concurrency path with no load test or CI gate"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:170-172"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Section 7 bundles four operations and eight test files in one commit"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:180-199"
  - id: F009
    severity: note
    category: scope
    summary: "`add` is in the start set with no stated reason"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:171"
  - id: F010
    severity: note
    category: scope
    summary: "Step 0.1 runs a live check that feeds no decision"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:55"
  - id: F011
    severity: note
    category: verification
    summary: "The baseline clause conflicts with \"checks pass\""
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:57-58"
  - id: F012
    severity: note
    category: docs
    summary: "Give each contract-doc entry one owning task"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:65,222"
  - id: F013
    severity: note
    category: process
    summary: "Planning edits and a design change are riding on the slice branch"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:225-227"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every design success criterion maps to a task"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:273-296"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing respects dependencies and has no cycles"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:60-244"
  - id: F016
    severity: pass
    category: verification
    summary: "Repo facts the tasks depend on check out"
    location: "src/amoeba/operations/prune.py:81-88"
  - id: F017
    severity: pass
    category: rules-compliance
    summary: "The Amoeba design rules hold in the breakdown"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:246-262"
---

# Review: tasks — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The live tier can pass without the automatic resume running

Task 8.1 has the harness reply from `cf-s`, then run `amoeba handle-pause` in `sq-s`. The live test can go green while the start trigger never fires. No named test runs a real detached child (`resolve_amoeba_script` plus `deps.spawn`) after an `amoeba reply`. Task 6.3 uses a fake spawn, and 6.5 does not say which spawn it uses. The design's headline, that the run carries on by itself, is therefore untested end to end.

Fix: make 8.2(a) reply through the CLI and poll, with a bound, until the run resumes with no manual `handle-pause`. Add one non-live test that runs the real detached child against a fixture store. Also replace the design's "within a minute" (`242-slice.hold-and-release.md:306`) with a bounded poll, since a live answering run with check and resume is not a one-minute operation.

### [CONCERN] `status` and `list` gain start-trigger waits under a deadline the plan treats as inapplicable

Task 6.5 says `status` and `list` "are outside this deadline test by design ... so no bound is added." The timing test covers four operations, but the deadline does not. `run_in_process` applies `MCP_CALL_DEADLINE_SECONDS` (180 s) to every in-process tool (`src/amoeba/mcp/in_process.py:77-82`). `list` and `status` are in-process tools with `READ_ADVICE` (`src/amoeba/mcp/tools.py:123`, `:135`). After 6.4, each adds one read and up to five busy-timeout writes, which is `START_BOUND_SECONDS` = 30 s at the 5.0 s `BUSY_TIMEOUT_SECONDS` (`src/amoeba/store/store.py:28`). The 240 architecture already sweeps in `status` and `list` (`240-arch` line 99), so their writes are inherited, and this slice adds to them.

Fix: include `status` and `list` in the worst-case test. Assert that their worst case plus `START_BOUND_SECONDS` stays under the deadline, or state why it cannot reach it.

### [CONCERN] Section 1's commit fails `tests/test_contract_docs.py`

Task 1.4 adds `PauseClass.WAITING_ON_REQUEST`. `test_the_cli_contract_names_every_command_exit_code_and_result_value` (`tests/test_contract_docs.py:129`) requires every `PauseClass` value except `NOT_PAUSED` to appear backticked in `docs/cli-contract.md`. No task in section 1 writes that entry. Tasks 2.6, 7.1 and 9.2 touch cli-contract for other things. So 1.5's "checks pass" fails at the section 1 commit.

Separately, `test_the_cli_contract_names_the_new_status_fields_and_the_remove_section` (`tests/test_contract_docs.py:159`) iterates `StatusResult.model_fields`. If the quoted-data notice from D9 is a field there, 7.1 must name it. It does not.

Fix: add the `waiting_on_request` pause-class entry to cli-contract in 1.4. Add the notice field to 7.1's docs step if it is a field.

### [CONCERN] Task 2.3 adds logic to `answering/passages.py`, which the Context rule forbids

The Context (task file line 41) says modules over about 300 lines get no new logic and that new code goes in a new module. `passages.py` is 416 lines. Task 2.3 gives `assemble` a keyword and a placement rule, and gives `render_passages` (`passages.py:307`) a new section. Both are logic changes in the file the rule protects.

Fix: put the request placement and rendering in a new module, and have `assemble` take one call.

Related: `operations/pause_claim.py` is 233 lines. Tasks 4.1 and 4.2 add a shared helper, a `request` argument to `_prepare`, `start_held_claim`, and a `restart_dead_claim` change. That likely crosses 300. The design requires `start_held_claim` in that module, so state the expected size and accept it, or name a split.

### [CONCERN] 10.2's "edited existing tests" check cannot be met as written

Task 10.2 says the only edited existing tests are those named in 1.1, 1.3, 2.5, 6.1 and 6.5. Many other tasks add cases to existing files: 1.5 (`test_questions.py`, `test_question_closing.py`, the 228 `test_question_sweep.py`, the 223 `test_pause_class.py`), 2.4 (`test_passages.py`), 4.3 (the 223 `test_pause_existing.py`), 6.5 (`test_wiring.py`), 7.2 (the four status suites), and 7.4 (`test_dismiss.py`, `test_every_state_exits.py`). A reviewer cannot tick this check as written. Context line 46 ("pass unchanged") has the same problem.

Fix: restate it as "no existing test function or assertion in the 223, 228, 240 or 241 suites changes. New test functions may be added to the files listed in tasks X, Y, Z." Name the files.

### [CONCERN] Task 4.1 cites "the 223 `pause_claim` tests," which do not exist

No file under `tests/` is named `test_pause_claim*.py`, and no test imports `amoeba.operations.pause_claim`. The 223 coverage of `start_new_claim` runs through `handle_pause` tests. The success line points at a suite that does not exist, so it cannot be checked.

Fix: name the 223 files that exercise `start_new_claim` and `restart_dead_claim`, found by searching `tests/` for the behaviour, and say which of them covers the shared limit helper.

### [CONCERN] The start trigger is a concurrency path with no load test or CI gate

The parent architecture restates no load NFR (a search of `240-arch` finds no load, throughput or latency terms), so the NFR rule does not fire. `.claude/rules/python.md` does: code on concurrency paths needs at least one load test in `tests/load/` that asserts a bound, and CI must gate it. The start trigger spawns detached processes from every write-capable operation and races claims. Tasks 6.3 and 6.5 test it only with fakes. No task writes a load test or CI wiring, and `.github` has no reference to `tests/load`. The existing `tests/load/test_report_release_load.py` is the model.

Fix: add a load test that runs `start_ended_held` with more held rows than `MAX_STARTS_PER_CALL` against a store under a busy writer, asserting the bound. Add a CI gate task for it.

### [CONCERN] Section 7 bundles four operations and eight test files in one commit

Section 7 covers `status`, `decisions`, `dismiss`, `answer` and the refused-resume path, with docs, in one commit. Task 7.4 says "no code change beyond 1.4 is expected," which leaves the agent unsure whether to write code.

Fix: split into 7a (`status` and `list`) and 7b (`decisions`, `dismiss`, `answer`), each with its own commit or a clear point. Also cut the 1.2 test that a store stamped 9 is refused. It checks the existing newer-schema guard, which is not a success criterion.

### [NOTE] `add` is in the start set with no stated reason

`START_AFTER_OPERATIONS` includes `add`. The design gives no reason (`242-slice.hold-and-release.md:202`). The 240 architecture lists the calls that run the sweep and can end a request: `send`, `reply`, `cancel`, `status`/`list` and `handle_pause` (`240-arch` line 99). `add` ends no request, so nothing in the criteria needs it. Drop it, or state the reason in the design.

### [NOTE] Step 0.1 runs a live check that feeds no decision

The matcher reads the whole question text either way (design D1), so the observed `…` tail changes no implementation. The design asks for the re-check, so it can stay as a recorded fact. Otherwise drop it.

### [NOTE] The baseline clause conflicts with "checks pass"

Line 57 says pre-existing failures are "written down, not fixed." Task 10.2 requires all four checks to pass. If the baseline is red, the step has no route: no BLOCKED, no fix, no stop. Say whether a red baseline stops the work (BLOCKED with the output) or is fixed in place.

### [NOTE] Give each contract-doc entry one owning task

Tasks 1.1 and 9.2 both edit the store-contract writers table, the `waiting_reason` values and the state-end list. Context line 45 says each task adds its entry as it adds the thing, but 2.3 adds `PassageKind.REQUEST_RESULT`, and its cli-contract entry appears only at 7.3 (line 190). Give each entry one owner.

### [NOTE] Planning edits and a design change are riding on the slice branch

Task 9.3 amends the 240 architecture and plan. Those are planning documents, and the Git rules commit planning work to the integration target, not to a slice branch. Task 2.1 also changes `find_request_link` from the design's one-argument form (`242-slice.hold-and-release.md:86`), and 9.3 corrects the design afterwards. Confirm with the PM whether the parent amendments and the design change go to the target now or travel with the merge.

### [PASS] Every design success criterion maps to a task

Functional: held, resume and `decisions` → 5.1–5.3 and 8.2(a) (see the live-tier finding). Already-done → 5.3. Release-line live → 8.2(b). Declined, cancelled, expired and `rm` → 5.3 and 6.5. Every exit → 1.5, 5.3 and 7.4. Marker shapes and bad links → 2.2 and 5.3. Answer limit → 4.3. Race → 5.3. Dead-claim restart → 4.3. Failed start → 6.3 and 7.2. Cap and drain → 6.3 and 6.5. Four request ends through both doors → 6.5. Live tier → 8.2.

Technical: migration → 1.2. Link tests → 2.2. `assemble` keeps the request → 2.4. No transaction across a subprocess → 4.3 and 6.3. `answering.yaml` validates → 2.5. Checks and contract docs → 1.1, 9.2 and 10.2.

### [PASS] Sequencing respects dependencies and has no cycles

Section 1 precedes 3 and 5. Task 2.1 precedes 5.2. Section 3 precedes 4 and 5. Task 4.2 precedes 5.1. Section 6 follows 3. Section 8 follows 5 and 6. Each code section carries its tests in the same section (test-with pattern). Commit markers sit at section ends. Section 1 has an intermediate pyright state that 1.4 closes.

### [PASS] Repo facts the tasks depend on check out

Verified: schema files 001–005 exist, and `store/messages.py` and 240's test files do not, so 0.1's BLOCKED gate is the right first step. Module sizes match the Context (`sql.py` 484, `wiring.py` 342, `passages.py` 416). The prune walk covers all of `logs_dir` and removes unnamed directories by age, so `logs/request-release/` is pruned. `AMOEBA_HOME` makes config and state one directory (`src/amoeba/config/home.py:88`), so 10.1's flat copy layout is correct. `dismiss --reason` exists (`src/amoeba/cli/parser.py:118`). `answering_wait_seconds`, `answer_limit` and `prune_after_days` exist in `src/amoeba/config/user_config.py`.

### [PASS] The Amoeba design rules hold in the breakdown

- **No deferral:** none found. The only "not fixed" phrase is the baseline clause, noted above.
- **No waiting on real-world events:** none. Live tests use fixtures and the pre-authorized live tier.
- **Every state has an exit:** held rows end by resume, `waiting_on_pm`, PM `answer`, `dismiss`, the close sweep or request end. Start retries are bounded by `answering_wait_seconds` and end by `dismiss`. An `accepted` request has no TTL (`240-arch` line 91), so a held question on one waits for the addressee. Its exits are `cancel` and `dismiss`, both PM commands.
- **Config versus state:** no new config key. Backups and logs sit in the state directory.
- **Live store:** P7 has a backup, a restore path and a removal step. The designation covers the migration. The P7.1 "241 not migrated live" stop is a dependency gate, not a designation.
- **Operator walkthrough:** the design's walkthrough finds no dead end where nobody can act. The one soft spot is the "within a minute" expectation, covered by the first finding.

### Run Digest

- Response length: 17202 chars
- Response is newline-free: no
- Tool calls made: 49
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 50
- Tokens — prompt / cached / cache write / completion / reasoning: 2327483 / 2114242 / 213211 / 88885 / not computed
- Duration: 410.4 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17

## Resolution

- **F001:** fixed. 8.1/8.2(a) run `handle-pause` once for the held first call, reply through the CLI, then poll to `AUTO_RESUME_WAIT_SECONDS` with no manual `handle-pause`. New 6.5 test `test_request_release_child.py` runs the real detached child (`resolve_amoeba_script` + `deps.spawn`) against a fixture store. Design step 5's "within a minute" replaced by the bounded poll.
- **F002:** fixed. 6.5's timing test covers `status` and `list` (worst case plus `START_BOUND_SECONDS` below `MCP_CALL_DEADLINE_SECONDS`); the "outside this deadline test" claim is removed.
- **F003:** fixed. 1.4 adds the `waiting_on_request` pause-class entry to `docs/cli-contract.md`. The notice part is moot: 240 documents `notice`.
- **F004:** fixed. 2.3 puts request placement (and any rendering) in `answering/request_passage.py`; `assemble` gains one call. 4.2 states `pause_claim.py` reaches about 320 lines and names the split: the waiting-settle helpers move to `operations/claim_waiting.py`.
- **F005:** fixed. Context and 10.2: no existing test function or assertion in the 223/228/240/241 suites changes except the edits 1.1, 1.3, 2.5, 6.1 and 6.5 name; the Context lists the existing files new test functions may be added to.
- **F006:** fixed. 4.1 names `test_handle_pause.py` (`start_new_claim`; its two answer-limit tests cover the shared helper), `test_pause_existing.py` and `test_every_state_exits.py` (`restart_dead_claim`).
- **F007:** fixed. New 6.6 load test `tests/load/test_start_ended_held_load.py`. No CI task: bare `uv run pytest` collects `tests/load`.
- **F008:** dropped. Section 7 stays one commit; the store-stamped-9 test stays.
- **F009:** dropped. `add` stays in the start set: its remove path runs `apply_removal`, which cancels the member's requests (240 D10), so `add` can end requests.
- **F010:** dropped. The 0.1 live check stays as a recorded fact.
- **F011:** fixed. 0.1: a pre-existing failure in the touched area is fixed in place as its own `fix:` commit before slice work; one outside it is left and noted. "Checks pass" excludes only those noted failures.
- **F012:** dropped.
- **F013:** dropped. Planning edits ride the slice branch (9.3), the established pattern as in 240.
- **F014–F017:** pass, no change.
