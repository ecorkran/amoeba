---
docType: review
layer: project
reviewType: slice
slice: contract-proof-and-hardening
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: f66d2cc3e3877c2349552884504df6eed3bae5fd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: governance
    summary: "Four technical decisions are marked \"PM pending\", including one that deliberately violates a stated architectural principle"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Technical Decisions"
  - id: F002
    severity: note
    category: scope
    summary: "Architecture assigns pruning policy to Amoeba; D7 implements it with correct scoping"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7 — Pruning is an operator command over Amoeba's own dead paused runs"
  - id: F003
    severity: note
    category: error-handling
    summary: "Failure modes are enumerated with explicit handling, and dependency directions are respected"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Restart injection (D4)"
  - id: F004
    severity: note
    category: nfr
    summary: "NFR coverage"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Excluded"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Four technical decisions are marked "PM pending", including one that deliberately violates a stated architectural principle

D3, D5, D6, and D7 each carry "(PM pending)". D7 in particular sanctions an exception to the architecture's "State is the interface" principle ("no part edits … SQ's run files directly", 100-arch.substrate-run-state-store.md, "State is the interface" / "Writer model"). The design argues the exception well (dry-run default, ownership check, re-read before delete, no automation, dependency-register request for a Squadron-provided delete command), but a design that depends on an unratified violation of a core principle should not proceed to implementation without that sign-off. The same applies to D5/D6, which change 101's already-published store contract (project-id restriction, `done` enforcement) — the change-recording path (contract doc + CHANGELOG, not editing 101's design) is sound, but the contract change itself is unratified.

### [NOTE] Architecture assigns pruning policy to Amoeba; D7 implements it with correct scoping

The architecture states "Paused runs are never pruned on SQ's side; pruning policy is Amoeba's" and notes "paused runs are never pruned" as a current-state fact. D7 matches this: ownership is proven from Amoeba's journal and `sq.run_id`, Squadron's own completed/failed runs are left alone, and pruning is operator-triggered, not automatic. No scope creep.

### [NOTE] Failure modes are enumerated with explicit handling, and dependency directions are respected

The three kill windows each name the recovery behavior (zero-match → `unknown` → `blocked_on_human`; one-match adoption; inbox applied on start), the harness uses condition-with-timeout waits rather than sleeps, and the single swallowed exception (`FileNotFoundError` at unlink) is justified per project rules. The store remains free of Squadron knowledge (`run_pruning.py` sits in `amoeba.upstream.squadron`; the store imports nothing from upstream/process/feed), preserving the architecture's layering.

### [NOTE] NFR coverage

The parent architecture states no numeric NFR targets (no latency/throughput budgets), so nothing needs restating. The slice explicitly excludes performance targets and points at the 102–104 load tier, while adding a restart-matrix load test — consistent.

### Run Digest

- Response length: 3561 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 2374
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
