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
reviewedSha: 953bff7e5383b0a3129a43faf9bd11dd596c5a76
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
turns: 19
promptTokens: 1014268
cachedTokens: 929024
completionTokens: 138300
reasoningTokens: 133196
durationSeconds: 413.5
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: api-contract
    summary: "`RunDisposition` is specified two incompatible ways, and the result record has no name"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:318"
  - id: F002
    severity: concern
    category: dependency-graph
    summary: "The hard-gate fallback instruction contradicts the dependency graph it sits next to"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:17"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Kill boundaries for actor-owned steps have no defined trigger, and Section 7 is told to reuse a driver that would have to change"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:265"
  - id: F004
    severity: note
    category: traceability
    summary: "`mid-follow` has no enum member and no row in the expected-difference mapping"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:176"
  - id: F005
    severity: note
    category: traceability
    summary: "Task 5.8 cites a Task 1.1 record that was never asked for"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:140"
  - id: F006
    severity: note
    category: documentation
    summary: "The contract index rows omit contracts that will exist by the time it is written"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:438"
  - id: F007
    severity: pass
    category: nfr
    summary: "Load-tier work exists for the slice's correctness tier and CI gating is verified, not assumed"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:270"
  - id: F008
    severity: pass
    category: traceability
    summary: "Every slice-design success criterion traces to at least one task, with no scope creep found"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `RunDisposition` is specified two incompatible ways, and the result record has no name

Task 9.1 says "Define `RunDisposition` as a `StrEnum` (`prunable`, `not_owned`, `not_paused`, `owner_not_done`, `unreadable`) **and** a result record with `run_id`, `path`, `status` …, `disposition`, `owner_node_ids`" — but never names the record. The slice design contradicts itself here, so the task cannot simply defer to it: `110-slice.contract-proof-and-hardening.md:244` ("Patterns and Conventions") makes `RunDisposition` the StrEnum, while `110-slice.contract-proof-and-hardening.md:284-285` (API Contracts) declares `classify_paused_runs(runs_dir, *, owned) -> list[RunDisposition]` and gives `RunDisposition` the *record* fields. A junior AI following the API Contracts table will annotate the return type as the enum, which cannot type-check under `pyright` strict, and will not know what to add to the hand-written pin test (Task 3.6 / 9.1: "export `classify_paused_runs` and `RunDisposition` … and add them to the pin test"). Task 9.2's assertions ("→ `prunable`") also do not say whether they compare records or enum members. Resolve by naming the record type and fixing the return annotation in the task (and flagging the LLD line for the documentation task).

### [CONCERN] The hard-gate fallback instruction contradicts the dependency graph it sits next to

The Context Summary says: "If any [of 105–109] is absent, do the sections that do not need it (8, 9.1–9.4, 10.1–10.3) and stop before the rest." The task file then declares dependencies that make that unworkable:
- Task 8.1 `**Dependencies**: 6.6` (line 280), and 8.1's own steps require "a clean run" and "the detection sidecars" (line 283) — the clean run is Task 5.9, which needs 105/106/107/109;
- Task 9.1 `**Dependencies**: 8.2` (line 313) — inherits the above, though 9.1 itself is pure;
- Task 10.1 `**Dependencies**: 5.9` (line 394), and 10.2/10.3 chain off it.

So a junior AI hitting the gate and following the fallback would start Section 8 with no runnable clean sequence and fail immediately, or start Section 10 with a dependency marked unmet. Either re-declare the deps (8.1 could depend on the harness/snapshot tasks, not 6.6; 9.1 on 1.1/4.x; 10.1 on 4.7/9.3) or correct the fallback list.

### [CONCERN] Kill boundaries for actor-owned steps have no defined trigger, and Section 7 is told to reuse a driver that would have to change

Task 5.1 puts "one boundary member per step 1–11" in `KillPoint` and states "the harness and tests reference only the enum" (line 32); Task 5.6 says "Each row also calls its `after-step-N` kill point at the end of its action" (line 113) — but only runner-owned rows (2, 3, 4, 6, 7, 11) exist, so nothing in `proof_runner.py` ever calls `kill_here(after-step-1/5/8/9/10)`. Task 7.1's third bullet (line 269) says the host "is killed right after the actor's effect is observed in public state" without saying by which mechanism (`kill_here` via the env var, or the harness's `kill_host()`), and its first bullet (line 265) says "Reuse `run_sequence` … do not copy it" although that driver (Task 5.9, line 157) is only specified to wait for states and trigger actors. If the driver must branch on actor-owned boundaries, Section 7 silently requires editing a `tests/contract` module from a `tests/load` task. Specify where the actor-boundary kill lives (likely: `run_sequence` handles every `KillPoint` member, the runner calls `kill_here` at the end of runner-owned rows only, and the harness kills for actor rows) so the eleven parametrized cases and the enum members agree.

### [NOTE] `mid-follow` has no enum member and no row in the expected-difference mapping

The slice design's kill-point table (`110-slice.contract-proof-and-hardening.md:144`) lists `mid-follow` as a kill point ("Not a separate run"). Task 6.1 defines the mapping "keyed by `KillPoint`" covering only `after-issue`, `after-launch`, `inbox-while-down`, and `after-step-N` (line 177), and Task 5.1's enum omits `mid-follow` (line 31). The behaviour is covered by Task 6.5's transcript checks, so this is naming/consistency rather than a coverage hole — but the LLD names a kill point that the enum and table both lack, which the "grep for the literal `after-issue` finds it only in the enum" style of check will not surface. Add the member or record explicitly why it is not one.

### [NOTE] Task 5.8 cites a Task 1.1 record that was never asked for

Task 5.8: "Use the HTTP client 109's tests use (Task 1.1 recorded it; `httpx` if that is what 109 chose)." Task 1.1 (`110-tasks.contract-proof-and-hardening-1.md:47`) instructs recording 105/106's names and "109's SSE client helper in `tests/`", but not 109's HTTP client. 109's tests use `starlette.testclient.TestClient` (in-process) and `httpx` is only a dev dependency (`109-tasks.network-api-1.md:362`); the Judge here needs an out-of-process client against `amoeba serve`. Since a subprocess client is what is actually needed, say so directly rather than pointing at an unrecorded value — this is exactly the class of dangling reference that makes a junior AI reach for a plausible-but-wrong token.

### [NOTE] The contract index rows omit contracts that will exist by the time it is written

Task 10.4 lists `store-contract.md`, `process-contract.md`, `inbox-contract.md`, `evidence-contract.md`, and 109's `network-contract.md`. Once 106 and 108 merge, `docs/feed-contract.md` (`106-tasks...-3.md:207`) and `docs/cf-contract.md` (`108-slice`, Included) will exist and answer questions 120/160 will ask; the task's Integration Requirement is "every answer one link away". The list mirrors LLD D8 verbatim, so this is a design-level omission rather than task drift — worth adding a row for each document present at implementation time.

### [PASS] Load-tier work exists for the slice's correctness tier and CI gating is verified, not assumed

The slice explicitly excludes performance targets ("this slice measures correctness"), and the only load-tier obligation is the restart matrix. Task 7.1 creates `tests/load/test_restart_matrix.py` for eleven cases and its success criteria require confirming gating by reading `ci.yml` (line 270). I verified `.github/workflows/ci.yml:53-54` runs `uv run pytest tests/load` as its own step, unsuppressed (`continue-on-error` is deliberately absent, line 11), and `pyproject.toml` excludes the tier from the default run via `--ignore=tests/load`. CI gating is therefore real and correctly stated as needing no wiring change.

### [PASS] Every slice-design success criterion traces to at least one task, with no scope creep found

Cross-reference result: clean-run criteria (nodes done, three verdicts, two judge samples, `ingested` + `runner_issued`, `finding_changes` naming round 1) → 5.9; kill-point recovery and snapshot equality → 6.1–6.4, 7.1; subscriber transcript across every kill plus replay → 6.5; `proof-b` isolation → 5.9, 8.1; four `done` refusals → 2.5/2.6 with the runner-level `InvalidTransitionError` case in 5.7; relative-directory and slug-id refusals at CLI/store level → 2.1–2.4 and 8.2; prune report classifications and byte-identical runs directory → 9.1–9.5; public-only guard with self-test → 4.9; five pinned export sets → 3.3–3.6; import-direction and writer-guard checks → 9.1, 11.1; link/anchor resolution → 10.5; index and obligations list → 10.4; gap table completeness → 10.5; `ruff`/`pyright`/suite/`wc -l` → 11.1. Tasks in 10.1–10.6 (hosting section, contract updates, Squadron dependency entry, CHANGELOG) trace to the LLD's Included scope and decisions D3/D5/D6/D7. No task was found that lacks a slice-design source. Sequencing is acyclic everywhere, test tasks immediately follow their implementation tasks (5.2→5.3, 5.4→5.5, 5.6→5.7, 9.1→9.2, 9.3→9.4), and commits are distributed per task or per implementation/test pair rather than batched at the end.

### Run Digest

- Response length: 9295 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 478526
- Effort: backend default
- Turns: 19
- Tokens — prompt / cached / completion / reasoning: 1014268 / 929024 / 138300 / 133196
- Duration: 413.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
