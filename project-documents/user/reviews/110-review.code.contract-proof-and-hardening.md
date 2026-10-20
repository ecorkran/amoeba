---
docType: review
layer: project
reviewType: code
slice: contract-proof-and-hardening
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: f55eb7174a6d18b96680d72f808e9fc8ac292584
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 99612
cachedTokens: 3232
cacheWriteTokens: 96378
completionTokens: 3559
durationSeconds: 29.5
costUsd: 0.429709
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Naive `updated_at` would crash selection with a TypeError"
    location: "src/amoeba/process/run_pruning.py:62"
  - id: F002
    severity: concern
    category: error-handling
    summary: "SSE follower thread can die silently on non-HTTP errors"
    location: "tests/contract/network.py:136-146"
  - id: F003
    severity: concern
    category: design
    summary: "Run-status literal `\"paused\"` is defined twice"
    location: "tests/contract/standin.py:26"
  - id: F004
    severity: concern
    category: design
    summary: "Prune timeout and retention are module constants in a \"pure\" module"
    location: "src/amoeba/process/run_pruning.py:25-30"
  - id: F005
    severity: note
    category: design
    summary: "Duplicated `only_node` helper"
    location: "tests/contract/steps.py:48"
  - id: F006
    severity: note
    category: style
    summary: "Stub `sq` script is built with `str.format`"
    location: "tests/sq_stub.py:77"
  - id: F007
    severity: pass
    category: design
    summary: "Atomic Runner report and journal refactor"
    location: "src/amoeba/store/runner_report.py:1-112"
  - id: F008
    severity: pass
    category: security
    summary: "Safe destructive-path design and test isolation"
    location: "src/amoeba/cli/prune.py:1-197"
---

# Review: code — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Naive `updated_at` would crash selection with a TypeError

`_is_prunable` computes `now - run.updated_at`. `SquadronRun.updated_at` is a plain `datetime | None` (src/amoeba/process/observers/sq_runs.py). If a run file carries a timestamp without an offset, pydantic yields a naive datetime. The subtraction then raises `TypeError: can't subtract offset-naive and offset-aware datetimes`. That aborts the whole `prune` command and gives no per-file diagnosis. Squadron's current files carry a `Z` suffix, so this is latent, but I did not confirm that the model rejects naive values. Either validate awareness in the model, or treat a naive value like a missing one ("unknown is not a value to guess"). Add a test for it.

### [CONCERN] SSE follower thread can die silently on non-HTTP errors

`SseFollower._run` catches only `httpx2.HTTPError` and `HarnessFailure`. `_record` can also raise `json.JSONDecodeError`, `KeyError`, or `ValueError` from `int(event.id)`. Those escape the thread, `error` stays `None`, and `_raise_subscriber_errors` never reports them. The test then times out with a generic message instead of the real cause. `Subscriber._run` handles this correctly by logging and storing the error. Apply the same pattern here, or narrow the exception list on purpose.

### [CONCERN] Run-status literal `"paused"` is defined twice

`run_pruning.PAUSED_STATUS` and `standin.STATUS_PAUSED` are separate definitions of the same value. The project rule is to define such a value once and reference it everywhere. The test stand-in can import the production constant, which would keep the proof and the selection rule from drifting apart. The same applies to `"completed"`, assuming the observer already has a constant for it.

### [CONCERN] Prune timeout and retention are module constants in a "pure" module

`SQ_PRUNE_TIMEOUT_SECONDS` is a subprocess concern, not selection logic, yet it sits in the module Rule 9 declares pure. `ProcessSettings` already holds `sq_timeout_seconds` and `cf_timeout_seconds`, and `run_prune` reads a module constant instead. The docstring says retention becomes a setting later, which is a reasonable deferral. The timeout belongs in config now to match the existing pattern.

### [NOTE] Duplicated `only_node` helper

`only_node` duplicates `_only_node` in `tests/contract/runner_tenant.py`, apart from a different error type. Consider sharing one. `steps.py` also uses the single-letter alias `h` for `self.harness` in several methods. Both are minor.

### [NOTE] Stub `sq` script is built with `str.format`

The Python rules prefer f-strings. Here `.format` is defensible, since the template contains literal braces and is written out as a script. It is also well documented with the observed `sq` behavior.

### [PASS] Atomic Runner report and journal refactor

The verdict, `runner_issued` ledger row, and entry resolution commit in one transaction. Every refusal path (wrong outcome, missing `run_id`, resolved entry, wrong kind, wrong project) is tested to leave state unchanged. Extracting `_resolve_entry_within` avoids duplicating the write. The MRO comment on `Store` explains the ordering.

### [PASS] Safe destructive-path design and test isolation

Amoeba never unlinks files itself. Stores are opened read-only, and an unreadable store refuses before `sq` is called, which is tested. `except FileNotFoundError` and `except TimeoutExpired` are specific and carry justification comments. The contract harness builds an explicit environment (nothing but `PATH`) and checks every path with `require_under` against `tmp_path`. `DEFAULT_SQ_RUNS_DIR` and `DEFAULT_CF_DATA_DIR` are added to the store-safety scan, with tests for both.

### Run Digest

- Response length: 4471 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 99612 / 3232 / 96378 / 3559 / not computed
- Duration: 29.5 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
