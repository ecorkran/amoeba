---
docType: review
layer: project
reviewType: slice
slice: resident-process-and-recovery
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/102-slice.resident-process-and-recovery.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260919
dateUpdated: 20260919
reviewedSha: 70556b4ede3d77f77a6c41ec72f82fffb292d70d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice-plan inspection criterion is unmet as written and the deviation is not yet ratified"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:399"
  - id: F002
    severity: concern
    category: alignment
    summary: "CF-side provenance unspecified against \"provenance on every ingested fact\""
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:70"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Three lifecycle failure modes are implicit rather than enumerated"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:234"
  - id: F004
    severity: note
    category: dependencies
    summary: "Load-bearing Squadron facts are dated observations unverifiable in this repository"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:76"
  - id: F005
    severity: note
    category: risk
    summary: "The WAL read-only fallback would soften the sole-writer invariant it exists to enforce"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:365-372"
  - id: F006
    severity: note
    category: nfr
    summary: "Load-tier bounds are placeholders pending implementation"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:389"
  - id: F007
    severity: pass
    category: alignment
    summary: "Reconcile-by-observation implements the architecture's command-before-result principle exactly"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:193"
  - id: F008
    severity: pass
    category: writer-model
    summary: "Sole-writer model made mechanical rather than conventional"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:173"
  - id: F009
    severity: pass
    category: integration-points
    summary: "Interfaces claimed from slice 101 all exist as described"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:76"
  - id: F010
    severity: pass
    category: error-handling
    summary: "\"Unknown is a value\" carried through every new external failure mode"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:195"
  - id: F011
    severity: pass
    category: dependencies
    summary: "Technology and scope choices stay inside the architecture and project rules"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md:171"
---

# Review: slice — slice 102

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Slice-plan inspection criterion is unmet as written and the deviation is not yet ratified

Description: The slice plan's slice-102 success criterion requires the inspection surface to "list nodes, findings, verdicts, and journal entries." Findings and verdict records do not exist until slice 104, which depends only on [101] and follows this slice. The design ships nodes, blocked states, and journal entries plus a listing registry that 104 extends — a sound resolution — but the slice plan entry is unedited and D4 is listed as awaiting PM ratification (the exclusion is also stated at line 54). Until the PM ratifies the split and the slice plan is edited, this slice cannot satisfy its own acceptance contract as written. Action: record the PM decision and split the criterion between 102 and 104 in `100-slices.substrate-run-state-store.md` before Phase 6 completes.

### [CONCERN] CF-side provenance unspecified against "provenance on every ingested fact"

Description: The architecture lists "Provenance on every ingested fact" as a principle and, under Technical Considerations, requires that "every ingested record stores the upstream version it was parsed from" because both upstreams change without semver. The design honors this for Squadron — observers "record the run file's own `schema_version` in the journal result as provenance" — but is silent for Context Forge: an adopted `cf_write` result carries the observed values with nothing stating which CF version produced them, or why that is unobtainable. An adopted read-back is exactly the kind of ingested fact the principle covers. The slice plan attributes the record-the-upstream-version requirement to slices 104 and 105, but the architecture's wording is general and this slice parses two unversioned upstreams. Action: specify CF version capture in the journal result, or state explicitly that `cf get --json` exposes no version and what is recorded instead.

### [CONCERN] Three lifecycle failure modes are implicit rather than enumerated

Description: The observer paths have an exhaustive `Unknown` ladder (line 195), but three process-lifecycle paths stop short of an explicit strategy:
1. **Lock held, PID file absent or unreadable.** `stop` "confirms the lock is held, sends `SIGTERM` to the recorded PID," with exit codes only for `NOT_RUNNING` and `STOP_TIMEOUT`. The start sequence is acquire lock → write PID file (line 112), so a live process can hold the lock with no PID file yet; a corrupt JSON PID file leaves `stop` with a confirmed holder and no signal target. `status` has a state for the stale-pid case; `stop`'s behavior in it is unstated.
2. **In-process grace-period expiry.** The bound exists (lines 42, 270) but what the process does at expiry — exit code, whether a tenant mid-tick is abandoned, what is logged — is unstated. The crash-only stance makes the *outcome* recoverable, but this is the one path where the process must decide rather than converge, and the handling is currently implicit.
3. **A tenant that hangs.** `stop_requested` is a contract tenants "must honor" (lines 114, 169), and the tunables list (line 287) contains no per-tick bound. A future tenant (103's apply loop, 120's Runner) that blocks a tick indefinitely stalls both the loop and graceful shutdown with no enumerated failure mode; the only remediation is an external kill. Since 103 and 120 code against this seam, the design should state the posture explicitly — e.g., no per-tick timeout by decision (crash-only covers it; `stop` reports `STOP_TIMEOUT` and the operator kills), or a bound in `ProcessSettings`.

Each is cheap to close in the design; none undermines the approach.

### [NOTE] Load-bearing Squadron facts are dated observations unverifiable in this repository

Description: The matching rule (D5) rests on six facts about Squadron's run-state files, stated as "each checked in source." Squadron's source is not present in this repository (only the ai-project-guide submodule exists; no `src/squadron`), so I could not confirm them. The design mitigates correctly — the observation is dated (20260919), observers tolerate unknown fields, and a missing required field degrades to `Unknown` rather than a match — so upstream drift surfaces as escalation, not a wrong adoption. The real-files fixture requirement (line 288) is the right ongoing check; no action required beyond honoring it.

### [NOTE] The WAL read-only fallback would soften the sole-writer invariant it exists to enforce

Description: The stated invariant is that the resident process is the only thing that opens a store read-write, enforced by the guard test. The contingency for the WAL `mode=ro` risk — a read-write handle the inspection code never writes through, with the guard test extended to `cli/inspect.py` — is properly evidence-gated (test first, decide on results) and keeps the guard honest. If taken, `docs/process-contract.md` and the writer-model section of `docs/store-contract.md` should state the softened invariant explicitly rather than leaving "only the resident process opens read-write" standing.

### [NOTE] Load-tier bounds are placeholders pending implementation

Description: The crash-loop and recovery-scale tests assert against "a stated bound" / "a bound" (lines 292, 389) with no numbers in the design. The architecture document states no NFR targets for this path, so there is nothing to restate; the Python rules only require that the bounds be asserted. Naming candidate bounds now (start-to-ready, recovery time per entry) would let implementation measure against a target rather than invent one, but this can also settle at implementation time.

### [PASS] Reconcile-by-observation implements the architecture's command-before-result principle exactly

Description: The architecture specifies: journal before the side effect, never re-issue blindly, observe the external system, exactly one match adopted, zero-or-several becomes an explicit unknown that becomes a `blocked_on_human` node carrying the journal entry, with S9 as the eventual exact fix. The design implements every clause: `journal_issue` commits before the effect, the crash-point table distinguishes the three crash states by observation only, every ambiguity escalates (line 195), `journal_escalate` pairs outcome=`unknown` with a HUMAN block in one transaction, and S9 stays in Future Work exactly as the slice plan's Future Work #3 records. The already-blocked branch is consistent with the slice 101 contract as implemented — `block()` refuses an already-blocked node (`src/amoeba/store/blocking.py`) and the unique partial index `idx_blocked_states_open_node ... WHERE resolved_at IS NULL` exists in `001_initial.sql` — and the design handles it as an explicit branch rather than by catching `InvalidTransitionError`. The clock-tolerance relaxation of the arch's "created after the journal timestamp" is named, centralized in `ProcessSettings`, and errs in the escalation-safe direction.

### [PASS] Sole-writer model made mechanical rather than conventional

Description: The architecture's writer model (resident process is sole writer; reads open to every part) becomes enforceable here: `fcntl.flock` for liveness (kernel-released on any death, avoiding the stale-PID-file anti-pattern; the PID file is informational only), `Store.open_read_only` for out-of-process consumers, and an AST guard test in the manner of the existing `tests/test_store_safety.py` (verified: that file exists and is AST-based). Dependency direction is correct and honestly bounded: the guard covers `src/amoeba/` only and the design states plainly that it prevents accidental in-repo writes, not third-party imports. `open_read_only` never migrates and raises `StoreSchemaError` on an unexpected version, matching slice 101's newer-than-code rule.

### [PASS] Interfaces claimed from slice 101 all exist as described

Description: Every named prerequisite was verified against the shipped slice 101 code and contract: `Store.open`, `get_node`, `nodes_for_project`, `blocked`, `block(node_id, *, kind=, context=)` (the keyword signature matches `blocking.py` exactly), the `StoreError` family, `amoeba.store.paths` central-directory resolution, the numbered-migration mechanism, `EXPECTED_SCHEMA_VERSION = 2` (so migration `003` → 3 is the correct next step), `sql.py` at 306 lines (the stated reason for the `sql_journal.py` sibling is accurate), and the partial unique index the already-blocked branch relies on. The frontmatter `interfaces: [103, 105, 106, 107]` exactly matches the slices whose dependencies include 102 in the slice plan (103: [101,102]; 105: [101,102,104]; 106: [101,102,103,104,105]; 107: [101,102,105]) and correctly omits 104, which depends only on [101].

### [PASS] "Unknown is a value" carried through every new external failure mode

Description: Both new external I/O paths enumerate failure modes with explicit outcomes rather than defaults or TBD. Runs directory: missing/unreadable directory, unparseable run file (logged at WARNING, counted, named in the reason — never silently skipped into a confident answer), zero candidates, multiple candidates. `cf`: missing binary, timeout (a `ProcessSettings` tunable), non-zero exit, unparseable output. Each yields `Unknown` → `blocked_on_human`, which is the architecture's principle applied at the new boundary. Parameter validation at issue time (required keys per `CommandKind`, raising before the side effect) prevents the discover-after-crash failure. Unexpected exceptions are logged with `logger.exception` and re-raised, and a failed recovery aborts startup rather than letting tenants run against unreconciled state — consistent with both the architecture and the project's exception-handling rule.

### [PASS] Technology and scope choices stay inside the architecture and project rules

Description: D3's `pydantic` at the Squadron run-file and `cf get --json` boundaries satisfies the project Python rule ("Use `Pydantic` for all external boundaries (API inputs/outputs, file parsing, ...)" — verified in the rules) and this is the first slice that actually parses external data; `argparse` adds no CLI dependency; no new environment variables keeps `AMOEBA_STORE_DIR` the single environment read (verified in `paths.py`). The inspection surface, single-instance handling, and command journal are named in both the architecture ("the local inspection surface, the `sq artifacts list` analogue") and the slice plan, so nothing here is scope creep; exclusions correctly hand findings/verdicts to 104, the inbox to 103, the feed to 105, and pruning to 106. The `Tenant` seam generalizes the architecture's "hosts the Runner loop" without adding intelligence — recovery records outcomes and does not act on them, preserving "no intelligence in the substrate." The load-test tier attaches at exactly the slice the Python rules say it must (concurrency/process boundaries), closing the deferral slice 101 recorded.

### Run Digest

- Response length: 13009 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 66571
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
