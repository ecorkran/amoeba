---
docType: review
layer: project
reviewType: slice
slice: contract-proof-and-hardening
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 28a187f6a8e1472dfcefb70071179f76690f9dcb
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Architecture principles are demonstrated, not just claimed"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Technical Decisions"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Contract-narrowing changes are gated, not smuggled"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#PM ratification"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated per kill point with explicit recovery"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Restart injection (D4)"
  - id: F004
    severity: pass
    category: dependency-direction
    summary: "Dependency directions correct"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Component Structure"
  - id: F005
    severity: note
    category: integration-points
    summary: "Cross-slice dependency on 106's transactional report-back is open-ended"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Interfaces Required"
  - id: F006
    severity: note
    category: under-specification
    summary: "Slug pattern permits trailing dots"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D5"
  - id: F007
    severity: note
    category: error-handling
    summary: "Read-only store concurrency during prune not discussed"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Pruning (D7)"
---

# Review: slice — slice 110

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Architecture principles are demonstrated, not just claimed

D1–D7 map cleanly onto the architecture: command-before-result with reconcile-by-observation (kill points `after-issue`/`after-launch` mirror the architecture's zero/one/several-match rule), sole-writer model preserved (`proof_host.py` constructs `ResidentProcess`, which opens stores through `project_stores.py`), and D7's report-only pruning honors both "pruning policy is Amoeba's" and "State is the interface" from the architecture's Squadron run lifecycle section. The rejected alternatives (direct Store API tests, `--tenant` flag, Amoeba unlinking files, age thresholds) each cite a concrete principle.

### [PASS] Contract-narrowing changes are gated, not smuggled

D5 narrows 101's published store contract in two places (relative directory refusal, ASCII-slug project ids). The design identifies both explicitly, publishes the before/after, states the fallback if not ratified, and gates Phase 5 task breakdown on the PM ruling. This is the correct handling of a slice that must amend an upstream slice's contract.

### [PASS] Failure modes enumerated per kill point with explicit recovery

Each kill window (`after-issue`, `after-launch`, `inbox-while-down`, `mid-follow`) specifies what recovery must do, the resulting journal/block state, and the expected snapshot difference — plus a load-tier matrix covering every step boundary. Harness waits are condition-with-timeout rather than fixed sleeps, and the one swallowed exception (`FileNotFoundError` on a run file vanishing mid-listing) is justified with the concrete race it covers, per project exception rules.

### [PASS] Dependency directions correct

`run_pruning.py` sits in `amoeba.upstream.squadron` (adapter layer) reading Squadron files, with the store explicitly kept free of Squadron knowledge; the store imports nothing from `amoeba.upstream`/`amoeba.process`/`amoeba.feed`; the writer guard is unchanged. The AST-based `test_public_only.py` guard plus hand-pinned `__all__` sets make the boundary mechanical.

### [NOTE] Cross-slice dependency on 106's transactional report-back is open-ended

The design requires a new public one-transaction report-back method from 106 and provides a fallback ("if 106 ships without it, this slice adds it"). This is workable but means the slice may grow a store method beyond its stated hardening scope; if the fallback fires, the gap table should record it as a 106 contract gap assigned here, not silently absorbed.

### [NOTE] Slug pattern permits trailing dots

`[a-z0-9][a-z0-9._-]*` allows ids ending in `.` or `.-` (e.g. `proof.`), which some filesystems and URL contexts treat awkwardly. Harmless on the current targets, but the contract-indexed rule should either forbid trailing `.`/`-` or document why it is accepted; the first-character anchor does correctly exclude `..`.

### [NOTE] Read-only store concurrency during prune not discussed

`amoeba prune sq-runs` opens every project's store read-only while the resident process may be actively writing. SQLite allows concurrent readers, so this is likely fine, but the design does not state the behavior if a store is locked mid-write (e.g. `SQLITE_BUSY` during a commit). A one-line disposition (retry or report the store as unreadable) would close the last implicit I/O path.

### Run Digest

- Response length: 5243 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 1904
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
