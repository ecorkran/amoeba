---
docType: review
layer: project
reviewType: slice
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 4ffb8b8b6f10aea13ec50751e6930cbb8445e974
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 99470
cachedTokens: 11028
cacheWriteTokens: 88438
completionTokens: 5704
durationSeconds: 47.6
costUsd: 0.412571
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Slice is overweight; several mechanisms have no consumer yet"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Technical Scope"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Writer model and Squadron boundaries are respected"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8, #D3"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8, #Success Criteria"
  - id: F004
    severity: note
    category: layer-responsibilities
    summary: "Pruning policy lives in the upstream adapter package"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Component Structure"
  - id: F005
    severity: note
    category: integration
    summary: "Ownership guarantee relies on a contract line that 120 must honor"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8 (The ownership guarantee)"
  - id: F006
    severity: note
    category: dependencies
    summary: "Design names surfaces from unmerged slices, and two values are unconfirmed"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Dependencies"
  - id: F007
    severity: note
    category: scope
    summary: "The proof drives the Runner through the `intent` channel"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D3"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice is overweight; several mechanisms have no consumer yet

The slice carries four parts (proof, hardening, pruning, docs) and an effort of 3. The gate for initiative 120 is the contract proof plus the hardening. Pruning is assigned scope, so it stays. The pieces around it can be cut or deferred:
- **`--json` and `--older-than-days`** on `amoeba prune sq-runs` (D8, API Contracts). Nothing consumes either. `PruneSettings.retention` already holds the value, and 120 may call `select_prunable` directly (Excluded). Ship the preview and `--yes` only.
- **`scripts/demo_prune.py`**, with instance-lock handling and a writer-guard allow-list entry (Technical Scope, Verification Walkthrough step 4). It exists only to seed a manual walkthrough. The stub-`sq` tests and the schema-v5 fixture already cover the selection and the deletion path. Cut the script, or limit the walkthrough to one real-`sq` run against a fixture-seeded `HOME`.
- **`test_docs_cover_exports.py`** (D9). It makes every future export fail the suite unless its name appears in backticks in some `docs/*.md`. That couples all later slices to documentation formatting. H1 and H3 already require doc updates. Replace it with a one-time checklist item.
- **`test_locality.py`** (D6). Slice 101 decided locality. The scenario already starts every subprocess against one supervisor directory. Keep only the unique check, which is the project-keying isolation (alpha vs beta). Drop the separate `XDG_CONFIG_HOME` and two-working-directory matrix unless 101's and 102's tests lack them.
- **The network subset's second kill.** Both kills are handed to this slice by 109's design, so keep them. The point is that the subset should not grow past D2's three bullets.
- **Prose that restates other documents.** The dated Squadron observations in Dependencies, and the "Hardened in 110" and "Known gaps" guide sections, repeat what D7 and `CHANGELOG.md` already carry. State each once.

### [PASS] Writer model and Squadron boundaries are respected

- **Runner and reads:** `ProofRunner` is an in-process tenant writing through the store API, which is the Runner's documented position. Pruning and the oracle open stores read-only, and no new state or migration is added. This matches the architecture's sole-writer model and its "reads open to every part" rule.
- **Squadron files:** deletion goes only through `sq runs prune`, with non-TTY stdin as the architecture requires. Amoeba never unlinks a Squadron file, which satisfies "no part edits SQ's run files directly".
- **Pruning policy:** it implements the architecture's line "pruning policy is Amoeba's" and its use of the owned-run record for pruning.

### [PASS] Failure modes are enumerated for each new I/O path

- **`sq` failures:** missing, failing, timing out, and refusing a live run are all handled. The result is decided by observing the runs directory, not by parsing sq's output.
- **Timeout:** on timeout, the `sq` process is killed and awaited before observation, so the report is final.
- **Retries:** reruns converge. An unreadable store refuses the whole command before `sq` is called.
- **Proof harness:** waits are predicates with timeouts. The network subset covers a server kill, a resident-process kill, and a POST made while the resident process is down.

### [NOTE] Pruning policy lives in the upstream adapter package

`amoeba.upstream.squadron.run_pruning` holds Amoeba's retention policy. The architecture treats `upstream` as the adapter for external formats, and pruning policy is Amoeba's. The layering rules keep it pure, with no store, inbox, or process imports, so no boundary is broken. If more Amoeba-side policy accumulates there, move it. No action is needed now.

### [NOTE] Ownership guarantee relies on a contract line that 120 must honor

`record_runner_report` enforces `run_id` in `result` for `sq_run` entries. Direct `journal_resolve` calls by 120 are bound only by a documentation line. If 120 omits `run_id`, its runs are never owned and never pruned, so the failure is safe and the cost is leaked paused runs. Make sure 120's slice design cites this line.

### [NOTE] Design names surfaces from unmerged slices, and two values are unconfirmed

- **Unmerged surfaces:** 107, 108, and 109 are `not_started`. Names taken from them include `discover_project_ids`, `nodes_for_project`, `amoeba.upstream.context_forge`, and exit code 13. The first-task gate (stop for the PM, then reconcile names) handles this adequately.
- **Unconfirmed values:** the 7-day retention default is "pending PM confirmation", and the exit code 14 is "confirmed after 109 merges". Settle both at that gate.

### [NOTE] The proof drives the Runner through the `intent` channel

The architecture defines `intent` as Translator → Runner. `ProofRunner` repurposes it as a test driver, with step and crash-point names in the body. This is acceptable for test code, but the substrate guide should say that the intent body format is the proof's own, so 120 does not read it as a contract.

### Run Digest

- Response length: 6171 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 99470 / 11028 / 88438 / 5704 / not computed
- Duration: 47.6 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
