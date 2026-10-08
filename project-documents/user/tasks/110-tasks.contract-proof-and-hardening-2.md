---
docType: tasks
slice: contract-proof-and-hardening
project: amoeba
lld: user/slices/110-slice.contract-proof-and-hardening.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108, 109]
projectState: Continuation of 110-tasks.contract-proof-and-hardening-1.md. Sections 1–4 are done when this file starts - hardening (relative dirs, slug ids, done terminal), the amoeba.process hosting seam, five export pins, and the proof scaffolding (fake Squadron, snapshot, harness, proof host, public-only guard). Sections 5–7 need 105–109 merged.
dateCreated: 20261008
dateUpdated: 20261008
status: not_started
---

## Context Summary

- Continuation of the **contract-proof-and-hardening** slice (110). Read File 1's Context Summary and reading note first; they apply here unchanged.
- **Task numbers with letters (5.8a, 5.8b, 5.8c) are real tasks inserted to keep each commit tested; do them in order, as listed.**
- **This file:** 5 `ProofRunner` and the clean run; 6 kill points and both subscribers; 7 restart matrix in the load tier; 8 locality under the sequence; 9 pruning; 10 docs and the contract index; 11 final validation.
- **Hard gate:** Sections 5, 6, 7 and 8, Task 9.5, and Tasks 10.1 and 10.4–10.6 need 105–109 merged (Task 1.1's presence table), because they run or describe the clean sequence. Tasks 9.0–9.4 (the pruning classifier and command) need 105 only, because they live in `amoeba.upstream.squadron`, the package 105 creates; they do not need 106–109. Tasks 10.2 and 10.3 need only 101–104 (and Task 1.2's method if it was added). If a needed slice is absent: do the tasks that do not need it, then stop and tell the PM which slices block the rest. Do not stub a missing slice's API.
- **`ProofRunner` rule (LLD "Special Considerations"):** it follows a fixed table and keeps **no progress in memory**. Each tick it reads the store (`nodes_for_project`, `runnable`, `blocked`, `journal_entries`, `verdicts`), finds the first step whose "state afterwards" does not hold, and does that step. It makes exactly one decision: re-issue after an `unknown` entry whose block was resolved. Add nothing else.
- **Waits:** every wait is "until a public-state condition holds, with a timeout" (Task 4.6's `wait_until`). No fixed sleeps.

**Commit cadence and branch:** as in File 1. No task merges.

---

## Section 5: `ProofRunner` and the Clean Run

### Task 5.1: Kill-point enum and the step table
**Owner**: Junior AI
**Dependencies**: 4.9, 1.1
**Effort**: 3
**Objective**: Define the data the runner and the harness share, once.

**Steps**:
- [ ] Create `tests/contract/proof_runner.py`. Define `KillPoint` as one `StrEnum`: `after-issue`, `after-launch`, `inbox-while-down`, plus one boundary member per step 1–11 for the load-tier matrix (name them `after-step-1` … `after-step-11`; the harness and tests reference only the enum). `ProofRunner` reads the kill point from one environment variable whose name is a module constant
- [ ] Define the step table as data: each row is a name, the "state that must hold afterwards" (a predicate over a store-reading view), and an action. Rows for runner-owned steps are 2, 3, 4, 6, 7, 11. Steps 1, 5, 8, 9, 10 are actors' (Task 5.5) and the runner only checks they have happened before continuing; its predicates for them read the store, never actor-side flags
- [ ] `tick(host)` implements the `Tenant` protocol: for each project it is assigned (`proof`, and `proof-b` for steps 1–3), find the first row whose predicate is false and either do its action or return, if it waits on an actor. Return the tenant's "did work" boolean as the protocol requires (read `Tenant.tick` in `process/host.py`)
- [ ] Define once, beside the enum, which side performs each kill (`KILL_OWNER`): the runner kills itself at `after-issue`, `after-launch`, and `after-step-N` for runner-owned steps 2, 3, 4, 6, 7, 11; the **harness** kills the host (`kill_host`) for `inbox-while-down` and for `after-step-N` of actor-owned steps 1, 5, 8, 9, 10, because the runner cannot observe those moments. `mid-follow` is deliberately not a kill point (see Task 6.1)
- [ ] Kill points apply to project `proof` only. `proof-b` runs steps 1–3 through the same table but its rows never call `kill_here`, and the driver's harness-side kills key on `proof`'s state, so an `after-step-N` kill is never attributed to the wrong project
- [ ] `kill_here(point)`: if the configured kill point equals `point`, `os.kill(os.getpid(), signal.SIGKILL)`. No mocks
- [ ] Nothing in memory between ticks except the configuration. A second `ProofRunner` constructed fresh must continue from the store

**Success Criteria**:
- [ ] Module has the enum, the table type, `tick`, and `kill_here`; passes the public-only guard
- [ ] Committed with Task 5.3

### Task 5.2: Steps 2 and 4 — nodes, then block on judge
**Owner**: Junior AI
**Dependencies**: 5.1
**Effort**: 2
**Objective**: Step 2 creates `initiative`, `slice` (`cf.slice_name = resident-process-and-recovery`), and a `gate` under it. Step 4 blocks the gate on `judge`.

**Steps**:
- [ ] Add the two rows. Step 2's predicate is "three nodes with these titles exist"; the action creates only the missing ones, so a kill between creates is repaired by the next tick. Step 4's predicate is "gate is `blocked_on_judge`"; use `block()` (never write status directly)
- [ ] Order: step 4 runs after step 3 per the table

**Success Criteria**:
- [ ] Rows added; each action is idempotent (running it twice changes nothing)
- [ ] Committed with Task 5.3

### Task 5.3: Test steps 2 and 4 on a store
**Owner**: Junior AI
**Dependencies**: 5.2
**Effort**: 2
**Objective**: Prove idempotence and fresh-instance continuation without a process.

**Steps**:
- [ ] `tests/contract/test_proof_runner_steps.py`: open a temp store through `Store.open` (public), run the step table's predicate-and-action pair for step 2 twice and assert three nodes; then, in a fresh store, pre-create only the initiative and assert the runner creates the remaining two. Use a second runner instance for the second call to show no memory is needed
- [ ] Step 4: with step 3's predicate faked true by building its state through the store (a recorded verdict), assert the gate becomes `blocked_on_judge` and a second call does nothing

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add ProofRunner node and judge-block steps`

### Task 5.4: Step 3 — journal, launch, report back
**Owner**: Junior AI
**Dependencies**: 5.3
**Effort**: 4
**Objective**: The Squadron round trip, in the obligation order: journal before launch, launch through the fake, report back in one transaction from the artifact.

**Steps**:
- [ ] Row 3 uses `journal_issue(sq_run)` on the slice node; calls `kill_here(after-issue)`; calls `fake_squadron.write_completed_run` and `write_review_round(1)` into the throwaway directories; calls `kill_here(after-launch)`; parses the artifact with 105's `parse_review_artifact`, converts with `to_verdict_input`, and calls 106's one-transaction report-back method (name from Task 1.1), passing the entry id, path, and digest. Use 106's `attribute_review` to confirm the slice node is the target. No other write
- [ ] Predicate: the slice node has a verdict from this artifact, a `runner_issued` detection for that `(path, digest)`, and a `completed` or `adopted` journal entry. A tick that finds an `adopted` entry with no verdict skips the issue and launch and goes to the report-back (the `after-launch` recovery); a tick that finds the verdict recorded by detection first records nothing new (the report-back is a retry)
- [ ] The one decision: an `unknown` entry whose human block is resolved leads to a fresh `journal_issue`. Everything else about `unknown` is left to the human actor
- [ ] The same row runs for `proof-b` (steps 1–3 only), with its own slice node, and with no kill calls (see Task 5.1)

**Success Criteria**:
- [ ] Row exists; no `Store` write other than `journal_issue`, node reads, and the report-back method appears in the file (grep)
- [ ] Committed with Task 5.5

### Task 5.5: Test step 3 on a store, no kill
**Owner**: Junior AI
**Dependencies**: 5.4
**Effort**: 3
**Objective**: Verify the step's postconditions and its retry behavior.

**Steps**:
- [ ] In `test_proof_runner_steps.py` add: run steps 2 and 3 against a temp store and throwaway directories; assert a `CONCERNS` verdict on the slice node, detection `runner_issued`, journal `completed`, and one run file plus one review file on disk. Run step 3's action a second time: still one verdict, one detection (idempotent retry)
- [ ] Build the `after-launch` state by hand (issue, write files, mark the entry `adopted` through the journal's public methods), then run the row: it records the verdict from the artifact and writes no second run file
- [ ] Build the `after-issue` state (entry issued, nothing on disk, then escalated to `unknown` with a human block, resolved): the row issues again

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add ProofRunner Squadron round-trip step`

### Task 5.6: Steps 6, 7, 11 — checkpoint block, human block, finish
**Owner**: Junior AI
**Dependencies**: 5.5
**Effort**: 3
**Objective**: The remaining runner-owned rows.

**Steps**:
- [ ] Step 6: `journal_issue(sq_run)` on the gate; the fake writes a **paused** run; resolve the entry with the run id; set the gate's `sq.run_id` (public `update_sq_reference`); `block()` on `sq_checkpoint`. Predicate: gate is `blocked_on_sq_checkpoint` with `sq.run_id` set and the entry resolved
- [ ] Step 7: `block()` the slice node on `human`, with the escalation row written with it (check how `block` and `journal_escalate` write the escalation message and use the same public call; the expected state is one human block and one escalation message on the slice node)
- [ ] Step 11: mark gate, slice, initiative `done` in that order. Predicate: all `done`, nothing runnable or blocked in `proof`. This relies on Task 2.5: the step cannot succeed with an unresolved entry
- [ ] Each runner-owned row also calls `kill_here(after-step-N)` at the end of its action (step 3's after the report-back). Actor-owned steps have no runner kill call: the driver kills them (Task 5.9)

**Success Criteria**:
- [ ] Rows added; each action idempotent
- [ ] Committed with Task 5.7

### Task 5.7: Test steps 6, 7, 11 on a store
**Owner**: Junior AI
**Dependencies**: 5.6
**Effort**: 2
**Objective**: Postconditions per the LLD table.

**Steps**:
- [ ] Extend `test_proof_runner_steps.py`: after steps 2–4 and a manual judge resolution (public `resolve`), step 6 leaves `blocked_on_sq_checkpoint` and exactly one paused run file; step 7 leaves `blocked_on_human` and one escalation; after manual resolutions, step 11 leaves everything `done` and `runnable`/`blocked` empty. Calling step 11 while an entry is unresolved raises `InvalidTransitionError` (D6 working through the runner)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add ProofRunner checkpoint, human block, and finish steps`

### Task 5.8: CLI actors — Operator, Human, PM, Inspector
**Owner**: Junior AI
**Dependencies**: 5.7
**Effort**: 3
**Objective**: The CLI and file-copy actors, in `tests/contract/actors.py`, each using only a public surface.

**Steps**:
- [ ] Operator (step 1): `amoeba submit create-project --project proof --by …` and `amoeba submit watch-reviews --project proof --reviews-dir <abs> --active true`, via the harness's `run_cli`. Wait for the project to be listed before submitting into it (the obligation "wait for `create_project` to apply")
- [ ] Human (steps 8 and 10, and the `after-issue` and `inbox-while-down` recoveries): `amoeba submit resolution --project proof --by human --blocked-state-id … --detail …`. Find the blocked-state id through `amoeba inspect blocked --project proof --json`, never the store. Step 10's detail is "abandon, do not resume"
- [ ] PM (step 9): copy round 2 (part 1) from `fake_squadron` into the registered reviews directory by writing a temp name in the same directory, then renaming, so the detector never reads a half-written file
- [ ] Inspector: `inspect(args) -> parsed JSON` via `amoeba inspect … --json`

**Success Criteria**:
- [ ] Module passes the public-only guard
- [ ] Committed with Task 5.8a

### Task 5.8a: Test the CLI actors
**Owner**: Junior AI
**Dependencies**: 5.8
**Effort**: 2
**Objective**: Each actor works against the real host before the sequence relies on it.

**Steps**:
- [ ] `tests/contract/test_actors.py`: start the proof host (runner registered), run the Operator, and assert through the Inspector that the project and the watch exist. The Human actor needs a blocked state that only the full sequence produces, so it is exercised in the clean run (Task 5.9), not here
- [ ] PM: after the Operator registers a reviews directory, copy a round into it and assert, with `wait_until`, that `inspect detections` shows one row (needs 106)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add CLI actors for the lifecycle proof`

### Task 5.8b: Server and Judge actor
**Owner**: Junior AI
**Dependencies**: 5.8a
**Effort**: 3
**Objective**: One `amoeba serve --auth tokens` for the whole sequence, and the Judge that posts through it (step 5).

**Steps**:
- [ ] Add `start_server()` to the harness: `amoeba token add --principal judge --scope submit` and `--principal subscriber --scope read` (the token is printed once; capture it from stdout), then start `amoeba serve --auth tokens` on a free loopback port bound to the throwaway supervisor directory. The server is never a kill target; the harness stops it only at the end
- [ ] Create `tests/contract/judge_actor.py`. The Judge POSTs to `/v1/projects/proof/submissions` with `Authorization: Bearer` using the HTTP client recorded in Task 1.1: one `verdict` for the gate, two judge samples (same `judge_invocation_id`, each submitted separately, using 107's key), then a `resolution` for the judge block. Wait for each submission's state through `GET …/submissions/{id}` before the next
- [ ] Every Judge submission sets `submitted_by` to the token's principal (`judge`). 109 refuses a body whose `submitted_by` differs from the principal (`403 principal_mismatch`); the resolution's `resolved_by` is therefore `judge`
- [ ] Tokens never appear in logs or assertion messages

**Success Criteria**:
- [ ] Module passes the public-only guard
- [ ] Committed with Task 5.8c

### Task 5.8c: Test the server and Judge actor
**Owner**: Junior AI
**Dependencies**: 5.8b
**Effort**: 2
**Objective**: Scopes and the judge writes work as the sequence needs.

**Steps**:
- [ ] In `test_actors.py` add: a `read` token's POST is refused (`403`); a `submit` token's POST is accepted and applied (`wait_until` the submission state is applied); a `submit` token whose body `submitted_by` is not `judge` gets `403 principal_mismatch` and nothing is applied; after the Judge runs against a gate that is `blocked_on_judge` (build it by running steps 2–4 through the host), the gate is `runnable` and exactly two judge samples exist as separate records, read with `amoeba inspect verdicts --project proof --judge-invocation-id <J> --json` (107 adds that filter), with two distinct record ids

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add serve harness and Judge actor`

### Task 5.9: The sequence driver and the clean run
**Owner**: Junior AI
**Dependencies**: 5.8c
**Effort**: 3
**Objective**: Drive steps 1–11 end to end with no kill.

**Steps**:
- [ ] Register `ProofRunner` in `proof_host.py` (Task 4.7 left it out). Create `test_lifecycle_proof.py` with a driver function `run_sequence(kill_point=None)` returning the final snapshot and the runs and supervisor directory paths; the clean test calls it with `None`. The driver waits on each step's "state afterwards" with `wait_until`, then triggers the next actor
- [ ] The driver accepts any `KillPoint`: for a point whose `KILL_OWNER` is the runner, it passes the point to the host environment; for a harness-owned point, it calls `kill_host` as soon as the named step's state-afterwards holds. In both cases it then restarts the host with no kill point and carries on. Section 7 reuses this driver unchanged
- [ ] Clean test asserts the sequence reaches step 11: every node of `proof` is `done` and nothing is runnable or blocked

**Success Criteria**:
- [ ] The clean test passes three times in a row without flakes
- [ ] Committed with Task 5.9a

### Task 5.9a: Clean-run assertions and `proof-b` isolation
**Owner**: Junior AI
**Dependencies**: 5.9
**Effort**: 3
**Objective**: The LLD functional criteria for the clean run, and project keying.

**Steps**:
- [ ] Assert: three verdicts (two review rounds and the Judge's); two judge samples recorded separately; one detection `ingested` (round 2), one `runner_issued` (round 1); `finding_changes` on the round-2 verdict names round 1 as the previous round though one was recorded by the Runner and the other detected
- [ ] Add `proof-b` to the driver: steps 1–3, with its create-project submitted between steps 1 and 2 of `proof`. Assert neither project's `runnable`, `blocked`, `verdicts`, or feed ever shows the other's rows and that `inspect projects` lists both. Put these assertions in a shared helper that Task 8.1 calls

**Success Criteria**:
- [ ] Tests pass three times in a row
- [ ] Commit `test: add ProofRunner, actors, and the clean lifecycle run`

---

## Section 6: Kill Points and Subscribers (D4)

### Task 6.1: Expected-difference table
**Owner**: Junior AI
**Dependencies**: 5.9a
**Effort**: 2
**Objective**: Write down, once, how each kill point may differ from the clean snapshot.

**Steps**:
- [ ] In `snapshot.py` define the per-kill-point allowed differences as one mapping keyed by `KillPoint`: `after-issue` adds one `unknown` journal entry, one human block, and one escalation on the slice node; `after-launch`, `inbox-while-down`, and every `after-step-N` add nothing. `mid-follow` has no enum member and no row, on purpose: it is not a separate run but the subscriber checks of Task 6.5, which run in every kill run. Say so in a comment on the mapping. Import the key type from `proof_runner.py`; do not repeat the names

**Success Criteria**:
- [ ] One mapping, no duplicated kill-point strings (grep for the literal `after-issue` finds it only in the enum)
- [ ] Committed with Task 6.2

### Task 6.2: `after-issue` run
**Owner**: Junior AI
**Dependencies**: 6.1
**Effort**: 3
**Objective**: A kill after the journal commit and before the launch recovers through the Human.

**Steps**:
- [ ] In `run_sequence(kill_point)`: when the host exits by `SIGKILL` at the named point, restart it with no kill point set. Recovery finds zero matching runs → entry `unknown`, slice `blocked_on_human`. The driver waits for that state (public reads), has the Human actor resolve it, and lets the runner re-issue. Continue to step 11
- [ ] Add the test case and assert: sequence completes; final snapshot equals the clean one except the table's `after-issue` differences; the runs directory holds exactly one completed run per issued entry that succeeded

**Success Criteria**:
- [ ] Test passes three times in a row
- [ ] Commit `test: add after-issue kill run`

### Task 6.3: `after-launch` run
**Owner**: Junior AI
**Dependencies**: 6.2
**Effort**: 2
**Objective**: A kill after the run and review exist, before the report-back.

**Steps**:
- [ ] Add the case. Expected: recovery adopts the one matching run; the runner records the verdict from the artifact; if detection recorded it first, the runner's report-back is a retry and writes nothing. Assert one verdict for round 1 (never two), snapshot equal to the clean run (no allowed differences)

**Success Criteria**:
- [ ] Test passes three times in a row
- [ ] Commit `test: add after-launch kill run`

### Task 6.4: `inbox-while-down` run
**Owner**: Junior AI
**Dependencies**: 6.3
**Effort**: 2
**Objective**: A resolution submitted while the process is down is applied on start.

**Steps**:
- [ ] The kill point sits before step 8 (the slice is `blocked_on_human`). The harness kills the host there, the Human actor submits the resolution while the host is down (assert the submission is pending via `amoeba inspect`'s inbox listing), then the host restarts. Assert the block resolves and the sequence completes; snapshot equal to the clean run

**Success Criteria**:
- [ ] Test passes three times in a row
- [ ] Commit `test: add inbox-while-down kill run`

### Task 6.4a: Deferred export pins
**Owner**: Junior AI
**Dependencies**: 6.4, 3.3
**Effort**: 1
**Objective**: Finish any pin test Task 3.3 had to skip.

**Steps**:
- [ ] If the feed or squadron modules of Task 3.3 were skipped for a missing slice, write those pin tests now from the merged `__all__`. If none were skipped, do nothing

**Success Criteria**:
- [ ] Pin tests pass; no skips remain
- [ ] Commit `test: pin remaining public export sets` (or no commit if nothing was skipped)

### Task 6.5: Local feed subscriber and transcript check
**Owner**: Junior AI
**Dependencies**: 6.4a
**Effort**: 3
**Objective**: The `amoeba feed --follow` subscriber stays up through every kill and its transcript is checked (`mid-follow`).

**Steps**:
- [ ] Start `amoeba feed --project proof --follow` as a subprocess at the beginning of `run_sequence`, capturing stdout lines. The kill points never restart it
- [ ] At the end of every run (clean and each kill run) assert the transcript equals `amoeba feed --project proof --after 0` printed at the end: same `seq` list (no gap, no repeat) and the same lines
- [ ] Replay the transcript: apply each change by node title using the change vocabulary 106's contract lists, and assert the rebuilt status of every node equals its final status
- [ ] Assert nothing in the transcript carries `proof-b`

**Success Criteria**:
- [ ] The checks run in the clean run and all three kill runs, and pass
- [ ] Commit `test: check local feed transcript across kills`

### Task 6.5a: Remote SSE subscriber
**Owner**: Junior AI
**Dependencies**: 6.5
**Effort**: 3
**Objective**: The same contract proven through the network surface (109).

**Steps**:
- [ ] Add an SSE client against the `amoeba serve` from Task 5.8b with the `subscriber` (`read`) token, reading `/v1/projects/proof/feed?after=0`. It runs in a thread of the test process using the HTTP client recorded in Task 1.1. On disconnect or error it reconnects with `Last-Event-ID` set to the last `id:` it received. Keep the reconnect logic in one function
- [ ] The server is never killed, so add one deliberate disconnect (the client closes its own connection once, mid-sequence) to exercise resume
- [ ] At the end of every run assert the remote transcript equals the local one from Task 6.5: same `seq` list and same payloads

**Success Criteria**:
- [ ] The comparison passes in the clean run and all three kill runs
- [ ] Commit `test: check SSE transcript across kills and reconnect`

### Task 6.6: Whole `tests/contract` pass
**Owner**: Junior AI
**Dependencies**: 6.5a
**Effort**: 1
**Objective**: Verify the group before the load tier.

**Steps**:
- [ ] Run `uv run pytest tests/contract -v` once. Expected: `test_lifecycle_proof.py` four cases (`clean`, `after-issue`, `after-launch`, `inbox-while-down`), `test_public_only.py`, snapshot, steps, and smoke tests pass. Run `ruff check`, `ruff format --check`, and `pyright` once
- [ ] Record the run time. If the directory takes more than the default suite can reasonably carry (say so to the PM rather than deciding), report it; do not move tests silently

**Success Criteria**:
- [ ] All pass; `ruff` and `pyright` clean
- [ ] No commit unless fixes were needed (`fix:` or `style:`)

---

## Section 7: Restart Matrix (load tier)

### Task 7.1: A kill at every step boundary
**Owner**: Junior AI
**Dependencies**: 6.6
**Effort**: 3
**Objective**: Eleven cases, one per step, each followed by restart, completion, and the same comparison.

**Steps**:
- [ ] Create `tests/load/test_restart_matrix.py` parametrized over the eleven `after-step-N` members of `KillPoint`. Reuse `run_sequence` from `tests/contract/test_lifecycle_proof.py` through `sys.path` as `tests/load/conftest.py` does for shared harnesses; do not copy it
- [ ] Each case asserts the same things as Section 6: completion, snapshot equal to the clean run's (no allowed differences, except where a boundary coincides with a named point whose table row applies), transcripts equal
- [ ] The driver already handles both owners (Task 5.9): runner-owned boundaries are killed by `ProofRunner` itself, actor-owned boundaries (1, 5, 8, 9, 10) by the harness once the step's state-afterwards holds. Assert in the test, from `KILL_OWNER`, that both kinds appear among the eleven cases

**Success Criteria**:
- [ ] `uv run pytest tests/load/test_restart_matrix.py -v` runs eleven cases, all passing, twice in a row
- [ ] `ci.yml` needs no change (it already runs `tests/load`); confirm by reading it
- [ ] Commit `test: add restart matrix with a kill at every step boundary`

---

## Section 8: Store Locality Under the Sequence

### Task 8.1: Working-directory split and two projects
**Owner**: Junior AI
**Dependencies**: 6.6
**Effort**: 2
**Objective**: The process starts from one working directory and every CLI actor runs from another; all resolve the same supervisor directory.

**Steps**:
- [ ] `tests/contract/test_locality.py`: confirm the harness starts the host with `cwd` set to one directory and runs actors with `cwd=work_dir` (Task 4.6); assert after a clean run that all stores, the lock, the inbox directories, and the detection sidecars are under the supervisor directory and that `work_dir` and the host's working directory contain no `amoeba` files
- [ ] `proof` and `proof-b` in one supervisor directory (from the clean run): each project's `runnable`, `blocked`, `verdicts`, and feed never show the other's rows (call the shared helper from Task 5.9a; do not duplicate it); `inspect projects` lists both

**Success Criteria**:
- [ ] Tests pass
- [ ] Committed with Task 8.2

### Task 8.2: Three directory resolutions
**Owner**: Junior AI
**Dependencies**: 8.1
**Effort**: 3
**Objective**: Three full clean runs resolve the supervisor directory by `AMOEBA_STORE_DIR`; by `XDG_CONFIG_HOME` only; by neither, with `HOME` pointed at a temporary directory.

**Steps**:
- [ ] Parametrize the clean run over the three environments. The harness must pass the environment explicitly to the host and every actor (copy `os.environ`, remove the other variables, set `HOME` for the third). `DEFAULT_STORE_DIR` is computed at import from `Path.home()`; each subprocess gets its own `HOME`, so this works across processes. Do not monkeypatch in-process
- [ ] Assert each run's store, lock, inbox, and sidecar files land under the expected directory (`$AMOEBA_STORE_DIR`; `$XDG_CONFIG_HOME/amoeba`; `$HOME/.config/amoeba`) and nowhere else under `tmp_path`. For the third, the Squadron runs directory is still passed explicitly, never the default
- [ ] Assert a relative `AMOEBA_STORE_DIR` and a relative `XDG_CONFIG_HOME` are each refused by `status`, `start`, `submit`, `inspect`, and `feed` (exit nonzero, message names the variable). A project id with an uppercase letter, a space, or a non-ASCII character is refused by `submit` (exit 9, nothing written); `open_project` and `Store.open` refusals are already covered by Task 2.4: reference them rather than repeating

**Success Criteria**:
- [ ] Tests pass; the three-resolution runs add no more than their own clean-run time each (report the figure)
- [ ] Commit `test: prove store locality under the lifecycle sequence`

---

## Section 9: Pruning (D7)

### Task 9.0: Move the Squadron run-file reader into `amoeba.upstream.squadron`
**Owner**: Junior AI
**Dependencies**: 3.3, 1.1 (105 present)
**Effort**: 2
**Objective**: The pruning classifier must read run files without importing from the process layer. `parse_run_file` and `SquadronRun` currently live in `amoeba/process/observers/sq_runs.py`. This is a behavior-preserving move, and it is a small addition to the LLD (which only says `run_pruning.py` sits next to 105's parser); report it to the PM with the task summary.

**Steps**:
- [ ] First check whether 105 already exposes a run-file reader in `amoeba.upstream.squadron`. If it does, point the observer at it and skip the move
- [ ] Otherwise create `src/amoeba/upstream/squadron/run_files.py` holding `SquadronRun`, `parse_run_file`, and the one named constant for Squadron's `paused` status string. Move them unchanged (same fields, same logging, same `None`-on-failure behavior). `process/observers/sq_runs.py` imports them from the new module. Process may depend on upstream; the reverse is never allowed
- [ ] Export `SquadronRun` and `parse_run_file` from the package `__init__` and add them to the squadron pin test from Task 3.3

**Success Criteria**:
- [ ] `tests/test_observer_sq_runs.py` and `tests/test_recovery.py` pass with no edits to their assertions
- [ ] `grep -rn "amoeba.process" src/amoeba/upstream` finds nothing
- [ ] Committed with Task 9.0a

### Task 9.0a: Check the move against real run files
**Owner**: Junior AI
**Dependencies**: 9.0
**Effort**: 1
**Objective**: The moved reader still reads every captured run.

**Steps**:
- [ ] Add a test in `tests/upstream/` (create the directory if absent) that calls `parse_run_file` on each file in `tests/fixtures/sq_runs/` and asserts none returns `None`, and that the captured paused run reports the `paused` constant as its status

**Success Criteria**:
- [ ] Test passes; full default suite passes
- [ ] Commit `refactor: move Squadron run-file reader into the upstream package`

### Task 9.1: `run_pruning.py`
**Owner**: Junior AI
**Dependencies**: 9.0, 3.3, PM naming ruling (Task 1.1)
**Effort**: 3
**Objective**: `classify_paused_runs(runs_dir, *, owned) -> list[RunDisposition]`, pure over a directory listing and an ownership map; reads files, writes nothing.

**Steps**:
- [ ] Create `src/amoeba/upstream/squadron/run_pruning.py`. Use the names the PM ruled in Task 1.1 (proposed: `RunDisposition` for the frozen result record with `run_id`, `path`, `status` (Squadron's string, or `None` if unreadable), `disposition`, `owner_node_ids`; `DispositionKind` for the `StrEnum` `prunable`, `not_owned`, `not_paused`, `owner_not_done`, `unreadable`). Read runs with `parse_run_file` and the `paused` constant from `run_files.py` (Task 9.0). Import nothing from `amoeba.process`
- [ ] Classification order per the LLD: unreadable (cannot read or parse) → `unreadable`; run id not in `owned` → `not_owned`; status not `paused` → `not_paused`; any owning node not `done` → `owner_not_done`; otherwise `prunable`. `owned` maps run id to the nodes that reference it (`Mapping[str, Sequence[Node]]`)
- [ ] `parse_run_file` returns `None` for any unreadable file, including one Squadron removed between listing and reading. When it returns `None`, check whether the path still exists: if it does not, omit the row, with a comment that Squadron pruned it in between so there is nothing to report; if it does, the row is `unreadable`. Any other unexpected error is logged with `logger.exception` and re-raised. A malformed file is a normal `unreadable` row, not an exception
- [ ] The module imports no store internals (only `Node` from `amoeba.store`'s public exports) and writes nothing; export `classify_paused_runs` and the two ruled names from the package `__init__` and add them to the squadron pin test from Task 3.3

**Success Criteria**:
- [ ] Module near or under 150 lines; `ruff`, `pyright` strict clean; the store still imports nothing from `amoeba.upstream`
- [ ] Committed with Task 9.2

### Task 9.2: Test `run_pruning.py` against fixtures
**Owner**: Junior AI
**Dependencies**: 9.1
**Effort**: 3
**Objective**: Each disposition, using real captured files, and byte-for-byte read-only.

**Steps**:
- [ ] `tests/upstream/test_run_pruning.py` (create `tests/upstream/` if absent; mirror `tests/process` layout): copy `tests/fixtures/sq_runs/*.json` into `tmp_path`. Build ownership maps by hand with `Node` objects (made through a temp store, not constructed raw if the model requires store ids). Cases: the captured paused run owned by a `done` node → `prunable`; same file with no owner → `not_owned`; a completed run owned by `done` → `not_paused`; the paused run owned by a `runnable` node → `owner_not_done`; two owners, one not done → `owner_not_done`; a truncated JSON file and an empty file → `unreadable`; a file deleted between listing and reading (use a directory listing hook or delete during iteration) is silently absent
- [ ] Real-input test per project rule: classify the whole real fixtures directory with an empty ownership map and assert every file is reported, none silently dropped
- [ ] Assert every file's bytes and mtimes are unchanged afterward

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `feat: classify paused Squadron runs for pruning`

### Task 9.3: `amoeba prune sq-runs` command
**Owner**: Junior AI
**Dependencies**: 9.2
**Effort**: 3
**Objective**: The read-only report (D7 CLI table).

**Steps**:
- [ ] Create `src/amoeba/cli/prune.py` and register it in `cli/main.py` following how `submit` and `inspect` register. Flags: `--sq-runs-dir PATH` (default is `DEFAULT_SQ_RUNS_DIR` imported from `amoeba.process.settings`, not a new literal) and `--json`. Add no `ExitCode`: print the report and return `OK`; any unexpected error goes through the existing boundary handler to `FAILURE`
- [ ] Build the ownership map: for each project in the supervisor directory, open the store read-only; for each node take `sq.run_id`; call `recorded_result_run_ids(project_id)` (read its docstring for the shape of what it returns) and map each run id to the node that owns its journal entry. If a recorded run id cannot be tied to a node, stop and ask the PM; the LLD does not say how to classify it
- [ ] Output: one row per run file with `run_id, path, status, disposition, owner_node_ids` (table by default, JSON array with `--json`). Match the table helper `inspect` uses (`cli/inspect.py`) instead of writing a new one
- [ ] The command opens every store read-only (`Store.open_read_only`) and writes nothing, including nothing in the runs directory

**Success Criteria**:
- [ ] `amoeba prune sq-runs --help` works; `amoeba --help` lists the command
- [ ] Committed with Task 9.4

### Task 9.4: Test the command
**Owner**: Junior AI
**Dependencies**: 9.3
**Effort**: 2
**Objective**: CLI end to end on built stores, using the harness.

**Steps**:
- [ ] `tests/cli/test_prune.py`: build a supervisor directory with two projects through the public `Store` API (owned paused run on a `done` node; paused run on a `runnable` node; a completed run) and a runs directory with those files plus the captured paused fixture. Assert the text and `--json` outputs list every file with the right disposition and path. Assert the runs directory listing and every file's bytes are identical before and after
- [ ] Assert no store file in the supervisor directory changed (compare bytes or mtime before and after) and no new file appeared

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `feat: add amoeba prune sq-runs report`

### Task 9.5: Pruning assertions in the proof
**Owner**: Junior AI
**Dependencies**: 9.4, 5.9a
**Effort**: 2
**Objective**: Per the LLD success criterion, on the real sequence's leftovers.

**Steps**:
- [ ] In `test_lifecycle_proof.py` after the clean run: copy `tests/fixtures/sq_runs/run-20260505-review-a697ad3d.json` into the same runs directory; add a paused run owned by a `runnable` node (create a second slice node in a throwaway store the test builds before the host stops, or in `proof-b`, which never finishes; use `proof-b`, whose step 3 leaves a completed run, and add a paused run for it via `fake_squadron` and the public `update_sq_reference`)
- [ ] Run `amoeba prune sq-runs --sq-runs-dir <runs> --json` through the Inspector helper. Assert: the step-6 run is `prunable` with its path; the copied fixture is `not_owned`; the step-3 run is `not_paused`; the `proof-b` paused run is `owner_not_done`; every file in the runs directory is byte-identical before and after the command

**Success Criteria**:
- [ ] Test passes
- [ ] Commit `test: assert pruning report against the lifecycle proof`

---

## Section 10: Documentation and the Contract Index

All markdown carries YAML front matter per `file-naming-conventions.md` where the existing `docs/*.md` files do. Read the front matter of `docs/store-contract.md` once and copy its shape.

### Task 10.1: Hosting a tenant in `process-contract.md`
**Owner**: Junior AI
**Dependencies**: 5.9a
**Effort**: 2
**Objective**: A "Hosting a tenant" section a 120 designer can follow without reading source.

**Steps**:
- [ ] Add the section: the exported names, `standard_tenants` order (inbox first, detection second), and the construction lines quoted verbatim from `proof_host.py` as Task 5.9 left it (standard tenants followed by `ProofRunner`); re-open the file now rather than quoting Task 4.7's earlier version. State that `amoeba start` calls `standard_tenants` too, so there is one list. State that a `--tenant` flag is not provided (120 may add it)
- [ ] Document `amoeba prune sq-runs` and the unchanged exit-code behavior; update the exports list if the contract has one

**Success Criteria**:
- [ ] The quoted lines match `proof_host.py` exactly (diff them)
- [ ] Commit `docs: add hosting-a-tenant section to process contract`

### Task 10.2: Update `store-contract.md` for D5 and D6
**Owner**: Junior AI
**Dependencies**: 2.6
**Effort**: 2
**Objective**: Record the narrowing and the enforcement as changes to 101's contract.

**Steps**:
- [ ] Locate the paragraphs on directory resolution ("used verbatim"), project ids, and `done`. Rewrite: both directory variables must be absolute and a relative value raises `ValueError` naming the variable; project ids are ASCII slugs with the pattern (copy it from the constant), with the reasons; `done` is final with the four refusals listed. Remove any "known limit" line about case-insensitive collisions
- [ ] Put the mapping rule where 120 will find it: "mapping a Context Forge project name to an Amoeba project id is the Runner's job; it must produce a slug"

**Success Criteria**:
- [ ] Each of the three contract statements matches the code (spot check by running the examples in the text)
- [ ] Commit `docs: update contracts for hosting seam, locality, and terminal done`

### Task 10.3: Squadron dependency entry
**Owner**: Junior AI
**Dependencies**: 2.6
**Effort**: 1
**Objective**: Ask Squadron for a command that discards a paused run, without tying it to a version.

**Steps**:
- [ ] Read the existing entries in `project-documents/user/notes/001-squadron-dependencies.amoeba.md` once and match their format. Add an entry dated 20261008: Amoeba needs a Squadron command that discards one paused run by id; Amoeba decides which runs are dead (`amoeba prune sq-runs`) and never deletes Squadron files; when the command exists, a later slice adds `--apply`. Do not name a Squadron version
- [ ] Do not edit anything under `ai-project-guide/` (the submodule)

**Success Criteria**:
- [ ] Entry present, dated, no version number
- [ ] Commit `docs: add Squadron prune-command dependency`

### Task 10.4: `docs/README.md` — the contract index
**Owner**: Junior AI
**Dependencies**: 10.1, 10.2, 10.3
**Effort**: 3
**Objective**: One entry document (D8), every answer one link away.

**Steps**:
- [ ] Sections in order: **Which document answers what** (one row for every contract document that exists in `docs/` when you write it: run `ls docs/*.md` and list each file, including any added by 105–109 such as `network-contract.md` and any feed or detection contract; do not list from memory. Each row names the questions that document answers; for sections that 105–109 added to an existing contract, say so in the row); **The public packages** (the five, with their pinned-export tests linked); **Hosting a Runner** (link to Task 10.1's section, and the "work out the step from the store" pattern with a link to `tests/contract/proof_runner.py`); **Obligations on consumers**; **Known limits**; **Contract gaps** (link to the gap table, Task 10.5)
- [ ] Obligations list, each a bullet with a link to the source section (open each contract and link its real heading; do not link from memory): journal before side effect; issue `sq` with non-TTY stdin and resume only by explicit id; attach reviews by `attribute_review`; report back in one transaction from the artifact through 105's parser; poll `stop_requested` and return promptly; never cache `project_ids`; save a feed cursor after acting and make handling repeatable; resolutions target a blocked state, not a node; wait for `create_project` to apply before submitting into it; no secrets in any payload; project ids are slugs; `done` is final
- [ ] Known limits: link each contract's future-work section. If a link target is missing, say so to the PM rather than inventing one
- [ ] Add the five Integration Requirements questions (host the Runner; journal, launch and report back a Squadron review; block and learn of a resolution; follow the feed; valid project ids and what never to do) as the first screen, each with one link

**Success Criteria**:
- [ ] Every obligation has a working link to a heading that states it
- [ ] Committed with Task 10.5

### Task 10.5: Gap table and link test
**Owner**: Junior AI
**Dependencies**: 10.4
**Effort**: 2
**Objective**: The gap table is complete, and the index cannot rot silently.

**Steps**:
- [ ] Put the LLD's gap table in `docs/README.md` ("Contract gaps") with its five rows and dispositions, plus one row for every gap found while doing Sections 5–7 (implementation-time findings, with disposition: fixed here, or assigned to a slice). If none were found, write "No further gaps found by the proof" with the date
- [ ] `tests/test_docs_links.py`: for every `docs/*.md`, parse markdown links with relative targets and `#anchor` fragments; assert each file exists and each anchor matches a heading in the target (slugify headings the way GitHub does: lowercase, strip punctuation, spaces to hyphens). Cover links to `tests/` files. Include a self-test with a deliberately broken link in an in-memory string
- [ ] Fix any broken link in existing contracts that the test finds

**Success Criteria**:
- [ ] `uv run pytest tests/test_docs_links.py` passes and fails on the planted broken link in its self-test
- [ ] Commit `docs: add contract index README and link check`

### Task 10.6: `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: 10.5
**Effort**: 1
**Objective**: Name the changes to 101's contract and the additions.

**Steps**:
- [ ] Match the existing entry format (read the top of `CHANGELOG.md` once). Under the current unreleased heading list: changes to 101's contract (relative directory variables refused; project ids restricted to ASCII slugs; `done` terminal with the four refusals); additions (`amoeba.process` hosting seam and `standard_tenants`; export pins; `amoeba prune sq-runs`; `docs/README.md`; contract proof tests and restart matrix)

**Success Criteria**:
- [ ] Entry present; the three contract-changing items are labeled as such
- [ ] Commit `docs: update CHANGELOG for contract proof and hardening`

---

## Section 11: Final Validation

### Task 11.1: Full validation and walkthrough
**Owner**: Junior AI
**Dependencies**: 10.6
**Effort**: 2
**Objective**: Everything green; the LLD walkthrough run once with real output.

**Steps**:
- [ ] Run once each: `uv run pytest` (default suite), `uv run pytest tests/load`, `uv run ruff check .`, `uv run ruff format --check .` (CI runs it as its own step), `uv run pyright`. Fix failures at the cause. Check no source file exceeds roughly 300 lines (`wc -l` on new and edited files) and split any that do
- [ ] Confirm the structural criteria: the store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed` (grep); `run_pruning.py` imports no store internals (grep); `test_writer_guard.py` passes; `proof_host.py` opens stores only through `ResidentProcess`
- [ ] Run the LLD's Verification Walkthrough steps 1–6 (bash, repo root). For step 4 use a fresh `mktemp -d` store directory. Note any differences from the draft text (output shapes, test directory names) and update the LLD's walkthrough with the real output, keeping the LLD's front matter dates current
- [ ] Review the LLD Success Criteria list line by line against the tests; for any criterion with no test, add the test or report it to the PM
- [ ] Delegate the checklist update for both task files to the `task-checker` agent

**Success Criteria**:
- [ ] Default suite, load tier, `ruff check`, `ruff format --check`, and `pyright` all clean
- [ ] Every LLD success criterion maps to a passing test, or the gap is reported
- [ ] Walkthrough text refined with real output and committed: `docs: refine slice 110 walkthrough with real output`
- [ ] Work is committed on `110-slice.contract-proof-and-hardening`; no merge
