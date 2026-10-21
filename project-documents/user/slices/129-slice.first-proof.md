---
docType: slice-design
slice: first-proof
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
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
interfaces:
- 130
- 131
- 140
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 37
promptTokens: 2779161
cachedTokens: 2678000
cacheWriteTokens: 101091
completionTokens: 26406
durationSeconds: 290.8
costUsd: 1.873054
usageRounds: 1
pricedRounds: 1
---

# Slice Design: first-proof

## Overview

Slices 120–128 build the Runner, and each one proves its own part against stubs, scratch copies, or this repository's plan. None of them points the Runner at real work and lets it drive. This slice does. The PM picks one unstarted slice in one real project. The Runner then drives it under intents through slice design (P4), tasks (P5), and implementation with code review (P6), up to the human merge. Every stop is recorded. Each stop the PM judges wrong becomes a routing-table edit or a follow-on slice.

The slice is mostly an operation, plus the documents that come out of it. It adds one listing (`amoeba inspect resolutions`, issue #16) that the write-up needs. Afterwards it applies the table edits the proof justifies, each with a regression test built from the decision that went wrong. It also writes the operator guide for running the Runner and closes out the substrate guide's 120 row.

## Value

- **The Runner is shown to drive real work.** Every earlier proof used a stub or a scratch copy. This is the first time a slice moves from "design pending" to "merged" with the PM acting only where the table sent them.
- **Evidence for the routing table.** The arch moves tier inference (131) and batch dispatch (130) to after this proof, so that the proof's wrong stops decide what they need. The write-up is that evidence. It also records which escalations were judge-eligible, which is 140's first evidence.
- **Answers to deferred questions.** Issue #12 (intent fault scope), #13 (`routing-table check`), Future Work 2 (a retry class for transient faults) and 126's starting time bounds were all deferred "until the first proof shows it". The write-up answers each one from what happened.
- **An operator can run the Runner.** The operator guide covers setup, settings, intents, resolutions and the routing table in one place, linking to the contracts for exact formats.

## Technical Scope

**Included**

- **The proof run.** One PM-chosen project and slice, driven by the Runner from `slice_design` through `merge` under the default human merge policy, with one forced crash of the resident process while a run is in flight (D3, D4).
- **`amoeba inspect resolutions`** (issue #16): a read-only listing of resolved blocks (D6).
- **The stop write-up** at `user/analysis/120-analysis.first-proof-stops.md`: every stop, the PM's classification, and a proposal for each wrong one (D5).
- **Table edits from the proof** (D7): each proposed rule change the write-up marks as a table edit is applied to the shipped `default.yaml`. A regression test runs every proof decision's recorded inputs through the edited table.
- **Operator guide** `docs/runner-guide.md` (D8).
- **Substrate guide close-out:** the 120 row describes the shipped Runner and links the operator guide and the write-up (D8).
- CHANGELOG entry.

**Excluded**

- **Follow-on slices the write-up proposes.** They are written as proposals, added to the slice plan's Future Work or to 130's and 131's entries, and built later.
- **Fixes to 120–128 code found during the proof.** These are handled by the Fixes rule (D9), not as part of this slice's code.
- **Auto merge policy.** 128 tests it. The proof uses the default policy, which is the one a PM meets first.
- **Batch dispatch, tier inference, multi-project scheduling.** These are 130, 131 and Future Work 1.
- **A proof harness or report generator.** The proof is read through existing `inspect` commands with `--json`. No new tooling is built for one run (D6).

## Dependencies

### Prerequisites

- **120–128 merged into the target** (Phase 7 done for each). 128 is a hard prerequisite: until it lands, dispatch has no clean-tree check (125, Risk Assessment), and an accept's gate disagreement is not recorded (issue #15).
- **Issue #14 closed.** Without it, `amoeba prune sq-runs` can delete a run paused under the Runner while its resolution is pending (127, Excluded). The proof checks that #14 is closed before it starts, and does not start otherwise.
- **106 (initiative 100, complete)** for `watch-reviews` and detections. It is outside this plan, so it is not in the frontmatter.
- **Squadron and CF installed with the shapes the startup probe checks.** The probe enforces these, so no version is pinned here. Versions are recorded in the write-up as observations.
- **A target project** meeting D1's criteria, registered with CF, with a slice plan whose initiative's `slice_plan` step the Runner reports `done`.

### Interfaces Required

- **122:** `amoeba start`/`stop`, settings and their flags, launch logs, recovery of in-flight runs across a crash.
- **123:** `amoeba submit create-project`, `link-cf-project`, plan reads, the node tree (`amoeba inspect nodes`).
- **124:** `amoeba submit intent` with `{"intent": "drive"}` on a slice node; `inspect desired-states`.
- **125:** dispatch, ingestion, `amoeba inspect journal`.
- **126:** `amoeba inspect routing-decisions` with its `recomputes` column; `--routing-table`; stored table versions.
- **127:** `amoeba submit resolution --decision … --instructions …`; `blocked_state(id)` with `runner_outcome`, `runner_code`, `runner_reason`; `inspect blocked`'s `blocked_state_id`.
- **128:** the clean-tree check, CF gate reads, the merge observation in git, and the gate-disagreement check record.
- **106:** `amoeba submit watch-reviews` and `amoeba inspect detections`. These provide the "nothing run by hand" evidence (D4).

## Architecture

### Component Structure

```
amoeba (resident process, from this repository's 129 branch)
  └─ Runner tenant ──drives──▶ target project checkout (PM-chosen, separate repo)
        │                         ├─ cf set / cf status   (journaled cf_write, reads)
        │                         └─ sq run P4/P5/P6      (journaled sq_run, detached)
        ▼
  per-project store (supervisor dir, kept until the write-up is done)
        │
        ▼ read-only
  amoeba inspect {nodes, journal, routing-decisions, blocked, resolutions*, detections, messages}
        │
        ▼
  user/analysis/120-analysis.first-proof-stops.md ──▶ default.yaml edits + regression tests
                                                  ──▶ Future Work / 130 / 131 entries

  * new in this slice
```

New and changed code is small:

```
src/amoeba/cli/inspect.py                 CHANGED  + resolutions subcommand
src/amoeba/store/…                        CHANGED  + resolved-blocks read (store contract)
src/amoeba/runner/routing/tables/default.yaml  CHANGED  per D7, after the proof
tests/runner/routing/test_first_proof_rules.py NEW      one test per D7 edit
tests/runner/routing/fixtures/first_proof/     NEW      exported decision inputs
docs/runner-guide.md                       NEW
docs/substrate-guide.md, docs/store-contract.md, README.md, CHANGELOG.md  CHANGED
```

### Data Flow

1. **Setup.** The PM starts `amoeba` with a dedicated supervisor directory. They create the project, link its CF project, watch its review directory, and wait for the first plan read.
2. **Drive.** The PM submits `{"intent": "drive"}` on the chosen slice's node, and nothing else. No other target is driven, so the Runner acts on this unit only.
3. **Loop.** For each step, the Runner writes the pointer, dispatches the pipeline, observes the run, ingests the review, and routes the outcome. A route to the PM is a stop: a block with an escalation message. The PM answers with `submit resolution`, and the Runner carries it out.
4. **Crash.** While P6 is in flight, the PM sends `kill -9` to the resident process and starts it again (D3).
5. **Merge.** P6 runs with `merge=false`. The merge step becomes a human step. The PM merges in git, and 128's observation advances the node to `done`.
6. **Read-out.** The PM exports `inspect … --json` for the project into the write-up's evidence appendix, then classifies each stop (D5).
7. **Feedback.** Wrong stops become table edits with regression tests (D7) or follow-on entries.

### State Management

This slice adds no persistent state. The proof's evidence is the project's store, which already holds every node, journal entry, decision, block, resolution and detection. The supervisor directory is kept until the write-up is committed, because the write-up's recompute check and exports read it. Fixture files under `tests/` are copies of recorded decision inputs, not live state.

## Technical Decisions

### D1 — Choosing the project and unit
Status: decided

- The slice plan makes the unit the PM's choice. The PM names it at the start of Phase 6, and the write-up's header records the project, CF project id, slice index and name. If no unit is named when the proof task starts, the task writes `BLOCKED:` and stops.
- **Criteria the unit must meet:**
  - **Separate repository.** It is not this repository, so the Runner never rewrites the checkout its own code runs from. A branch switch there would change the running Runner.
  - **Unstarted.** It has no slice design file yet, and its initiative's slice plan is done.
  - **A checkout the PM leaves alone during the proof.** 128's clean-tree check would escalate edits, but a stop caused by the PM's own editing is noise in the evidence.
  - **Small, but real code.** P6 should have something to implement and review. A docs-only slice would not exercise P6's code review.
- Rejected: an Amoeba slice such as 130. It depends on this proof's evidence, and it runs in the Runner's own checkout.
- Rejected: a purpose-built toy project. The point is real work, with a real plan and real reviewers.

### D2 — One table version for the whole run
Status: decided

- The routing table is not edited while the proof runs. Every decision in the proof is made under the shipped table's version, so each stop is evidence about one table.
- A wrong stop during the run is answered with a resolution, as any stop is. The PM may answer the same kind of stop more than once. That repetition is evidence too.
- Edits are applied after the unit merges (D7). No decision is made under the edited table, because nothing is driven after the merge, so no second version is stored. The proof's decisions must still recompute against the first version. The walkthrough checks this.
- Rejected: editing mid-run. Decisions would then be split across versions, and a rule edited to clear one stop could change the routes of later steps in ways the write-up cannot separate.

### D3 — The restart is a SIGKILL with P6 in flight
Status: decided

- The criterion is that a restart "leaves the run completable". The hardest case is a crash, not a clean stop, while the longest run is in flight. So the PM sends `kill -9` to the resident process during P6, after its launch is confirmed. Then they run `amoeba start` again.
- **Pass:**
  - The P6 run keeps running, because it is detached (122).
  - After restart, recovery leaves its entry unresolved, the Runner observes it, and ingests its outcome.
  - The step has exactly one `sq_run` entry for that attempt.
  - The unit still reaches `done`.
- If P6 finishes before the kill, the PM repeats the SIGKILL during the unit's next in-flight run, such as a P6 rerun. A miss is not a pass. If no run remains in flight, the crash criterion is unmet and the slice is not done: the PM drives a second unit chosen by D1 and lands the SIGKILL during its P6. The PM can make a miss unlikely by sending the kill soon after P6's launch is confirmed.
- A restart made to apply a fix (D9) also counts, and is recorded the same way. The SIGKILL is still required, because a clean stop does not test recovery.
- Rejected: restarting at a random point. A crash between launch and confirmation is 122's crash proof. Repeating it against a real run adds cost and no new coverage.

### D4 — What "nothing run by hand" is checked against
Status: decided

- The criterion's scope is commands that change state. Reads such as `cf status` or `sq runs list` are not driving anything.
- Some kinds of hand-run command leave evidence in the store. The write-up checks that evidence:
  - **A Squadron review the Runner did not issue** is ingested by detection as `ingested` rather than `runner_issued`. Check: `inspect detections --project P --json` has no `ingested` row after the drive intent, apart from runs the PM launched at a step the table sent them to. Each such exception is listed with its block id.
  - **A CF pointer moved by hand** while a run is in flight raises the moved-pointer escalation (125, D11). Any such escalation is a stop in the write-up.
  - **A resume by hand** is the `handled` resolution, which 127 records.
- The PM also writes a short log of every command they ran, with the block id that sent them there. The log is the primary record, and the evidence above is a partial check on it.
- The write-up states what the store cannot detect: a `cf set` while no run is in flight, a Squadron command that writes no review artifact, and git commands. For these, the log is the only record.
- Rejected: enumerating Squadron's runs. `sq runs list` shows only running and resumable runs, so completed runs started by hand would not appear.

### D5 — The stop write-up
Status: decided

- **Location:** `user/analysis/120-analysis.first-proof-stops.md` (`docType: analysis`, initiative base index).
- **A stop** is any block on the unit's nodes, plus any project-scoped escalation raised during the proof. Human steps (the merge) are stops too. They are expected, and are classified as right unless the table should have handled them.
- **One row per stop:**
  - block id, node and step;
  - the decision's rule id, inputs and `judge_eligible`, or the fault kind for a block with no decision;
  - what the PM did: the resolution and its decision, or a by-hand action, from the D4 log;
  - classification: `right`, `wrong: routable` (an escalation the table could have routed), or `wrong: misrouted` (a route the PM disagreed with);
  - for a wrong stop, one proposal: a table edit (the rule as YAML), a follow-on slice (130, 131, or a new Future Work entry), or a code issue. A stop with no decision record (a fault) cannot be fixed by a table edit, because faults escalate before the table is consulted and there are no recorded inputs to fixture. Its proposal is a follow-on slice (a retry class is Future Work 2) or a code issue.
- **Further sections:**
  - **Answers to deferred questions:** issues #12 and #13, Future Work 2, and whether 126's time bounds (P4/P5 240 min, P6 720) fit the observed run lengths.
  - **Evidence appendix:** the `--json` exports the rows were built from, the Squadron, CF and Amoeba versions observed, and every Amoeba commit the process ran on.
- The classification is the PM's judgment. The Architect drafts each row from the evidence, and the PM confirms or changes the classification. This is the slice plan's definition of a wrong stop ("a human found routable", "a human disagreed with"), not an added approval step.
- Rejected: storing classifications in the store. They are one-off analysis with no consumer. The routing table and the slice plan are where they take effect.

### D6 — `amoeba inspect resolutions` (issue #16), and no other tooling
Status: decided

- The write-up needs every resolved block on the unit, with what was decided and what the Runner did with it. `inspect blocked` lists open blocks only. Reading `blocked_state(id)` one id at a time means already knowing every id. Issue #16 was deferred for exactly this use.
- `amoeba inspect resolutions --project P [--node-id N] [--json]` lists resolved blocks oldest first. Columns:
  - `blocked_state_id`, node, step, reason, `opened_at`, `resolved_at`;
  - the resolution's decision and instructions;
  - `runner_outcome`, `runner_code`, `runner_reason`;
  - for an accept, the accepted verdict ids (127, D7).
- It opens the store read-only, as every `inspect` command does. A new store read backs it, documented in `docs/store-contract.md`. Adding it to 100's contract this late is deliberate. The arch's contract-first rule covers what the Runner needs, and this read is additive and serves operators, not the Runner.
- Nothing else is built. Recompute is `inspect routing-decisions`' `recomputes` column (126). Journal, detections and messages already have `--json`. A dedicated proof report would be code written for one run.

### D7 — Wrong stops that become table edits
Status: decided

- After the unit merges, each `wrong` row whose proposal is a table edit is applied to `default.yaml`.
- **Fixtures are every proof decision, not only the wrong ones.** Rules are first match wins, so an edit that fixes one stop can reroute a decision the PM accepted. Each decision's recorded `inputs`, rule id and route are exported from the proof's store into `tests/runner/routing/fixtures/first_proof/<decision-id>.json`. A decision behind a `wrong` row also carries its proposed rule id and route. Production-shaped input is the point. These are the inputs the table will actually see.
- **One test in `test_first_proof_rules.py`** runs every fixture through the edited table and asserts two things:
  - every decision not behind a `wrong` row keeps its recorded route;
  - each wrong decision reaches its proposed rule and route, and nothing else changes.
- After a restart on the edited table, every proof decision still recomputes `yes`. Recompute reads the stored first version (D2), so this checks that the stored versions are intact. It says nothing about the edit, which the test above covers.
- An edit is a table change only. A proposal that needs a new routing input, such as a tier, is a follow-on slice (131), not an edit. The arch forbids routing in code outside the table.
- If the proof finds no wrong stop that a table edit fixes, nothing is edited. The write-up says so.

### D8 — Operator guide and substrate guide close-out
Status: decided

- **`docs/runner-guide.md`** is task-ordered:
  - setup: supervisor directory, `start`, `create-project`, `link-cf-project`, `watch-reviews`;
  - settings, with each flag and its default as defined in `settings.py`;
  - driving with intents;
  - reading stops: `inspect blocked`, `messages`, `routing-decisions`;
  - answering with resolutions: which decisions apply in which situation;
  - the routing table: where it is, how a version is formed, editing and restarting, `--routing-table`;
  - merge policy;
  - crashes and restarts;
  - pruning.
- It states each rule once, in the guide or by a link to the contract section that owns it. Body formats, decision rules and the table grammar stay in their contracts and are linked, not copied.
- Settings and defaults are listed from `settings.py` and the CLI's `--help`, not from the designs, because the designs may have drifted.
- **Substrate guide:**
  - The opening sentence drops 120 from the initiatives being designed.
  - The 120 row says the Runner ships as `amoeba.runner`, keeps its contract links, and adds the operator guide and the write-up.
  - The stand-in proof remains the contract evidence, and the row says so.
  - README links the operator guide.

### D9 — Defects found during the proof
Status: decided

- A defect in 120–128 code is not this slice's code. It follows the project's Fixes rule. A small fix is committed to the target as `fix:` with a failing test first, and `Fixes #n`. The target is then merged into the 129 branch, which is a clean sync from the target, and the resident process is restarted on the fixed code. The write-up lists the fix, its issue, and the restart.
- A defect that does not stop the proof is filed as an issue and noted in the write-up. The proof continues.
- A defect that leaves the unit unrecoverable, such as a corrupted step state with no resolution available, ends the attempt. It is written up, fixed, and the proof restarts on a fresh unit chosen by D1. Both attempts stay in the write-up.

### Technology Choices

No new libraries. The proof uses `amoeba`, `cf`, `sq`, `git` and `jq` for reading exports in the walkthrough.

### Patterns and Conventions

- `inspect resolutions` follows the existing `inspect` pattern: read-only open, `--json`, oldest first, and the `StoreSchemaError` exit for a store at another schema version.
- Rule tests are named for the stop they fix, for example `test_p4_concerns_on_first_round_reruns`.

## Implementation Details

### API Contracts

```bash
amoeba inspect resolutions --project P [--node-id N] [--json]
```

| Column | Source |
| --- | --- |
| `blocked_state_id`, `node_id`, `step`, `reason`, `opened_at`, `resolved_at` | the blocked state |
| `decision`, `instructions` | the resolution (127) |
| `runner_outcome`, `runner_code`, `runner_reason` | the Runner's acknowledgment (127) |
| `accepted_verdict_ids` | for an applied `accept` only, else null (127, D7) |

A block that has been resolved but not yet acknowledged by the Runner shows null `runner_*` fields. It is listed, not hidden.

## Integration Points

### Provides to Other Slices

- **130, 131:** the write-up's wrong stops, as their scope input. Proposals land in their slice plan entries.
- **140:** the list of judge-eligible escalations and how the PM resolved each one.
- **Future Work:** answers for entries 2 and 10, and for issues #12 and #13.
- **Operators, 160 and the notification bridge:** `docs/runner-guide.md`, and `inspect resolutions` as a read of resolved blocks.

### Consumes from Other Slices

- Every Runner surface listed under Interfaces Required. A surface that fails in the proof is a defect handled by D9, not something worked around here.

## Success Criteria

### Functional Requirements

- The chosen unit's `slice_design`, `tasks`, `implementation` and `merge` steps all reach `done`, and the slice branch is merged into the target project's target by the PM.
- No state-changing Squadron or CF command was run by hand, except at a step the routing table sent to the PM. Each exception in the D4 log names its block id. The store evidence D4 lists agrees with the log, within the limits the write-up states.
- Every row of `amoeba inspect routing-decisions --project P --json` for the unit shows `recomputes: yes`.
- After the D7 edits and restart, the same rows still show `yes`.
- One SIGKILL with P6 in flight: the run survived, its entry was observed and ingested after restart, its step has one `sq_run` entry for that attempt, and the unit completed (D3).
- The write-up lists every stop with a classification. Each wrong stop has exactly one proposal.
- `amoeba inspect resolutions` lists every resolved block on the unit, with the columns in API Contracts.

### Technical Requirements

- `inspect resolutions` has tests for each column, the unacknowledged case, `--node-id` filtering, and the schema-mismatch exit.
- D7's test passes on the edited table: decisions the PM accepted keep their routes, and each wrong decision reaches only its proposed rule.
- `uv run pytest -q`, `ruff check`, `ruff format --check`, `pyright` and `tests/contract` pass.
- `docs/runner-guide.md`, `docs/store-contract.md` (the new read), `docs/substrate-guide.md`, README and CHANGELOG are updated.

### Integration Requirements

- 130's and 131's plan entries, and the slice plan's Future Work, reflect the write-up's proposals.
- Issues #12, #13 and #16 are closed, or updated with the proof's evidence. #16 closes with this slice. #12 and #13 are either closed as not needed or re-scoped, citing the write-up.

### Verification Walkthrough

Draft. Commands for 120–128 are as their designs specify. The exact project and slice come from D1. Replace `<P>`, `<cf-id>`, `<slice-node>` and `<target-checkout>`.

1. **Preconditions.**
   ```bash
   gh issue view 14 --json state -q .state
   cf config get git.integration_branch          # the Value: line; empty means main
   git branch --merged <target> | grep -E '^\*? *12[0-8]-slice\.'
   ```
   Expected: the first command prints `CLOSED`. The third lists nine slice branches, 120 through 128. If either check fails, stop.

2. **Start and link.** Use a dedicated supervisor directory, kept until the write-up is committed:
   ```bash
   export AMOEBA_STORE_DIR=<proof-supervisor-dir>
   uv run amoeba start &
   uv run amoeba submit create-project --project <P> --by operator
   uv run amoeba submit link-cf-project --project <P> --by operator --cf-project-id <cf-id>
   uv run amoeba submit watch-reviews --project <P> --by operator \
       --reviews-dir <absolute-reviews-dir-of-target-checkout> --active true
   sleep 5; uv run amoeba inspect nodes --project <P>
   ```
   Expected: the chosen slice's node, with four step rows, and `slice_design` runnable. No escalations, because nothing is driven yet.

3. **Drive.**
   ```bash
   uv run amoeba submit intent --project <P> --by operator --node-id <slice-node> \
       --body '{"intent": "drive"}'
   ```
   Expected: the intent is acknowledged `applied`. Within a tick or two, `inspect journal` shows a `cf_write` and then an `sq_run` for P4.

4. **Answer stops as they come.** Poll `inspect blocked --project <P>`. For each block, read its escalation in `inspect messages` and its decision in `inspect routing-decisions`, then answer:
   ```bash
   uv run amoeba submit resolution --project <P> --by operator \
       --blocked-state-id <id> --detail "…" --decision <retry|accept|handled|rerun|stop>
   ```
   Record each command run by hand in the D4 log, with the block id.

5. **Crash during P6.** Once `inspect journal` shows P6's `sq_run` confirmed:
   ```bash
   kill -9 <resident-pid>; uv run amoeba start &
   ```
   Expected: the run continues (`sq runs list` still shows it running). After it finishes, its entry resolves `completed`, and the step has no second `sq_run` entry for the attempt.

6. **Merge.** P6 ends with the slice branch unmerged, and the merge step is blocked as a human step. In `<target-checkout>`, merge the slice branch into its target. Expected: the merge step goes `done`, and so does the slice node.

7. **Audit.**
   ```bash
   uv run amoeba inspect routing-decisions --project <P> --json | jq '[.[] | .recomputes] | unique'   # ["yes"]
   uv run amoeba inspect detections --project <P> --json | jq '[.[] | select(.outcome=="ingested")]'
   uv run amoeba inspect resolutions --project <P> --json
   ```
   Expected: recompute is all `yes`. Any `ingested` row matches a D4 log entry. Resolutions cover every stop.

8. **Write-up and edits.** Draft the write-up from step 7's exports. The PM classifies each stop. Export every decision's inputs to fixtures, edit `default.yaml`, and run:
   ```bash
   uv run pytest tests/runner/routing/test_first_proof_rules.py -v
   uv run amoeba stop; uv run amoeba start &
   uv run amoeba inspect routing-decisions --project <P> --json | jq '[.[] | .recomputes] | unique'
   ```
   Expected: the test passes. The proof's decisions still recompute `yes`, which shows the stored first version is intact.

9. **Docs.** In a fresh supervisor directory, run the guide's setup commands as written: `start`, `create-project`, `link-cf-project`, `watch-reviews`, then `inspect nodes`. Expected: each command succeeds, the unit's slice node and its four step rows exist, and the journal is empty, because nothing is driven. Check each flag and default in the guide against `--help` and `settings.py`. Check the sections on intents and on answering stops against the D4 log from the real run. Every command in the log is described in the guide.

## Risk Assessment

### Technical Risks

- **A defect in 120–128 stalls the proof.** This is the first end-to-end run against real work, so some defect is likely.
- **Squadron spend and wall-clock.** P6 can run for hours, and reruns multiply that.

### Mitigation Strategies

- D9 gives a defect one path: fix on the target, sync, restart, and keep going. Recovery across restarts is part of what is being proven, so a restart to apply a fix does not invalidate the run.
- Squadron's `max_cost_usd` bounds each run, and a `cost_cap` failure escalates and is never retried automatically (arch). 126's attempt limits bound reruns. LLM spend for the proof is pre-authorized.

## Implementation Notes

### Development Approach

1. Check the preconditions (walkthrough step 1). Record the D1 choice in the write-up's header.
2. Build `inspect resolutions` (D6), with its store read, tests and contract text. It is needed for the read-out, so it comes before the proof.
3. Run the proof (walkthrough steps 2–7), keeping the D4 log as it goes.
4. Write up the stops (D5).
5. Apply the table edits with their fixtures and tests (D7). Restart and check that recompute still holds.
6. Write the operator guide (D8), and verify it by following it (walkthrough step 9). Then the substrate guide, README, slice plan entries, issues and CHANGELOG.

Relative effort: 3/5. Most of the effort is the proof run and the write-up, not code.

### Special Considerations

- **No secrets** in the D4 log, in resolution instructions, or in exported fixtures. Fixtures are decision inputs (enums, counts, ids), which carry none, but check before committing.
- The proof's supervisor directory is evidence until the write-up is committed. It is not pruned or deleted before then.
- The target project's own branches and merges follow that project's rules. The Runner never merges, deletes branches or pushes (arch), and the PM's merge at the human step is theirs.
