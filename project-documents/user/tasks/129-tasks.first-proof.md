---
docType: tasks
slice: first-proof
project: amoeba
lld: user/slices/129-slice.first-proof.md
dependencies:
- 120
- 121
- 122
- 123
- 124
- 125
- 126
- 127
- 128
projectState: Slices 120–128 are merged into main and the Runner is complete as
  designed. Each part has been proven against stubs, scratch copies or this
  repository's plan, but the Runner has never driven real work. `amoeba inspect`
  has no listing of resolved blocks (issue #16). Issue #14 (pruning must hold
  Runner-paused runs) was still open on 20261027.
dateCreated: 20261027
dateUpdated: 20261027
status: not_started
---

## Context Summary

- Working on the **first-proof** slice (129), the last slice of initiative 120 before 130 and 131. The Runner drives one PM-chosen, unstarted slice in a separate real project from `slice_design` to the human `merge`. Every stop is recorded and classified, and each wrong stop becomes a routing-table edit or a follow-on proposal.
- **Current state:** see `projectState`. The routing table ships as `src/amoeba/runner/routing/tables/default.yaml`. `inspect blocked` lists open blocks only.
- **Dependencies:** 120–128, all merged. 106 (`watch-reviews`, detections). Squadron and CF are checked by shape by the start-up probe, so their versions are recorded as observations, not pinned.
- **What this slice delivers:** `amoeba inspect resolutions` (D6); the proof run (D3, D4); the stop write-up `user/analysis/120-analysis.first-proof-stops.md` (D5); table edits with fixtures and `tests/runner/routing/test_first_proof_rules.py` (D7); `docs/runner-guide.md` and the substrate guide close-out (D8); CHANGELOG.
- **Next planned slices:** 130 (batch dispatch) and 131 (tier inference). The write-up's proposals are their scope input.

**Branch:** all work happens on `129-slice.first-proof`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task merges anything. Task 3.5 only observes the PM's merge in the target project.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/129-slice.first-proof.md` at the named decision (D1–D9), "Implementation Details" or "Verification Walkthrough" step. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Keep new or changed source files near 300 lines and functions near 50.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off.

**Commit cadence:** each task ends in one commit, unless it says otherwise. An implementation task without a commit step is committed with the test task after it. Run `uv run ruff format .` before each commit. Types: `feat:`, `test:`, `docs:`, `review:` (the write-up), `fix:` only under D9.

### Slice preconditions

These are inputs this file cannot supply. Task 1.2 checks them. If one is missing, Task 1.2 writes `BLOCKED:` and the proof (Sections 3–5) waits; Section 2 does not depend on them.

- [ ] **Proof unit named.** The PM has written the project, its CF project id, the slice index and name, the target checkout's path and its absolute reviews directory under "Proof unit" below. The unit meets D1's four criteria.
- [ ] **Issue #14 closed** (`gh issue view 14 --json state -q .state` prints `CLOSED`). It was `OPEN` on 20261027.

**Proof unit** (filled in by the PM):
- Project / CF project id: —
- Slice index and name: —
- Target checkout / reviews directory: —

### Roles in the proof (Sections 3–4)

The LLD makes three acts the PM's, by definition, not as approvals: choosing the resolution's decision at each stop (Data Flow 3), the git merge at the human `merge` step (D1, walkthrough step 6), and each stop's classification (D5). Sections 3 and 4 are worked in a session with the PM present. The agent runs every command, keeps the D4 log, and drafts each stop's row. For each stop it presents the block, its escalation and its decision to the PM, then submits the decision the PM gives. An item marked **(PM)** is the PM's act; the agent records that it happened. The agent never chooses a resolution, classification or merge itself.

**Task-level additions to the LLD** (code facts the LLD does not state, checked on 20261027):
- **Where `step` and `reason` come from.** `BlockedState` has `node_id`, `kind` and `context` but no step or reason. The step is the blocked node's `cf.phase` for a `phase_or_artifact` node, which is the rule in `runner/lifecycle/tree.py` `LifecycleTree.step_of`. Reuse that rule. If calling it from `amoeba.inspection` needs a tree the listing does not have, extract the rule into one function that both call. Do not copy it. The reason is the `reason` key of the escalation message's payload, joined by `blocked_state_id`. For a fault block, which has no `reason`, use its `fault_kind` (`runner/faults.py` `PAYLOAD_FAULT_KIND`). For a block with no escalation message, use null. Reuse the existing payload key constants. Do not add new string literals.
- **`accepted_verdict_ids`.** `runner/gates/accepted.py` `accepted_by_pm(entries, latest_blocked)` already identifies an accept from the step's journal entries and the blocked state. For a resolved block, call it with that block and with the step's entries created before the block's `created_at`, so an older accept reads the run it accepted. The value is null unless the result is not `None`.
- **The new store read.** `Store.resolved_blocked_states(project_id, *, node_id=None) -> list[BlockedState]`, in `store/blocking.py`. It returns resolved blocked states, ordered by `resolved_at` then `id`, through the existing `BLOCKED_STATE_COLUMNS` and `map_blocked_state`. `store/sql.py` is already 364 lines, so the SQL constant goes in `store/sql_runner.py` (278 lines). If that file would pass about 300 lines, put it in a new `store/sql_resolutions.py`.
- **The listing.** A new `inspection/resolutions.py` holds `RESOLUTION_COLUMNS` and `resolution_rows`. It is registered in `inspection/__init__.py` like `routing-decisions`, with `value_options=(NODE_OPTION,)`. `NODE_OPTION` spells the flag `--node` (`inspection/listing.py`), so the listing takes `--node`, not the LLD's `--node-id`, like every other listing. Do not add a second option. Task 2.5 records this spelling in the contract text.
- **Walkthrough step 1's branch check does not work.** `git branch --merged main` lists 122–128 only, because the tips of the 120 and 121 branches carry commits that are not on main. Task 1.2 checks the slice plan's ticks and the `merge` commits instead.
- **Shipped-table test.** `tests/runner/routing/test_default_table.py` asserts the rule ids in order and the time bounds. A D7 edit that adds, removes or reorders a rule, or changes a bound, updates that test in the same commit.
- **Exceptions.** Add no `except Exception`. Each `except` names a specific exception with a comment, or re-raises after `logger.exception`.

**Section map.** 1 baseline and preconditions; 2 `inspect resolutions` (D6); 3 the proof run (D3, D4, D9); 4 the stop write-up (D5); 5 table edits (D7); 6 operator guide and close-out (D8); 7 final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and confirm a green baseline
**Effort:** 1/5. **Dependencies:** none.

- [ ] Read the target with `cf config get git.integration_branch`. An empty value means `main`.
- [ ] Create `129-slice.first-proof` from the target, or switch to it if it exists.
- [ ] Run `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check .` and `uv run pyright`.
  - [ ] All four pass before any change. If one fails, file an issue with the output and stop. A red baseline would make the proof's evidence unreadable.

### Task 1.2: Check the preconditions and open the write-up
**Effort:** 1/5. **Dependencies:** 1.1.

- [ ] Check the slice preconditions above.
  - [ ] `gh issue view 14 --json state -q .state` prints `CLOSED`.
  - [ ] "Proof unit" is filled in, and the unit meets D1. It is not this repository. It has no slice design file. Its initiative's slice plan is complete. It is real code, not docs only.
  - [ ] If either check fails, write `BLOCKED:` and the reason under this task and continue with Section 2.
- [ ] Check that 120–128 are complete. Entries 1–9 of `user/architecture/120-slices.runner-routing-engine.md` are ticked `[x]`, and `git log --oneline <target>` shows a merge commit for each of 120–128.
- [ ] Create `project-documents/user/analysis/120-analysis.first-proof-stops.md` with frontmatter per `file-naming-conventions.md` (`docType: analysis`, `status: in_progress`). Add the header recording the D1 choice, then empty sections for: Stops, Answers to deferred questions, Gate disagreements, Defects and restarts (D9), Command log (D4), and Evidence appendix.
- [ ] Commit `review: open the first-proof stop write-up`.

---

## Section 2: `amoeba inspect resolutions` (D6, issue #16)

### Task 2.1: Add the resolved-blocks store read
**Effort:** 2/5. **Dependencies:** 1.1.

- [ ] Add the SQL constant and `Store.resolved_blocked_states(project_id, *, node_id=None)`, as "Task-level additions" places them.
  - [ ] It joins `nodes` to scope by project, as `SELECT_PENDING_RESOLUTIONS` does. With `node_id`, it also filters to that node.
  - [ ] It returns resolved blocked states only (`resolved_at IS NOT NULL`), ordered by `resolved_at` then `id`.
  - [ ] It works through `Store.open_read_only`.
- [ ] Export it wherever `Store`'s public methods are listed for `tests/test_public_api.py`, if that test requires it.

### Task 2.2: Test the store read
**Effort:** 1/5. **Dependencies:** 2.1.

- [ ] In `tests/store/`, create `test_resolved_blocked_states.py`, using `Store.open_temporary()`:
  - [ ] `test_lists_resolved_blocks_oldest_first`: three resolved blocks come back in `resolved_at` order.
  - [ ] `test_omits_open_blocks`.
  - [ ] `test_is_scoped_to_one_project`: a resolved block in another project is not returned.
  - [ ] `test_node_filter_returns_only_that_node`.
  - [ ] `test_unacknowledged_resolution_is_listed_with_null_runner_fields`.
  - [ ] `test_reads_through_a_read_only_handle`.
- [ ] `uv run pytest tests/store -q` passes.
- [ ] Commit `feat: add resolved blocked-state store read`.

### Task 2.3: Add the `resolutions` listing
**Effort:** 3/5. **Dependencies:** 2.2.

- [ ] Create `inspection/resolutions.py` with `RESOLUTION_COLUMNS` in the LLD's "API Contracts" order: `blocked_state_id`, `node_id`, `step`, `reason`, `opened_at`, `resolved_at`, `decision`, `instructions`, `runner_outcome`, `runner_code`, `runner_reason`, `accepted_verdict_ids`.
- [ ] Implement `resolution_rows(store, request)`:
  - [ ] `opened_at` is the blocked state's `created_at`. `resolved_at` is the resolution's `resolved_at`.
  - [ ] `step` and `reason` follow "Task-level additions". A non-step node has a null step.
  - [ ] `accepted_verdict_ids` is a list for an applied `accept` that `accepted_by_pm` identifies, and null otherwise.
  - [ ] The `runner_*` fields are null while the Runner has not acknowledged the resolution. The row is still listed.
- [ ] Register the listing in `inspection/__init__.py` as `resolutions`, project-scoped, with the node option. Help text: "Resolved blocks for a project, oldest first, and what the Runner did with each."
- [ ] Check that `amoeba inspect resolutions --help` shows `--project`, `--node` and `--json`.

### Task 2.4: Test the listing
**Effort:** 2/5. **Dependencies:** 2.3.

- [ ] Create `tests/inspection/test_resolutions.py`, using the helpers in `tests/inspection_harness.py` and the patterns in `tests/inspection/test_routing_decisions.py`. Name each test for the rule it proves:
  - [ ] One test per column source: the block fields, the resolution fields, the `runner_*` fields of an applied and of a rejected resolution, and `step` for a step node.
  - [ ] `reason` for a routed escalation, for a fault block (`fault_kind`), and null for a block with no escalation message.
  - [ ] `accepted_verdict_ids` set for an applied accept of a completed run, and null for a `retry`, for a rejected accept and for a loop accept.
  - [ ] An older accept on a step that was blocked again later still reads the run it accepted.
  - [ ] An unacknowledged resolution is listed, with null `runner_*` fields.
  - [ ] `--node` returns only that node's rows.
  - [ ] `--json` and the table form both work through the CLI.
  - [ ] A store at another schema version exits with the `StoreSchemaError` code, as the other listings do (see `tests/test_read_only_open.py`).
- [ ] `uv run pytest tests/inspection tests/test_cli_inspect.py -q` passes.
- [ ] Commit `feat: add amoeba inspect resolutions listing (#16)`.

### Task 2.5: Contract text for the read and the listing
**Effort:** 1/5. **Dependencies:** 2.4.

- [ ] In `docs/store-contract.md`, under "Resolution answers", document `resolved_blocked_states`: what it returns, its order, its scope and its node filter. Say that it serves operators, not the Runner (LLD D6).
- [ ] Where the other `inspect` listings are documented (find `routing-decisions` in `docs/`), add `resolutions`, its columns and the unacknowledged case. Link the store contract. Do not copy it.
- [ ] `uv run pytest tests/contract -q` passes.
- [ ] Commit `docs: document resolved-blocks read and inspect resolutions`.

---

## Section 3: The proof run (D3, D4, D9)

Worked with the PM present (see "Roles in the proof"). Every `<…>` value comes from "Proof unit". Record each command that changes state in the write-up's Command log as it is run, with the time and the block id that sent you there, if any. Keep secrets out of the log and out of resolution text.

**Defects (D9).** A defect in 120–128 code is handled by the Fixes rule, never worked around. File the issue. For a small fix, commit it to the *target* as `fix:` with a failing test first and `Fixes #n`. Then merge the target into `129-slice.first-proof`, which is a clean sync, and restart the resident process. If the sync conflicts, stop and ask the PM. Record the fix, the issue and the restart under "Defects and restarts". A defect that does not stop the proof is filed and noted, and the proof continues. A defect that makes the unit unrecoverable ends the attempt. Write it up, fix it, and the PM names a fresh unit (D1). Both attempts stay in the write-up.

### Task 3.1: Start the Runner and link the project
**Effort:** 1/5. **Dependencies:** 1.2 (preconditions met), 2.5.

- [ ] Create a dedicated supervisor directory outside both repositories. Record its path in the write-up. Do not prune or delete it until Task 7.1 is committed.
- [ ] Run LLD walkthrough step 2 with `AMOEBA_STORE_DIR` set to it: `start`, `create-project`, `link-cf-project`, `watch-reviews` with `--active true`, then `inspect nodes`.
  - [ ] The slice's node exists with four step rows, and `slice_design` is runnable. No escalation is open.
- [ ] Record in the Evidence appendix: `sq`, `cf` and `amoeba` versions, and this repository's commit (`git rev-parse HEAD`).

### Task 3.2: Drive the unit
**Effort:** 1/5. **Dependencies:** 3.1.

- [ ] Submit the single `{"intent": "drive"}` intent on the slice node (walkthrough step 3). Submit no other intent on any other node.
  - [ ] The intent is acknowledged `applied` (`inspect desired-states`).
  - [ ] Within a tick or two, `inspect journal` shows a `cf_write` and then an `sq_run` for `P4`.
- [ ] Do not edit `default.yaml` or restart with `--routing-table` from here until Section 5 (D2).

### Task 3.3: Answer each stop as it comes
**Effort:** 3/5. **Dependencies:** 3.2. Repeats until the `merge` step blocks as a human step.

- [ ] Poll `inspect blocked --project <P>`. For each new block:
  - [ ] Read its escalation (`inspect messages`) and its decision (`inspect routing-decisions --node <node>`). For a fault, read its `fault_kind`.
  - [ ] Present the block, the escalation and the decision to the PM.
  - [ ] **(PM)** The PM gives the decision (`retry`, `accept`, `handled`, `rerun` or `stop`) and any instructions.
  - [ ] Submit it with `submit resolution --blocked-state-id <id>` (walkthrough step 4). Log the command with its block id.
  - [ ] Confirm the Runner's acknowledgment (`inspect resolutions --node <node>`). A `rejected` one is a stop in its own right. Present it to the PM and log it.
  - [ ] Add a draft row to the write-up's Stops section, using D5's fields. Leave the classification blank.
- [ ] If the PM acts by hand at a step the table sent them to, such as launching a run, log the action with its block id.
- [ ] Repeated stops of the same kind are answered the same way each time and recorded each time. Do not edit the table (D2).

### Task 3.4: Crash the resident process with `P6` in flight
**Effort:** 2/5. **Dependencies:** `P6`'s `sq_run` is confirmed in `inspect journal` (inside Task 3.3).

- [ ] As soon as `P6`'s launch is confirmed, `kill -9` the resident process, then run `amoeba start` again (walkthrough step 5). Log both, with the time.
- [ ] Check D3's pass conditions and record each one in the write-up with its evidence:
  - [ ] `sq runs list` still shows the run running after the kill.
  - [ ] After the restart, the entry stays unresolved until the run finishes, and then resolves `completed`, or whatever the run's real outcome is.
  - [ ] The step has exactly one `sq_run` entry for that attempt (`inspect journal --json`).
- [ ] If `P6` finished before the kill, it is a miss, not a pass. Repeat at the unit's next in-flight run. If no run remains in flight, the crash criterion is unmet. Write `BLOCKED:` here, and the PM names a second unit per D1, which is driven through Tasks 3.1–3.4 in the same supervisor directory.

### Task 3.5: Observe the human merge
**Effort:** 1/5. **Dependencies:** 3.3 (the `merge` step is blocked as a human step). The merge itself is the PM's act at that human step in `<target-checkout>`, under that project's rules. It is not a task. The agent logs it when the PM reports it.

- [ ] Confirm that `P6` ran with `merge=false` (the `P6` entry's `merge_policy` and parameters), and that the `merge` step is blocked as a human step.
- [ ] Confirm the observation. The `merge` step goes `done`, and so does the slice node (`inspect nodes`). If it does not, apply D9.
- [ ] The unit's `slice_design`, `tasks`, `implementation` and `merge` steps are all `done`.

### Task 3.6: Audit and export the evidence
**Effort:** 2/5. **Dependencies:** 3.5 (and 3.4's pass).

- [ ] Run walkthrough step 7.
  - [ ] Every routing decision for the unit shows `recomputes: yes`. If any does not, file it under D9 and record it.
  - [ ] Each `ingested` detection after the drive intent matches a Command-log entry with a block id. List each one in the write-up. An unmatched one is a hand-run command and goes in the write-up as a finding.
  - [ ] `inspect resolutions` covers every block the Stops section lists.
- [ ] Export `--json` for `nodes`, `journal`, `routing-decisions`, `blocked`, `resolutions`, `detections`, `messages` and `checks --node <slice-node>` into `project-documents/user/analysis/120-analysis.first-proof-evidence/`. If the export is short, put it inline in the Evidence appendix instead. Check it for secrets before staging.
- [ ] Record every `amoeba` commit the process ran on (Task 3.1, plus each D9 restart).
- [ ] Commit `review: record first-proof run and evidence`.

---

## Section 4: The stop write-up (D5)

### Task 4.1: Complete every stop row
**Effort:** 2/5. **Dependencies:** 3.6.

- [ ] Check that the Stops section has exactly one row per block on the unit's nodes, plus each project-scoped escalation raised during the proof and the human `merge` step. Each row has block id, node, step, rule id, inputs and `judge_eligible` (or fault kind), and what the PM did (from the Command log).
- [ ] Draft each row's proposed classification and, for a proposed wrong one, one proposal per D5. A fault row's proposal is never a table edit. A proposal needing a new routing input goes to 131, not the table (D7).
- [ ] **(PM)** The PM confirms or changes each classification and proposal. Record the final values.
- [ ] Each `wrong` row has exactly one proposal. Each table-edit proposal carries its rule as YAML, and the rule id and route the wrong decision should reach.

### Task 4.2: Answers, gate disagreements and the judge list
**Effort:** 2/5. **Dependencies:** 4.1.

- [ ] Answers to deferred questions, each from the evidence:
  - [ ] Issue #12 (intent fault scope): did a faulting intent stall Observe?
  - [ ] Issue #13 (`routing-table check`): would it have caught anything the run met?
  - [ ] Future Work 2 (a retry class for transient faults): which fault stops were transient?
  - [ ] 126's time bounds (P4/P5 240 min, P6 720): the observed run lengths from `journal` timestamps, and whether each bound fits.
- [ ] Gate disagreements: list every `cf_gate_accept_disagreement` check on the slice node, or state that there were none.
- [ ] List the judge-eligible escalations and how the PM resolved each, for 140.
- [ ] State what the store cannot detect (D4): a `cf set` with no run in flight, a Squadron command that writes no review artifact, and git commands.
- [ ] Commit `review: classify first-proof stops`.

---

## Section 5: Table edits (D7)

If Task 4.1 has no `wrong` row whose proposal is a table edit, write "No table edit: no wrong stop is fixed by a table change" in the write-up. Mark Tasks 5.1–5.3 with that line, leave them unchecked, and go to Section 6.

### Task 5.1: Export decision fixtures
**Effort:** 2/5. **Dependencies:** 4.2.

- [ ] For every routing decision of the proof, not only the wrong ones, write `tests/runner/routing/fixtures/first_proof/<decision-id>.json` from the store with its recorded `inputs`, `rule_id` and `route`. For a decision behind a `wrong` row, also write `proposed_rule_id` and `proposed_route`.
- [ ] The fixture keys are defined once, as constants in the test module that reads them (Task 5.2), and the export uses those constants.
- [ ] Check the fixtures for secrets. They should hold only enums, counts and ids.
- [ ] Add a short `README.md` in the directory: the source store, the date, and the table version the decisions were made under.

### Task 5.2: Write the first-proof rule test
**Effort:** 2/5. **Dependencies:** 5.1.

- [ ] Create `tests/runner/routing/test_first_proof_rules.py`. It loads the shipped table the way `test_default_table.py` does, and builds inputs with `RoutingInputs.from_record`, as `recompute` does.
  - [ ] A test asserts that each fixture without a proposal keeps its recorded rule id and route.
  - [ ] A test asserts that each fixture with a proposal reaches its proposed rule id and route.
  - [ ] Each wrong stop also gets a test named for the stop it fixes, for example `test_p4_concerns_on_first_round_reruns` (LLD "Patterns").
- [ ] Run it against the unedited table. The proposal assertions fail, and the others pass. Record this.

### Task 5.3: Apply the edits to the shipped table
**Effort:** 2/5. **Dependencies:** 5.2.

- [ ] Apply each table-edit proposal to `src/amoeba/runner/routing/tables/default.yaml`, as written in the write-up.
- [ ] Update `test_default_table.py`'s rule-id order and time bounds if they changed.
- [ ] `uv run pytest tests/runner/routing -q` passes, including Task 5.2's test.
- [ ] Restart the resident process on the edited table, using the proof's supervisor directory, and rerun walkthrough step 8's recompute check. Every proof decision still shows `yes`. Record it in the write-up.
- [ ] Commit `feat: add first-proof routing rules to the shipped table`.

---

## Section 6: Operator guide and close-out (D8)

### Task 6.1: Write the operator guide
**Effort:** 3/5. **Dependencies:** 3.6.

- [ ] Create `docs/runner-guide.md` in D8's order: setup; settings; driving with intents; reading stops; answering with resolutions; the routing table; merge policy; crashes and restarts; pruning.
  - [ ] Take each setting, flag and default from `src/amoeba/` settings (`settings.py`, `cli/settings_flags.py`) and `--help`, not from the slice designs.
  - [ ] Body formats, decision rules and the table grammar are linked to the sections of `docs/inbox-contract.md`, `docs/process-contract.md` and `docs/store-contract.md` that own them, not copied. State each rule once.
  - [ ] The resolutions section says which decision applies in which situation, linking 127's contract text, and uses the stops the proof met as examples.
  - [ ] Show `inspect resolutions` in "reading stops".

### Task 6.2: Verify the guide by following it
**Effort:** 2/5. **Dependencies:** 6.1.

- [ ] Run walkthrough step 9 in a fresh supervisor directory. Run the guide's setup commands as written, then `inspect nodes`. Each command succeeds, the unit's slice node and its four step rows exist, and the journal is empty.
- [ ] Check every flag and default in the guide against `--help` and the settings code.
- [ ] Check that every command in the write-up's Command log is described in the guide.
- [ ] Fix the guide wherever a check fails. Delete the fresh directory afterwards. It is not evidence.
- [ ] Commit `docs: add runner operator guide`.

### Task 6.3: Close out the substrate guide and README
**Effort:** 1/5. **Dependencies:** 6.2.

- [ ] In `docs/substrate-guide.md`, drop 120 from the opening sentence's list of initiatives being designed.
- [ ] In the 120 row, say that the Runner ships as `amoeba.runner`, keep its contract links, add links to `runner-guide.md` and the write-up, and say that the stand-in proof remains the contract evidence.
- [ ] Add a link to the operator guide in `README.md`.
- [ ] Commit `docs: close out substrate guide 120 row and link operator guide`.

### Task 6.4: Carry the proposals into the slice plan
**Effort:** 1/5. **Dependencies:** 4.2.

- [ ] In `user/architecture/120-slices.runner-routing-engine.md`, add each follow-on proposal from the write-up to 130's or 131's entry, or as a new Future Work entry. Link the write-up row. Update Future Work 2 and 10 with the answers from Task 4.2.
- [ ] Commit `docs: add first-proof proposals to the 120 slice plan`.

### Task 6.5: Update issues #12, #13 and #16
**Effort:** 1/5. **Dependencies:** 4.2, 2.5.

- [ ] #12 and #13: comment with the write-up's answer, linking it. Close an issue the write-up finds not needed, or re-scope it.
- [ ] #16: comment that `inspect resolutions` is on `129-slice.first-proof`. Leave it open until the merge.
- [ ] Each code-issue proposal from Task 4.1 has a filed issue, and the write-up row links it.

### Task 6.6: CHANGELOG
**Effort:** 1/5. **Dependencies:** 5.3 or the "no table edit" line, 6.3.

- [ ] Under `[Unreleased]`, add 1–2 line entries in the file's style: `inspect resolutions`; the operator guide; the first proof and its write-up; and each table edit. Mark a table edit **Behavior change** if it reroutes any outcome.
- [ ] Commit `docs: add slice 129 changelog entries`.

---

## Section 7: Final validation

### Task 7.1: Full validation
**Effort:** 1/5. **Dependencies:** all above.

- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check .`, `uv run pyright` and `uv run pytest tests/contract -q` all pass.
- [ ] Check the LLD's Success Criteria one by one against the write-up and the code, and note any criterion that is not met as `BLOCKED:` with its reason.
- [ ] Set the write-up's `status: complete`. After that commit, the proof's supervisor directory is no longer evidence. Do not delete it unless the PM asks.
- [ ] Commit `review: complete first-proof write-up`. The work ends here on `129-slice.first-proof`.
