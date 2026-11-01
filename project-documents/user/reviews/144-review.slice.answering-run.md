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
reviewedSha: 3f3fae75cfcc7a85faa1f9eae55a19354d42a02d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 406733
cachedTokens: 295325
cacheWriteTokens: 111396
completionTokens: 6943
durationSeconds: 58.4
costUsd: 0.545409
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, ownership and the changes to 132-owned code match the architecture"
    location: "project-documents/user/slices/144-slice.answering-run.md#Technical Scope"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Race handling and crash safety are explicit"
    location: "project-documents/user/slices/144-slice.answering-run.md#D5, D6, D9"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design carries restated material and fields nothing reads"
    location: "project-documents/user/slices/144-slice.answering-run.md#D14, #Dependencies, #Verification Walkthrough, #D11"
  - id: F004
    severity: note
    category: failure-modes
    summary: "No Amoeba-side wall-clock bound on an answering run"
    location: "project-documents/user/slices/144-slice.answering-run.md#D10"
  - id: F005
    severity: note
    category: cost
    summary: "A question the gate will decline still costs one run"
    location: "project-documents/user/slices/144-slice.answering-run.md#D10"
---

# Review: slice — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Boundaries, ownership and the changes to 132-owned code match the architecture

- The answerer stays a stage of the Runner's tick, with no second tenant. The answer returns through `submit_answer` and the inbox, and the launch has no checkout.
- The `sq_answer` kind, its recovery observer and the shared reader (D2, D3) match the architecture's three-part change. The reader is applied to `classify`, `run_to_resume`, the checkout hold, dispatch state and the resume counter, which are the readers the architecture and slice plan name.
- D4's done-guard change matches the architecture's "Store changes". I checked the code: `SELECT_UNRESOLVED_ENTRY_FOR_NODE` is read only by `_write_status` for `done`, and the journal has no unique-unresolved-per-node constraint. So the guard is the only store-level obstacle to a resumed run finishing while an answering run is in flight.
- D1 drops the per-project `pipeline` key. The slice plan's 144 entry already says the pipeline is the shipped file, and 140 D1 and 142 D8 justify it, so this is not dropped scope.

### [PASS] Race handling and crash safety are explicit

- D5 journals the entry and moves the record in one transaction. A crash between the commit and the spawn ends in a recovery `not_applied` resolution and a stranded-pass decline.
- Every launch-path failure has a named reason (D6). D9 orders "settle the record, then resolve the entry" so a retry is safe. The PM-first, `block_resolved` and `settled` outcomes are each handled and tested.
- Together these cover the architecture's "PM wins" and "adopt by run id, never duplicate" requirements.

### [CONCERN] Design carries restated material and fields nothing reads

The slice plan scopes this slice at effort 4. The design is long because parts of it repeat other documents or add detail no consumer needs. Cut or shrink:
- **D14's ownership table.** Its first row says 143 already ships `check_citations(cited, passage_ids)`, which 143's own design and D7 here already state. Keep only the two rows where 144 edits 141's and 142's code, and fold them into D9's last bullet and D14's `settle_pending` note.
- **"Interfaces Required", "Consumes from Other Slices" and the "Prerequisites" list.** They overlap one another and the Technical Scope bullets. Merge them into one short list of what is consumed.
- **Walkthrough steps 1–3.** Each is a bare `pytest` command that repeats the D3, D5 and D7 test descriptions. Keep steps 4–7, which exercise behavior an operator can see.
- **`question_id` as a required `sq_answer` parameter (D2).** The record already links to the entry through `answering_entry_id`, and the listing joins through it. This is a second copy of the link. If `amoeba inspect journal` needs it, state that need, otherwise drop it.
- **`passage_index` entries (D11).** Each entry carries `kind` and `date`, but D11 and the success criteria require only the id, the source and the PM `question_id`. Store the fields something reads. Add `kind` and `date` when a consumer needs them, since the text can be re-read from git at `source_commit`.

Everything else stays: the distinct decline reasons, the cap, the live tier and `dropped_pm_answers` are plan-assigned, and the D3 test and the evidence columns serve stated success criteria.

### [NOTE] No Amoeba-side wall-clock bound on an answering run

D10 states this choice. A run that stays alive without reporting a failure holds a concurrency slot until Squadron's stall detection or `max_cost_usd` ends it. If Squadron never reports a stall, `max_concurrent_runs` hung runs stop all answering for the project. The result is safe, because questions go to the PM as they do today. It does rely on Squadron's behavior, so 145 should watch for it.

### [NOTE] A question the gate will decline still costs one run

The "No pre-gate" decision is consistent with the architecture. Its queue step lists only three pre-checks, and a second copy of the gate outside its transaction would conflict with 142. The spend is bounded by `max_cost_usd` per run and by the concurrency cap. The cost is acknowledged in Special Considerations.

### Run Digest

- Response length: 4938 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 406733 / 295325 / 111396 / 6943 / not computed
- Duration: 58.4 s
- Cost: $0.55 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
