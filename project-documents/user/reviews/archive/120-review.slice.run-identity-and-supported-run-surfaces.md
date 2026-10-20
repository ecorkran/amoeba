---
docType: review
layer: project
reviewType: slice
slice: run-identity-and-supported-run-surfaces
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 971fb6e79757d0aa10302202f0715a96449bc52a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 106139
cachedTokens: 11266
cacheWriteTokens: 94869
completionTokens: 6545
durationSeconds: 55.5
costUsd: 0.446864
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Alignment with the architecture's run-identity and supported-surface contract change"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Technical Decisions"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O path are enumerated"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D2 — One outcome reader, modelling only what is read"
  - id: F003
    severity: concern
    category: integration-contract
    summary: "The `not_applied` guarantee given to 122 contradicts D4's own caveat"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Provides to Other Slices"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs; cuttable scope"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Verification Walkthrough"
  - id: F005
    severity: note
    category: layering
    summary: "Placement of the shared outcome reader"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Component Structure"
  - id: F006
    severity: note
    category: design-choice
    summary: "Startup sleep inside the grace window is a design choice the architecture did not specify"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D4 — not_found: the launch grace period"
---

# Review: slice — slice 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture's run-identity and supported-surface contract change

The design delivers the architecture's "Contract changes the Runner needs from 100" items that concern run identity: `run_id` becomes a required `sq_run` key (D1), and a by-id observer replaces matching (D3). Recovery and paused-run pruning both move onto `sq runs wait --json` (D2, D6). Legacy matching is kept only for entries journaled without an id, as the architecture states. The grace-period rule (D4) follows the architecture's "Run identity" paragraph: `not_applied` after the launch grace, with an unknown value escalating. Unknown or ambiguous outcomes escalate instead of being defaulted, which matches "Unknown escalates". The design does not absorb 121's contract changes or 122's and 125's launching and ingestion work, so scope boundaries hold.

### [PASS] Failure modes for the new I/O path are enumerated

D2 lists every failure of the `sq runs wait` call:
- a missing `sq`
- a timeout
- other OS errors
- exit 2 or an unmapped exit code
- non-JSON output
- an outcome that disagrees with the exit code
- a mismatched `run_id`

Each becomes a `PollFailure` that escalates, with no retry. D4 also bounds worst-case startup delay and puts that bound under a load-tier test. Nothing is left as "TBD". The architecture's "tick never waits" NFR is respected: the slice adds no subprocess call inside a tick.

### [CONCERN] The `not_applied` guarantee given to 122 contradicts D4's own caveat

Provides to 122 says it "can rely on recovery having resolved every id-bearing entry as … `not_applied` (safe to reissue after one more poll)". D4 states the opposite: a run whose state was later removed, for example by `sq runs prune`, also returns `not_found` and is marked `not_applied`. A reissue under the same id would then be accepted, because the taken-id refusal no longer applies. The Risk Assessment names this as the slice's main hazard, "122 launch the same work twice".

The architecture's exactness argument ("a taken id is refused, so a crash can never produce a second run") holds only while the run state exists. The slice defers the compensating launch-log check to issue #9 in 122, which is a reasonable split. But the interface contract for 122 should not call `not_applied` "safe to reissue" before that check exists.

Fix: reword the 122 bullet and the `process-contract` Recovery text so `not_applied` means "no run state found after the grace period". Say reissue is permitted only after the repoll and the launch-log check. Confirm that issue #9 is filed and cross-referenced from the 122 slice plan entry.

### [CONCERN] Design is heavier than the slice needs; cuttable scope

The core deliverable is the outcome reader, the by-id observer, the required key, and pruning on outcome documents. Several parts add effort beyond that:
- **Real-`sq` walkthrough steps 3–6.** They need a new `--adopt-run-id` option in `scripts/demo_journal.py`, a scratch supervisor directory, and a timed `sleep 10` start/stop. The automated stub-based tests, including the D8 no-reads tests and the contract suite, already prove every criterion. Cut the walkthrough to steps 1–2, plus at most one read-only `sq runs wait` check of the live surface (step 3). Drop the demo-script extension and its two new cases.
- **The 15-file consumer list in the Migration Plan.** The slice itself says the task breakdown must re-grep and not trust this list. Keep only the shared `sq_run_parameters` helper and the instruction to re-grep.
- **A separate `sq_run_dispatch.py` module.** The dispatcher is a single branch on `PARAM_RUN_ID` presence. It can live beside the by-id observer or in the registry wiring, which removes one module and one export.
- **`--launch-grace` start flag.** The setting is required (the architecture lists the launch grace period under Settings), but the flag exists mainly to shorten the walkthrough. If the walkthrough is cut, the flag has no consumer in this slice. Confirm other `ProcessSettings` fields all have flags before keeping it for consistency.
- **Restated Squadron exit-code and field table in Interfaces Required.** It duplicates `docs/COMMANDS.md` and D2. A pointer would do.

Dropping these does not defer any scope the slice plan assigns, since they are verification and packaging extras.

### [NOTE] Placement of the shared outcome reader

`sq_outcome.py` sits under `process/observers/`, but it is meant to be the reader that the pruning CLI, 122's Observe stage and 125's ingestion all share. Pruning's import-boundary test (D8) forbids `observers.sq_runs` while allowing `observers.sq_outcome`, so the package location carries a distinction that is easy to break. The dependency directions are still correct. If the module is likely to grow with 125's `failure` and `reviews` models, consider placing it where those consumers import from, outside the recovery-specific `observers` package. This does not need to block the slice.

### [NOTE] Startup sleep inside the grace window is a design choice the architecture did not specify

The architecture defines behavior only after the grace has passed. D4 handles the in-grace case by sleeping at startup, bounded to one `launch_grace_seconds` across all entries, then polling once more. This is bounded, tested with injected clock and sleep, and runs before any tenant ticks, so it does not violate the tick obligation. The design records the rejected alternatives. Startup delay of up to 60s after a crash close to a launch is an accepted cost.

### Run Digest

- Response length: 6747 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 106139 / 11266 / 94869 / 6545 / not computed
- Duration: 55.5 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
