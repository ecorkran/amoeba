---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: b125625692c18c030e6634fb30d69564e36dd647
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
turns: 20
promptTokens: 807390
cachedTokens: 688512
completionTokens: 89827
reasoningTokens: 85154
durationSeconds: 260.8
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: completeness
    summary: "Every slice success criterion maps to at least one task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F002
    severity: pass
    category: scope
    summary: "No scope creep: every task traces to a design decision or LLD scope item"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F003
    severity: concern
    category: validation
    summary: "Final validation omits the CI-gated format check"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F004
    severity: concern
    category: api-contract
    summary: "Judge actor steps omit the `submitted_by` binding required by 109"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F005
    severity: concern
    category: api-contract
    summary: "Judge-sample assertion points at a verdict listing, not a sample read"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F006
    severity: concern
    category: sequencing
    summary: "`after-step-N` attribution is ambiguous when two projects run the sequence"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F007
    severity: concern
    category: architecture
    summary: "`run_pruning.py` is told to reuse a helper from the process layer"
    location: "src/amoeba/process/observers/sq_runs.py#parse_run_file"
  - id: F008
    severity: concern
    category: task-sizing
    summary: "Two tasks are large enough to hide several independent outcomes"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F009
    severity: concern
    category: commit-cadence
    summary: "\"Committed with Task N.M\" chains collapse commits and, read literally, commit untested rows"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F010
    severity: note
    category: documentation
    summary: "Task 10.1 quotes lines that Task 5.9 will have changed"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F011
    severity: note
    category: ci
    summary: "Load-tier gating is explicit and already satisfied"
    location: ".github/workflows/ci.yml"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every slice success criterion maps to at least one task

Cross-referencing the LLD's Success Criteria section against the file: the clean-run assertions (three verdicts, two samples, one `ingested` + one `runner_issued`, nothing runnable/blocked, `finding_changes` naming round 1) are Task 5.9; the four crash windows and the expected-difference table are 6.1–6.4; the transcript/replay criterion is 6.5; `proof-b` keying is 5.9 plus 8.1; the three directory resolutions and the relative-variable refusal are 8.2 (with 2.1/2.2); the id refusals are 2.4 with 8.2; the four `done` refusals are 2.6; the pruning report rows and byte-identical guarantee are 9.5; the guard plus its self-test are 4.9; the export pins are 3.3 (deferred halves re-covered in 6.5); the store/upstream import boundaries and line limits are 11.1; the docs index and gap table are 10.4/10.5. Nothing in the LLD is left unowned.

### [PASS] No scope creep: every task traces to a design decision or LLD scope item

Sections 5–8 trace to D1/D4 and the Data Flow sequence table; 9.x traces to D7 (the pruning report, including the `RunDisposition`/`DispositionKind` name collision being settled in 9.1); 10.x traces to D3, D5, D6, D8 and the LLD's Included list (`docs/README.md`, contract updates, the Squadron dependency entry, `CHANGELOG.md`). Nothing here drafts Runner behaviour, adds model calls, or deletes Squadron files — the LLD's Excluded list is respected.

### [CONCERN] Final validation omits the CI-gated format check

Task 11.1 runs `uv run pytest`, `uv run pytest tests/load`, `uv run ruff check .`, and `uv run pyright`, and its Success Criteria say "Default suite, load tier, `ruff`, and `pyright` all clean". `.github/workflows/ci.yml` has a separate step, `uv run ruff format --check .`, which can fail the run independently of `ruff check`. Slices 101–103 all included `uv run ruff format --check .` in their validation tasks, so the omission is a regression from established practice and lets a reformat-only failure surface first in CI. Add the format check to Task 11.1's run list and its success criterion.

### [CONCERN] Judge actor steps omit the `submitted_by` binding required by 109

Task 5.8b creates a `judge` principal with `--scope submit` and POSTs verdict/sample/resolution bodies to `/v1/projects/proof/submissions`, but never states the body's `submitted_by`. 109's design and tasks make the principal binding a hard rule: a submission whose `submitted_by` differs from the token's principal is `403 principal_mismatch` (109 slice, error table; `tests/serve/test_writes_auth.py`). As written, a junior AI following 5.8b will get a 403 it cannot explain, and 5.8c's assertion that "a `submit` token's POST is accepted and applied" would fail for a reason unrelated to the scope logic it is meant to test. State the body field (`submitted_by: "judge"`) in 5.8b and name `principal_mismatch` (not `insufficient_scope`) as the expected failure mode in 5.8c.

### [CONCERN] Judge-sample assertion points at a verdict listing, not a sample read

Task 5.8c asserts "two judge samples exist as separate records (read through `inspect verdicts --json`)", while Task 4.4 defines a distinct snapshot field ("judge samples per gate") sourced from 107's read method. `inspect verdicts` is the two-verdict listing (`src/amoeba/cli/inspect.py:239`), and the LLD's clean-run criterion counts samples separately from verdicts. If 107 records both samples inside one verdict record keyed by `judge_invocation_id`, this assertion is either vacuous or wrong. Name 107's read method here (Task 1.1 is already charged with recording it) or state explicitly that samples are separate verdict rows so the read is justified.

### [CONCERN] `after-step-N` attribution is ambiguous when two projects run the sequence

Task 5.1 puts the kill point in one process-wide environment variable, and 5.9/7.1 parametrize over eleven `after-step-N` members while also running `proof-b` (steps 1–3 only) interleaved in the same supervisor directory. Neither task says which project's step boundary an `after-step-N` case targets, and 7.1's assertion ("snapshot equal to the clean run's") is single-project. With two projects reaching the same step, the first one to satisfy the predicate kills the process and the named-step wait can observe the other project's boundary, which is a plausible source of flakes exactly where the file demands "twice in a row". Pin the attribution (e.g. kill points keyed by project, or `proof-b` started only after `proof` passes the boundary) and say so in 5.9.

### [CONCERN] `run_pruning.py` is told to reuse a helper from the process layer

Task 9.1 instructs the author of `src/amoeba/upstream/squadron/run_pruning.py` to "read how `process/observers/sq_runs.py` reads the same field and reuse its parsing helper if it exposes one" — and `parse_run_file` is public (`src/amoeba/process/observers/sq_runs.py:72`). That would have `amoeba.upstream.squadron` import `amoeba.process.observers`, while 105's parser in the same package is consumed by process-side detection, a likely cycle; the only import boundary the LLD and Task 11.1 pin is the store's ("the store still imports nothing from `amoeba.upstream`/`amoeba.process`"). Either state the permitted direction explicitly, or place the shared reading of Squadron's `status` field in the upstream package and have the observer use it from there, so the dependency runs upstream ← process.

### [CONCERN] Two tasks are large enough to hide several independent outcomes

Task 5.9 (effort 4) carries the driver with both kill-owner branches, the full clean-run assertion set, `proof-b` interleaving, snapshot/path returns, and a three-times-no-flakes bar. Task 6.5 (effort 4) carries a local `--follow` subprocess, an SSE client with a reconnect function and a deliberate disconnect, a transcript-equality/replay check, a `proof-b` cross-check, and — if File 1 skipped them — the feed and squadron export pins. Each is a candidate for splitting (e.g. 5.9 → driver + clean assertions = 9; that task too = 9.1/6.5 → local check versus remote check) so a failure names one thing. Both remain completable as written, so this is a sizing concern, not a blocker.

### [CONCERN] "Committed with Task N.M" chains collapse commits and, read literally, commit untested rows

File 1's cadence rule is "one commit per task unless a task says 'committed with Task N.M'" and "a commit never holds untested behavior". Task 5.1 says "Committed with Task 5.2", while 5.2 says "Committed with Task 5.3"; Section 6 chains 6.1→6.2→6.3→6.4 the same way. Read forwards, each chain is one commit — but read literally at 5.1, the commit lands before 5.3's tests, i.e. with untested step-table rows, which the cadence rule forbids. Make the intent unambiguous (e.g. 5.1 and 5.2 both say "Committed with Task 5.3"), so the checkpoints stay one-per-test-task rather than batching.

### [NOTE] Task 10.1 quotes lines that Task 5.9 will have changed

Task 10.1 says to quote "the construction lines … from `proof_host.py` (Task 4.7)", and D3 describes "the three lines" for a tenant-less host. Task 5.9 then registers `ProofRunner` in `proof_host.py`, so the file 10.1 reads has four lines and the "Task 4.7" cross-reference is stale. The success criterion (diff the quoted lines against `proof_host.py`) catches any mismatch, so this is cosmetic; re-pointing the reference at the current file would remove the ambiguity.

### [NOTE] Load-tier gating is explicit and already satisfied

The restart matrix lands in `tests/load/test_restart_matrix.py` (Task 7.1), and `.github/workflows/ci.yml` already runs `uv run pytest tests/load` as its own step with no `continue-on-error`, so the matrix fails the build on its own. Task 7.1's step "confirm by reading it" makes the gating checked rather than assumed, which satisfies the requirement that CI wiring not be left implicit. The LLD also restates no numeric NFR (performance targets are explicitly excluded), so no separate NFR load task is owed.

### Run Digest

- Response length: 9702 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 307522
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 807390 / 688512 / 89827 / 85154
- Duration: 260.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
