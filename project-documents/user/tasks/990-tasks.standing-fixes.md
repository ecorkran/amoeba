---
docType: tasks
slice: standing-fixes
project: amoeba
lld: user/slices/990-slice.standing-fixes.md
dependencies: []
projectState: A permanent container. One group per fix.
dateCreated: 20261102
dateUpdated: 20261102
status: in_progress
---

## Context Summary

- Fixes that need several steps, one group each. See `rules/fixes.md`.
- Work on the target branch (`main` unless `git.integration_branch` is set). No slice branch, no review unless the Project Manager asks.

---

## log-flood: a test process wrote over 600 GB to a log

A resident process left running by a killed test run looped on a fault and wrote its log without bound. Measured cause: the Runner tenant reported a failed tick as work, so the host loop skipped its idle wait and logged one traceback per pass (about 3.7 MB/s, over 300 GB a day). Nothing capped a test child's files, and nothing killed children when pytest itself was killed.

- [x] **1. A failed tick is not work.** `RunnerTenant` returns no work after an unexpected fault and thins out repeated tracebacks (`tests/runner/test_tenant_fault_pacing.py`).
- [x] **2. A process cannot log without bound.** `BoundedStreamHandler` (`process/log_limit.py`) caps one process's log at 256 MiB; `amoeba start` and the crash-proof entry use it.
- [x] **3. Test children are capped and reaped.** `tests/process_containment.py`: `RLIMIT_FSIZE` on every child, children killed at exit, leaked children of an earlier killed session reaped at session start, and a guard test that no test calls `subprocess.Popen` directly.
- [x] **4. Contract docs.** `docs/process-contract.md`.

**Commit**: `fix: stop a failing tick from spinning the log, and contain test processes`
