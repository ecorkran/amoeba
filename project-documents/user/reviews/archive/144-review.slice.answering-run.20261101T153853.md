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
reviewedSha: 0b0053215bf14689b7b19b8332e9568c73ffdb37
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 109174
cachedTokens: 11162
cacheWriteTokens: 98008
completionTokens: 5774
durationSeconds: 46.9
costUsd: 0.451735
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Stage placement, tick order and answering-entry isolation match the architecture"
    location: "project-documents/user/slices/144-slice.answering-run.md#Data Flow"
  - id: F002
    severity: concern
    category: scope-alignment
    summary: "D1 drops the answering pipeline from per-project configuration, which the architecture still lists"
    location: "project-documents/user/slices/144-slice.answering-run.md:164-169"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "144 retroactively rewrites the contracts of 141, 142 and 143"
    location: "project-documents/user/slices/144-slice.answering-run.md:76,98,281"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Launch-path failures other than `spawn` are not enumerated"
    location: "project-documents/user/slices/144-slice.answering-run.md:210-218"
  - id: F005
    severity: note
    category: scope-alignment
    summary: "The done-guard change (D4) and the `begin_answering` store operation extend the architecture's list of changes to code 120 and 100 own"
    location: "project-documents/user/slices/144-slice.answering-run.md:193-199"
  - id: F006
    severity: note
    category: integration
    summary: "Four newly required `AnswererSettings` keys break existing answerer sections"
    location: "project-documents/user/slices/144-slice.answering-run.md:318-338"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable, with some repetition"
    location: "project-documents/user/slices/144-slice.answering-run.md:191,418,453-459"
---

# Review: slice — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Stage placement, tick order and answering-entry isolation match the architecture

- The stage runs after ingest and before act, under the tick budget and fault isolation.
- `sq_answer` entries never reach `record_finished`.
- The shared `supervision_entries` reader covers every reader the architecture names: `classify`, `run_to_resume`, the checkout hold, dispatch state and the resume counter (D3).
- The PM-wins race, the discard of a late answer, and adoption by run id after a restart all match the architecture's steps 7 and "A restart…".
- `decide_answer` reads only recorded inputs, with the passage ids stored on the record (D7, D11). This matches "decides from recorded inputs alone".
- Every uncertain path declines, and nothing retries.

### [CONCERN] D1 drops the answering pipeline from per-project configuration, which the architecture still lists

The architecture's "Cost and configuration" section says the answering pipeline belongs in per-project configuration. The slice plan reportedly lists it too (D1 says so). D1 removes the key, citing 140 D1 and the 142 start-up probe. The reasoning is sound: a per-project key would bypass the probe, and a key with one valid value has no use. But the architecture text is unchanged, so the parent document and this slice now disagree. Either amend the architecture's configuration sentence to say the pipeline is the shipped file and not configurable, or record D1 as an explicit architecture deviation. The same applies to the slice plan entry.

### [CONCERN] 144 retroactively rewrites the contracts of 141, 142 and 143

This slice changes upstream slices' public surfaces:
- `check_citations` changes from taking the set to taking the set's ids, and "143's design is updated with it".
- `submit_answer` and `decline_question` gain `evidence` and `detail` keywords.
- `settle.py`'s final branch changes from `Decline(no_answer_on_file)` to `Launch`.

The Development Approach hedges with "if 143 has shipped" and "re-check names against its code before task breakdown". It does not say what happens in each case:
- If 142 or 143 are already implemented, 144 edits shipped code and their suites.
- If they are not, the upstream designs should absorb the changes now, so the dependency points one way.

Pick one for each of the four changes and state which slice owns it. As written, the dependency direction is ambiguous, and a hidden coupling could break 141–143's suites. The Technical Requirements already require those suites to pass.

### [CONCERN] Launch-path failures other than `spawn` are not enumerated

D6 handles `LaunchError` from `spawn`, a budget refusal, and a `SourcesProblem`. The launch also does I/O that D6 does not cover:
- `mkdir` of the scratch directory.
- `prepare_scratch`, which writes the inputs and `.squadron.toml`.
- Writing the launch log.

An `OSError` (permissions, disk full) from any of these falls under "only programming errors raise". That would escalate every tick for a record that stays `pending`, and each retry would mint a new run id and a new orphaned directory. Say explicitly what happens:
- Decline with an `answering_launch_failed`-style reason, or
- Escalate once and stop launching.

D6 should also say how many orphan directories this can leave behind.

### [NOTE] The done-guard change (D4) and the `begin_answering` store operation extend the architecture's list of changes to code 120 and 100 own

The architecture says the changes to code 120 owns are limited to the named set, and "nothing else in the supervisor changes shape". D4 changes `SELECT_UNRESOLVED_ENTRY_FOR_NODE` in the store, and D5 extracts `_insert_entry_within` from `journal_issue`. Both are justified: D4 prevents a fault on a slice that finished, and D5 gives crash-atomic launch. The architecture's Store changes section names only the resolve-and-record operation and the record-only decline. Add D4 and D5 there so the parent stays the complete list of changes to code others own.

### [NOTE] Four newly required `AnswererSettings` keys break existing answerer sections

All four keys are required with no defaults, which the architecture and project rules prefer. Any project that already carries a 142/143 answerer section (`answer_limit`, `reserved_terms`, `rules_paths`, `passages_max_chars`) will fail to load until it adds the keys. The Integration Requirements cover only "no answerer section". The load error naming the key path is enough, but the process contract's migration note should say this is a breaking config change for those projects.

### [NOTE] Proportionality is acceptable, with some repetition

Relative effort is 4. Most of the mechanisms trace to an architecture requirement:
- Atomic launch.
- The traceability columns.
- The distinct decline reasons.
- The concurrency cap.

D3's acceptance test is stated three times: in D3, in Success Criteria and in Walkthrough step 2. Keep it in D3 and have the other two sections reference it. The three live-tier cases overlap with 145's four walkthrough cases, so the second same-meaning-other-slice case could be left to 145.

### Run Digest

- Response length: 6054 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 109174 / 11162 / 98008 / 5774 / not computed
- Duration: 46.9 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
