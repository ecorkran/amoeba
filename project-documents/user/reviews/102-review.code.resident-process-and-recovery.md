---
docType: review
layer: project
reviewType: code
slice: resident-process-and-recovery
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/102-slice.resident-process-and-recovery.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: 08d2f882cae186df5f86928ee5ddc74bb1beed9f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
findings:
  - id: F001
    severity: note
    category: correctness
    summary: "`stop` cannot honor `--stop-timeout`; the flag is defined but unreachable"
    location: "src/amoeba/cli/main.py:240"
  - id: F002
    severity: note
    category: tooling
    summary: "`scripts/` is outside the writer and safety guards' scanned sets"
    location: "scripts/demo_journal.py"
  - id: F003
    severity: pass
    category: correctness
    summary: "Command journal: ordering, atomicity, and idempotent re-run are correctly implemented"
    location: "src/amoeba/store/journal.py"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Exception-handling rule is followed rigorously"
    location: "src/amoeba/cli/main.py:280"
  - id: F005
    severity: pass
    category: concurrency
    summary: "Concurrency publication is explicit and documented"
    location: "src/amoeba/process/host.py"
  - id: F006
    severity: pass
    category: testing
    summary: "Test tiers carry mechanical guards; load tier is excluded from the default suite"
    location: "tests/test_store_safety.py"
---

# Review: code — slice 102

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [NOTE] `stop` cannot honor `--stop-timeout`; the flag is defined but unreachable

`_add_settings_flags` is registered only on the `start` subparser (main.py:112), but `stop_timeout_seconds` is a `stop`-side tunable — `lifecycle.stop` consumes `settings.stop_timeout_seconds` (lifecycle.py:106,114) and is dispatched with a bare `ProcessSettings()` (main.py:240). The result: the CLI exposes a `--stop-timeout` flag on `start`, a command that never uses it, while `amoeba stop --stop-timeout 5` is rejected by argparse as an unrecognized argument. A user who reads `amoeba start --help` sees a knob that does nothing; a user who wants to change the stop timeout cannot. The flag should live on the `stop` parser (with `settings_from_args` given a way to tolerate the other flags' absence), or the docstring in `ProcessSettings` should stop presenting it as a CLI-reachable knob.

### [NOTE] `scripts/` is outside the writer and safety guards' scanned sets

Two mechanical guards define "permitted writer" and "safe accessor" by scanning a fixed tree, and both exclude the new demo script by construction:

- `tests/test_writer_guard.py:36` builds `SOURCE_DIR = .../src/amoeba` and scans only that tree, so `Store.open` calls outside `src/amoeba/` are invisible to it.
- `tests/test_store_safety.py` scans `TESTS_DIR` only.

`scripts/demo_journal.py` calls `Store.open(project_id=PROJECT)` — a read-write open resolving the *central* per-supervisor store path — and sits in neither scanned set. This is not a latent bug today: the script is an intentional operator-facing demo (a third-party-style consumer the writer guard explicitly disclaims covering), and it requires the user to point `AMOEBA_STORE_DIR` at a scratch directory first. But it means "no read-write open outside `process/host.py`" is enforced only inside `src/`. If `scripts/` is expected to accumulate, a lightweight third guard (or an explicit `scripts/` exemption recorded in the same docstring that defines the scanned sets) would keep the invariant from silently eroding.

### [PASS] Command journal: ordering, atomicity, and idempotent re-run are correctly implemented

The journal implements the crash-safety contract precisely:

- `journal_issue` validates required parameter keys *before* any write (journal.py:84-89), then commits inside `with self._connection` — so the entry is durable before the side effect is issued. `test_issue_commits_before_returning` proves it via a second connection.
- `RESOLVE_JOURNAL_ENTRY`'s `WHERE outcome IS NULL` guard (sql_journal.py) makes a second resolve a zero-rowcount result that raises `InvalidTransitionError` rather than overwriting the first outcome — the property the crash-loop load test relies on for "never reconciled twice."
- `journal_escalate` writes the outcome and the blocked state in one transaction (`_block_for_entry` uses the same connection, not a nested `block()` call), and handles the already-blocked node as an explicit branch rather than by catching `InvalidTransitionError` — exactly matching the project's exception-handling rule (no catching an exception to do the job a guard check should).
- Migration 003's partial index `(project_id, issued_at) WHERE outcome IS NULL` matches the recovery query shape; parameterized queries throughout, no f-string SQL carrying caller data.

### [PASS] Exception-handling rule is followed rigorously

Every broad handler in the change is either the single documented process-boundary handler (`main.py:280 except Exception` → `logger.exception` + typed `FAILURE`), a narrow re-raise wrapper (`host.py:301 except Exception` → `logger.exception` then `raise StartupFailedError ... from error`; same pattern in `_recover_every_project`), or a specific-type catch with an inline justification comment (`read_pid_file`'s `OSError`/`JSONDecodeError`, `InstanceLock.acquire`'s `OSError`→`False`, `_close_stores`' teardown swallow). No bare `except:`, no `except Exception: pass`. The `BLE` ruff rule is enabled in pyproject.toml, so this is mechanically enforced going forward.

### [PASS] Concurrency publication is explicit and documented

Cross-thread state is small and each piece is published deliberately: `threading.Event` for `stop_requested`, `expired`, and `finished`; `_current_tenant_name` is written on the loop thread and read by the watchdog only after the grace wait — a documented happens-before (host.py:355-361). The grace watchdog uses `os._exit` only after the grace period with an explicit justification comment, and signal handlers do nothing but set the event (no I/O, no store access from the handler — avoiding the classic async-signal deadlock). Store thread-affinity (SQLite connections may only be used on their creating thread) is why the loop stays on the main thread, and the docstring says so.

### [PASS] Test tiers carry mechanical guards; load tier is excluded from the default suite

`test_store_safety.py` is a genuine multiline-aware AST guard against tests resolving the central store, and it verifies its own detector (`test_scan_finds_a_wrapped_reference`) so a passing guard isn't vacuous. `test_writer_guard.py` does the same for the sole-writer invariant, including a "permitted module still opens a store" drift check. The load tier (`tests/load/`) is excluded from the default suite via `addopts = ["--ignore=tests/load"]` and is explicitly collectable, satisfying the load-test-tier rule for code on the process/concurrency boundary. Crash-loop and recovery-scale tests assert bounds plus an *exact* scan-count invariant (the O(n·m) guard), not just functional correctness.

### Run Digest

- Response length: 6157 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
