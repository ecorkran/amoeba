---
docType: review
layer: project
reviewType: code
slice: outbound-change-feed-and-detection-of-external-work
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 449187493cd4fca6d6381e3a3207e511158a580f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 124077
cachedTokens: 3232
cacheWriteTokens: 120843
completionTokens: 4242
durationSeconds: 36.9
costUsd: 0.579808
costBasis: provider
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: performance
    summary: "Every settled file is re-read in full on every scan, inside the synchronous tick"
    location: "src/amoeba/process/review_sources.py#DirectoryReviewSource._examine"
    resolution: accepted
    resolvedBy: "DirectoryReviewSource returns a settled file once per (size, mtime_ns) signature; load test asserts zero reads on a steady scan of 500 files"
  - id: F002
    severity: concern
    category: design
    summary: "`feed` without `--follow` loads the whole feed into memory before printing anything"
    location: "src/amoeba/cli/feed.py#_existing"
    resolution: accepted
    resolvedBy: "_existing is a generator; amoeba feed prints each batch as it is read"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A vanished store is reported as `StorePermissionError`"
    location: "src/amoeba/feed/follower.py#_wait_for_commit"
    resolution: rejected
    resolvedBy: "StorePermissionError for a missing store is the existing contract (Store.open_read_only raises it for 'no store exists'); a new type would change the store contract for every slice. A deletion mid-batch is noticed at the next idle check, which is enough for a follower"
  - id: F004
    severity: concern
    category: correctness
    summary: "`record_detected_verdict` can link a ledger row to a verdict from another project"
    location: "src/amoeba/store/_verdict_writer.py#VerdictWriter._record_verdict_within"
    resolution: accepted
    resolvedBy: "record_detected_verdict raises StoreIntegrityError inside its transaction when the verdict id is recorded in another project; tested. Unreachable in production, where each project has its own store file"
  - id: F005
    severity: note
    category: structure
    summary: "`examine` is well over the preferred function length"
    location: "src/amoeba/process/review_scan.py#examine"
    resolution: accepted
    resolvedBy: "examine split into _Examined.refuse, _attributed_node, and _ingest with explicit keyword parameters"
  - id: F006
    severity: note
    category: testing
    summary: "No load-test tier for the new polling and concurrency paths"
    location: "tests/feed/test_follower.py"
    resolution: accepted
    resolvedBy: "tests/load/test_feed_and_detection_load.py: steady scan reads no file (500 files, 4.5 ms); 1000-commit burst arrives in order, worst latency 257 ms"
  - id: F007
    severity: note
    category: style
    summary: "Duplicated import style and aliasing for the shared version-label helper"
    location: "src/amoeba/process/observers/cf_readback.py:33-40"
    resolution: accepted
    resolvedBy: "cf_readback imports the version_label module once; CF_VERSION_ARGS alias removed; cli/feed.py imports paths once"
  - id: F008
    severity: pass
    category: conventions
    summary: "Exception handling, vocabulary single-definition, and layering"
    location: "src/amoeba/store/feed_models.py"
---

# Review: code — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Every settled file is re-read in full on every scan, inside the synchronous tick

`_examine` calls `path.read_bytes()` for every settled file on every poll, and `poll()` returns all of them. The class docstring says this is intentional: "A settled file is returned on every poll while it stays settled". `examine` then hashes the bytes before the ledger check, so each file is read and sha256'd every `review_scan_interval_seconds` (2s by default), forever. The tenant loop is synchronous and shared with the inbox tenant, so a large or growing reviews directory slows the inbox and the stop check. Cost grows linearly with directory size. Instead, return a settled file once per signature, or check the ledger by `(path, size, mtime_ns)` before reading the bytes. I did not run a measurement, so this is based on the code only.

### [CONCERN] `feed` without `--follow` loads the whole feed into memory before printing anything

`_existing` reads the changes in batches but appends them all to one list and only then calls `_print_all`. This undoes the point of `feed_batch_size`: memory grows with feed length and the first line appears only after the full read. A generator that prints per batch would keep the batching. It would also keep the one-shot path consistent with `follow`, which streams.

### [CONCERN] A vanished store is reported as `StorePermissionError`

When the store file disappears mid-follow, the code raises `StorePermissionError(f"store at {path} no longer exists")`. A missing file is not a permission problem, and the docstring in `follow` documents this reuse. A caller or the CLI boundary mapping that treats this type as an access or permission fault will give the operator a misleading message. Prefer a dedicated or more accurate store error type. The existence check also runs only after a sleep inside the wait loop. A deletion that happens while batches are still being read is not noticed until the follower next goes idle.

### [CONCERN] `record_detected_verdict` can link a ledger row to a verdict from another project

For an existing verdict id, `_record_verdict_within` logs a WARNING and returns the existing record. It does this even when `existing.project_id != project_id`. `record_detected_verdict` then builds the ledger row from `record.id` and `record.node_id`. Verdict ids are content-derived, so a cross-project collision is unlikely. But if one happens, the ledger row in project A points at a verdict and node in project B, and `recorded_since` correctly returns False for it. The older `record_verdict` had the same "keep the first" behaviour. The new caller adds a cross-project foreign reference, so consider raising for a project mismatch in this path.

### [NOTE] `examine` is well over the preferred function length

`examine` is roughly 70 lines. It covers digest, ledger check, parse, attribution, verdict composition and recording, against a ~50-line project target. The nested `record(outcome, **fields: str | None)` closure also hides the `DetectionInput` field types from pyright strict. Extracting the "attribute" and "compose verdict" steps would shorten it and allow explicit keyword parameters.

### [NOTE] No load-test tier for the new polling and concurrency paths

The Python rules require at least one `tests/load/` test for code on concurrency paths. The follower (cross-process `data_version` wake-up) and the detection tenant (a scan inside the shared tick loop) are such paths. The slice has thorough functional and end-to-end tests. None of them asserts a latency or throughput bound, such as follower latency under a writer burst or scan time with N files. The first concern above is the kind of problem such a test would catch.

### [NOTE] Duplicated import style and aliasing for the shared version-label helper

The helper is imported twice from `amoeba.process.version_label`, once with an alias (`capture_version_label as capture_shared_label`). `CF_VERSION_ARGS` is also re-exported as a pure alias of `VERSION_ARGS`. This works, but a module-qualified import (`from amoeba.process import version_label`) would be clearer. `cli/feed.py` also imports `paths` and `project_store_path` from the same module in two statements.

### [PASS] Exception handling, vocabulary single-definition, and layering

Every `try/except` is specific and carries a justification comment, or logs with `logger.exception` and re-raises, as in `recording`. Change kinds and detection outcomes are defined once, and the migration repeats them as literals. `tests/test_import_boundaries.py` enforces the layering rules and that no module spells the vocabulary as string literals, and `test_feed_invariant.py` ties the trigger literals to the enums. Migration 006 has tests for upgrading a populated store, column parity and the cursor index. All SQL uses bound parameters. The new tests cover refusal paths and races against real captured review fixtures.

### Run Digest

- Response length: 5566 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 124077 / 3232 / 120843 / 4242 / not computed
- Duration: 36.9 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
