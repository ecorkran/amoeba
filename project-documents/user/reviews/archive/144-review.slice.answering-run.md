---
docType: review
layer: project
reviewType: slice
slice: answering-run
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/144-slice.answering-run.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: a1299c968119416729057ffbc1ca8191da31d022
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 217726
cachedTokens: 108158
cacheWriteTokens: 109562
completionTokens: 5189
durationSeconds: 45.3
costUsd: 0.501804
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Answering stage, entry handling and PM-wins race match the architecture"
    location: "project-documents/user/slices/144-slice.answering-run.md#Architecture"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "The slice's changes to 132, 141, 142 and 143 code have owners and stay within the architecture"
    location: "project-documents/user/slices/144-slice.answering-run.md#D14"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Persisted columns beyond what traceability needs"
    location: "project-documents/user/slices/144-slice.answering-run.md#D11"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Decline vocabulary larger than the requirements name; several members could share a reason"
    location: "project-documents/user/slices/144-slice.answering-run.md#D8"
  - id: F005
    severity: note
    category: error-handling
    summary: "No Amoeba-side bound on how long an answering run can stay in flight"
    location: "project-documents/user/slices/144-slice.answering-run.md#D10"
  - id: F006
    severity: note
    category: scope
    summary: "Heavy but justified blocked-state handling"
    location: "project-documents/user/slices/144-slice.answering-run.md#D9"
---

# Review: slice — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Answering stage, entry handling and PM-wins race match the architecture

The slice follows the architecture's seven-step flow:
- The stage runs after ingest and before act, under the tick budget.
- `sq_answer` entries never reach `record_finished`.
- The record moves to `answering` in the same transaction as the journal entry (D5).
- The PM wins every race (D9).
- Restart adopts by run id through the recovery observer (D2).
- Every uncertain path declines, and nothing retries.

The shared `supervision_entries` reader (D3) covers every reader the architecture names: `classify`, `run_to_resume`, the checkout hold, dispatch state and the resume counter. Its acceptance test matches the one the plan and the architecture require.

### [PASS] The slice's changes to 132, 141, 142 and 143 code have owners and stay within the architecture

The 132-owned changes (readers, done-guard, `sq_answer` kind) are the ones the architecture lists in "Store changes" and "The answering entry and the slice's journal". D14 gives every change to 141–143 surfaces one owner. The `check_citations(cited, passage_ids)` claim holds: 143's design already has that signature (143 D8, line 215, and API Contracts, line 312). The `evidence` and `detail` keywords are optional, so 141's and 142's existing suites run unchanged. Store types flow from the store to the runner, not the reverse.

### [CONCERN] Persisted columns beyond what traceability needs

The architecture's traceability goal needs the record to show the question, the answer, the cited passages, the verdict and the answering run. D11 adds ten columns. Two of them can be cut without losing a stated requirement:
- `answering_run_id` copies the `run_id` parameter of the `sq_answer` entry that `answering_entry_id` already points to. The listing can join through the entry, so the column and its write in `begin_answering` can go. If the PM wants it inline, the listing can expose the joined value.
- `dropped_pm_answers` serves no consumer in this slice. Neither the decision (D7), the listing, nor any success criterion reads it. 143 produces the dropped ids, and the architecture only asks that trimming be part of the risk model. Defer the column until something reads it.

`passage_index` is needed, because `decide_answer` reads its ids and the PM needs it to trace citations.

### [CONCERN] Decline vocabulary larger than the requirements name; several members could share a reason

The plan requires distinct reasons for a check `no`, an uncited answer, malformed or missing artifacts, and failed, orphaned, stalled or cost-capped runs. D8 adds about nine more members, each with its own mapping, decide row and test case. They are `answering_run_vanished`, `answering_run_paused`, `answering_run_not_started`, `answering_run_unknown`, `answering_launch_failed`, `answer_discarded` and the three `sources_*` members.

The three `sources_*` members are 143's vocabulary and are justified. The run-lifecycle ones carry no different handling: every one is "decline, show the PM". Nothing, including 160, branches on them. `detail` already carries the specifics. Fold `vanished`, `paused`, `not_started` and `unknown` into `answering_run_failed` (or one `answering_run_lost`), with the lifecycle kind in `decline_detail`. That shrinks the table, the maps and the D7/D8 table test. Keep the split only if the PM wants to filter on those reasons.

### [NOTE] No Amoeba-side bound on how long an answering run can stay in flight

Failure handling for the new I/O paths is otherwise enumerated well:
- mkdir or `prepare_scratch` `OSError`
- `spawn` `LaunchError`
- poll fault
- crash between the journal write and spawn, and between settle and resolve
- vanished runs and `not_found` after the launch grace

The one path left implicit is a run that stays alive and reports no failure. It would hold a concurrency slot indefinitely. The slice relies on Squadron's `stall` and `cost_cap` kinds (D8) and says so only by implication. One sentence in D10 saying this is the intended bound would close it. No architecture NFR is touched, so no restatement is required.

### [NOTE] Heavy but justified blocked-state handling

The stranded pass and the `block_resolved` and `settled` outcome handling add mechanism. Each one closes a race the architecture states (PM answered first, a re-pointed block, crash recovery), so it is in scope. No cut is recommended.

### Run Digest

- Response length: 5032 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 217726 / 108158 / 109562 / 5189 / not computed
- Duration: 45.3 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
