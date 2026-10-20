---
docType: review
layer: project
reviewType: slice
slice: run-dispatch-and-outcome-ingestion
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 8ce730ec62b24ddc33fbd9e3386970cab19acea4
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 116349
cachedTokens: 11266
cacheWriteTokens: 105079
completionTokens: 6691
durationSeconds: 56.2
costUsd: 0.489167
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Absent read-back field is both \"unresolved forever\" and \"Unknown → escalate\""
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D2 — The pointer write sets the slice only, in the checkout, and is checked by index"
  - id: F002
    severity: concern
    category: integration
    summary: "POINTED depends on a post-write snapshot that may never be recorded"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D3 — A step's dispatch state is derived from its own journal entries"
  - id: F003
    severity: concern
    category: scope
    summary: "Per-pipeline time bound dropped from this slice"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D12 — The per-pipeline time bound moves to 126"
  - id: F004
    severity: concern
    category: architecture
    summary: "Detection's ledger-key computation is reimplemented in ingest"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D7 — Which review files are recorded, and how they are attributed"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Slice is heavy; name what to defer or fold"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Technical Scope"
  - id: F006
    severity: note
    category: risk
    summary: "Dispatch precedes the clean-tree check"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Risk Assessment"
  - id: F007
    severity: note
    category: contracts
    summary: "Verdict linkage departs from the architecture's wording on verdict ids"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D7 — Which review files are recorded, and how they are attributed"
  - id: F008
    severity: pass
    category: architecture
    summary: "Boundaries, dependency direction and failure handling"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Architecture"
---

# Review: slice — slice 125

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Absent read-back field is both "unresolved forever" and "Unknown → escalate"

D2 says that on "an absent field, or a read that fails" the entry "stays unresolved" and Observe reads back again on the next tick. D10 says that for the same observer "a field that is absent or does not parse is `Unknown`", and D2 itself routes `Unknown` through `journal_escalate`. The two statements contradict each other.

The architecture's "Unknown escalates" principle says a missing field becomes an explicit unknown routed to a human. The persistent-failure path has no bound. A `cf get` that times out or returns non-JSON on every tick keeps the `cf_write` entry in flight.

An unresolved `cf_write` also holds the checkout (D4, in-flight). The affected checkout therefore stalls with no node-level block. Only a per-tick project fault would surface it, and the design does not say that fault is raised or that it closes.

Split the two cases:
- Transient read failure (timeout, non-JSON): retry, with a stated bound after which the entry escalates.
- Absent field: `Unknown`, escalate immediately.

### [CONCERN] POINTED depends on a post-write snapshot that may never be recorded

D3 and D11 gate `POINTED` on "a snapshot recorded after the pointer write resolved". The state is no action until one exists. The design assumes "the CF watch records one within a scan interval".

Interfaces Required says `cf set` on an already-set value "writes nothing". In that case CF's `updatedAt` does not move. The architecture describes snapshot entries where nothing changed (`changed: []`), but this design never confirms that 108 records a snapshot row on every scan. If it records only on change, a step whose pointer was already correct never leaves the no-action branch. Nothing escalates, because the entry is resolved and the step is simply not acted on.

Even when snapshots are recorded, every dispatch pays up to one scan interval of latency between the pointer write and the launch.

State the 108 guarantee, cite its source, and add a test for the already-pointed case. Otherwise bound the wait and escalate when it expires.

### [CONCERN] Per-pipeline time bound dropped from this slice

The slice plan entry assigns the per-pipeline time bound to 125. D12 moves it to 126 and edits plan entries 6 and 7. The reasoning is sound: the table is 126's, and a mid-run block would defeat the outcome block (D11). It is still deferral of assigned scope.

The architecture already says the bound is enforced by the routing engine and cites D12. So there is no architectural conflict, only a plan change. Until 126 lands, a hung run holds its checkout indefinitely.

The design should say that explicitly. It should list the plan edits as a prerequisite to merging, not as an item in step 7.

### [CONCERN] Detection's ledger-key computation is reimplemented in ingest

The last bullet of D7 describes how `ingest/reviews.py` computes the `path` key: a watch directory joined with the file name, or else the resolved absolute path. It says this is "the key detection computes (evidence contract D5, point 3)". That is a second implementation of 106's rule inside the Runner.

If detection's rule changes, the `runner_issued` marker silently stops matching and detection records the review again. That is exactly the failure this slice exists to prevent. The architecture says the Runner follows D5 to the letter, and the project rules say not to duplicate logic.

Consume a single function exported by the detection or evidence layer. If none exists, add one as a contract change in D10, with a test that detection and ingest agree on the key.

### [CONCERN] Slice is heavy; name what to defer or fold

This slice carries effort 4/5 and bundles:
- two new subpackages;
- a store migration and a changed `record_runner_report` signature;
- a changed `cf_write` contract;
- a pointer-move monitor with its own pure module and fault kind;
- the issue #9 reissue path;
- five contract-document updates.

Candidates to cut or fold:
- **Interfaces Required.** It restates Squadron and CF source observations that belong in the contract documents. Keep one reference to those documents instead of copying their shapes, which have to be maintained twice.
- **Provides to Other Slices.** It repeats the Special Considerations list and D8/D6. Collapse it to the interface names.
- **D11 deduplication limit.** The accepted limit (a second run's move is not listed while an escalation is open) leaves the named-node requirement only partly met. Either let the payload be refreshed, or move the monitor into a follow-on slice. The architecture and plan do assign the monitor to 125, so moving it is a plan change like D12's.
- **Real-tool walkthrough.** Step 3 duplicates what the stub-based tests prove. Keep it as a short smoke check.

The size is justified for the contract-first work, but the doc should say which parts can ship separately if the slice overruns.

### [NOTE] Dispatch precedes the clean-tree check

The architecture says the Runner dispatches only after observing a clean tree on the target or the slice's branch. That check is 128's, so this slice launches into a real working tree without it. The mitigation is that a PM drive is required and the walkthrough uses a scratch copy. This is acceptable given the plan's ordering. Say so in Excluded and in the risks, because "touch a real working tree" is listed as a risk with no matching mitigation.

### [NOTE] Verdict linkage departs from the architecture's wording on verdict ids

The architecture describes the run id as letting the Runner mint the verdict id at journal time. D6 and D7 instead use content-digest ids with `journal_entry_id=None`, linked through `sq_run_id` and `verdict_ids`. The justification (the entry is on the step node, the verdict on the slice node) is sound, and the evidence contract edit is listed. Confirm that 100's retry rule is digest-based, so the architecture sentence is not left stale.

### [PASS] Boundaries, dependency direction and failure handling

- **Observe/decide/act and purity.** I/O stays in Observe and Act. The planner, `dispatch_state`, `resolve_checkout` and `pointer_moved` are pure and table-tested.
- **Journaling.** Every command with a side effect (`cf_write`, `sq_run`) is journaled first, with an observer and a re-issue rule. This matches the architecture.
- **Contract changes first.** The contract changes to 100 (D10) land before Runner code, as the architecture requires.
- **Dependency direction.** Runner → process/store only.
- **Failure modes.** They are enumerated for the new paths: `cf set` non-zero, read-back mismatch, cut-off between write and read-back, missing or unparseable review files, crash between block and report, an unreadable launch log, and a launch that appears late. Each has an explicit handling strategy.
- **Timing NFR.** The "tick never waits" NFR is restated: every `cf` and `sq` call goes through `TickBudget` under the per-call timeout, and a test asserts it.
- **Documented departures.** The checkout hold starting at the pointer write, the project-scoped pointer-moved escalation, and the verdict sitting on the slice node are each argued, with the matching architecture edits listed.

### Run Digest

- Response length: 8899 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 116349 / 11266 / 105079 / 6691 / not computed
- Duration: 56.2 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
