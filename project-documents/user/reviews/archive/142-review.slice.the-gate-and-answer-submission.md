---
docType: review
layer: project
reviewType: slice
slice: the-gate-and-answer-submission
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/142-slice.the-gate-and-answer-submission.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: f0a77178137d43a997b80a82474ad682b995ccc7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 102510
cachedTokens: 11162
cacheWriteTokens: 91344
completionTokens: 4432
durationSeconds: 37.8
costUsd: 0.411657
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Gate placement and transaction semantics match the architecture"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D1 — The gate runs inside the submission transaction, passed in as a pure function"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "`submit_answer` bypasses the inbox validator that the architecture says every resolution goes through"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D5 — The answerer's submission is an ordinary resolution with a submission record"
  - id: F003
    severity: concern
    category: scope
    summary: "The start-up probe has no stated configuration source and runs before anything uses it"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D8 — The answering probe runs at start only when a project has an answerer section"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Some mechanisms handle cases this slice does not have"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D2 — The gate's checks, in order"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Lock contention and busy-timeout failure modes are implicit"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D4 — `submit_answer`'s outcomes, and why a lost race writes nothing"
  - id: F006
    severity: note
    category: dependencies
    summary: "Rejected-resolution handling depends on a later slice"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D6 — An answerer resolution the Runner rejects"
  - id: F007
    severity: note
    category: dependencies
    summary: "141 is not yet implemented"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#Prerequisites"
---

# Review: slice — slice 142

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Gate placement and transaction semantics match the architecture

The architecture requires one gate for every resolution and an answer count read inside the submitting transaction. It also requires one new store operation under `BEGIN IMMEDIATE` that branches on the outcome. D1 and the Data Flow deliver this with a pure `evaluate_gate`, bound by `partial` and called once under the write lock. The store knows no terms or limit. Dependency direction is correct: runner depends on store types, and the store imports nothing from the Runner. D4's "PM answered first" handling follows the architecture's "discard and leave the record to the acknowledgment". D3 counts only the answerer's answers, which matches the architecture's wording of "how often it may answer one run".

### [CONCERN] `submit_answer` bypasses the inbox validator that the architecture says every resolution goes through

The architecture says "The answer goes back through the PM's door... One path, one validator, and a submission record of who answered." D5 does not call `apply_submission`, because it opens its own transaction. Instead it fills the slot with `_write_resolution` and inserts the row with the extracted `_insert_submission`. Only the insert and the slot write are shared. The slice never says which of `apply_submission`'s validations `submit_answer` reproduces and which it drops. Candidates are:
- decision vocabulary.
- that `resume` requires instructions.
- block kind and state.
- node match.

Today the slice checks only "block resolved" and "blank answer/instructions". The decision is passed as a plain string the store "reads none of". A wrong `decision` from a later caller would therefore write a malformed slot and an `applied` submission row. The Risk section names only the "second writer of the slot" and not the second validator. Either extract the validation into a shared step that both paths call, or list in D5 the checks `submit_answer` applies and why the rest are safe to omit.

### [CONCERN] The start-up probe has no stated configuration source and runs before anything uses it

D8 calls `probe_answering_pipeline(settings, …)` when any project has an `answerer` section. After this slice the section holds only `answer_limit` and `reserved_terms`. The architecture puts the answering pipeline and its models in per-project configuration. The D7 example shows `pipeline: p456`, which is 132's pipeline and not an answering pipeline. The slice never says where the probe gets the pipeline it validates.

It is also a hidden dependency on 140's D9, and the dependency is recorded only as "does not wait on Squadron". The probe has no consumer until 144. Meanwhile it makes `start` fail with `STARTUP_FAILED` for any configured project, even though nothing answers yet. Verification step 5 admits the outcome depends on the installed `sq`.

Either name the config key the probe reads, or defer the wiring to 144, where the answering pipeline config arrives. If the slice plan assigns the wiring to 142, restate that and name the config source.

### [CONCERN] Some mechanisms handle cases this slice does not have

- **Check 1 (question missing).** D2 says the branch is "a guard" because 141's settle step already declines null questions before any run. `evaluate_gate` and `AnswerGate` take `question: str | None` only to serve this unreachable branch, and it needs its own `GateRefusal` path and tests. `submit_answer` already raises `ValueError` for programming errors such as a blank answer. Reject a null question the same way, or let 141's record invariant carry it, and cut the branch.
- **Constants in `gate.py`.** `ANSWERER_SUBMITTER` and `ANSWERER_DETAIL` sit in the pure gate module, although D5 says they are never read to decide anything. They are submission provenance, not gate logic. Put them with the answer-submission code, or with the caller in 144, so `gate.py` stays pure screening.
- **Extra `submission_id` link.** D9 adds `submission_id` to the record in addition to `answered_by`. The architecture does not require it, and the slice names no reader. The submissions listing already shows the row. Name the consumer or drop the column.

### [CONCERN] Lock contention and busy-timeout failure modes are implicit

This is a new write path that takes the store's write lock. D4 covers three failure modes explicitly: crash mid-transaction, a gate that raises, and a lost race. It says nothing about `BEGIN IMMEDIATE` failing on a busy database, or about what the caller (144) sees. "Same rule as `apply_submission`" in Patterns and Conventions implies the store's existing busy handling, but D4 and the API Contracts table do not say so. One sentence naming that behavior and the exception the caller sees would close it.

### [NOTE] Rejected-resolution handling depends on a later slice

D6 accepts that a rejected answerer resume leaves the record `answered`, counts toward the limit, and is not recorded as precedent. It rests this on 144's shared journal reader and a 144 test. The reasoning is explicit and consistent with "failures decline; nothing retries", and the decision is reasonable. Keep the 144 test as a named requirement in 144's design, because 142's safety argument for this path depends on it.

### [NOTE] 141 is not yet implemented

The design is written against 141's contracts, and it says so and asks for a name re-check before the task breakdown. That handling is adequate.

### Run Digest

- Response length: 6647 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 102510 / 11162 / 91344 / 4432 / not computed
- Duration: 37.8 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
