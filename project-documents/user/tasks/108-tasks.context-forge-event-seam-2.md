---
docType: tasks
slice: context-forge-event-seam
project: amoeba
lld: user/slices/108-slice.context-forge-event-seam.md
dependencies: [101, 102, 103, 106]
projectState: Sections 1–5 (file 1) are complete — real fixtures, the upstream reader and diff, migration 008 with `cf_watches` and `cf_snapshots`, the feed trigger, the store operations, the `watch_cf` kind, the watch-revision counter, and the three settings exist and are tested. This file holds `CFWatchTenant`, the listings, the `start` wiring, the end-to-end test, docs, and final validation.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **context-forge-event-seam** slice (108), continued from `108-tasks.context-forge-event-seam-1.md` (Sections 1–5). Read file 1's Context Summary, branch, reading note, commit cadence, and list of task-level mechanisms; they apply here unchanged.
- **Sections in this file:** 6 `CFWatchTenant`; 7 listings and wiring; 8 end-to-end, docs, final validation.
- **Branch:** still `108-slice.context-forge-event-seam`. No task here merges.
- **Migration number:** use the number recorded in Task 1.1 wherever "008" appears.
- **Wording differences:** where these tasks word settings, flags, or the idle-check differently from the LLD, the LLD governs; list each difference in Task 8.6. No load test or CI gate is planned (see file 1).
- **Coverage of file 1's criteria:** the reader and diff by Tasks 2.1–2.3; the migration, trigger, and invariant by Tasks 3.2–3.7; the kind by Tasks 4.1–4.3; settings by Task 5.1. Task 8.7 re-checks every LLD requirement against a named test.

---

## Section 6: `CFWatchTenant`

All tenant code is in `src/amoeba/process/cf_watch.py`, with the sidecar path in `src/amoeba/process/cf_layout.py` (Task 6.5; a module the LLD's component list does not name, added so the path is defined once; reported in Task 8.6). Tasks 6.3–6.4 use the real-`cf` harness from Task 1.3. The tenant follows `InboxTenant`'s host protocol shape (`settings`, `stop_requested`, `project_ids()`, `store_for()`). It takes its clock and its label-capture callable as constructor arguments so tests never sleep and never start a subprocess.

### Task 6.1: Tenant skeleton, scan cadence, watch cache, and the idle path
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 4
**Objective**: The common case costs one `stat` and no query (LLD Data Flow; Functional Requirements, last bullet).

**Steps**:
- [ ] Create `CFWatchTenant(supervisor_dir, *, capture_label, clock)` with `name` and `tick(host) -> bool`. A tick does nothing unless `cf_scan_interval_seconds` has elapsed on the injected clock since the last scan
- [ ] Watch cache: per project, each watch's `cf_project_id`, `active`, and stored `state`, plus the `cf_watch_revision` last seen. The tenant updates a cache entry's state itself whenever it calls `set_cf_watch_state` (that call never bumps the revision), so the cache knows which watches are `failed` without a query. Refresh a project's cache from `store.cf_watches()` only on first sight or when its revision differs (Task 4.3). A refresh that finds an active watch not in the previous cache marks the tenant dirty
- [ ] If no open project has an active watch, return without touching the file
- [ ] File signature: `(st_mtime_ns, st_size, st_ino)` of `projects.json` in `settings.cf_data_dir`, or `None` if `stat` fails with not-found. If the signature equals `last_sig` and the tenant is not dirty, return. Otherwise set `last_sig` **before** dispatch (an unrecognized or missing file is not re-read until the signature changes), clear dirty, and call a dispatch method that Tasks 6.2–6.3 fill in (here it is a stub)
- [ ] `last_sig` is memory only; a new tenant instance starts unset, which is the whole catch-up mechanism
- [ ] Add `tests/process/test_cf_watch_idle.py` with a fake host over real `Store`s (follow `tests/process/test_inbox_tenant.py`): no watches → no `stat`, no read; one active watch and an unchanged file → the second scan performs one `stat`, no `read_projects_file` call, and no call to `store.cf_watches`; a link made between scans (revision bump) triggers a dispatch; a deactivation refreshes the cache but, with no new active watch, does not dispatch; the interval gate holds with a fake clock; a replaced file (new inode, same size and mtime) dispatches

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(process): add CFWatchTenant skeleton and idle path`

**Files to Create**: `src/amoeba/process/cf_watch.py`, `tests/process/test_cf_watch_idle.py`

---

### Task 6.2: File-level states: `unreachable` and `unrecognized`
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 3
**Objective**: The two file-wide failures change every active watch's state and record nothing (LLD Errors).

**Steps**:
- [ ] In dispatch: signature `None` → every active watch `unreachable` via `set_cf_watch_state` (a no-op when already so); `ProjectsFileUnrecognized` → every active watch `unrecognized` with the error text as `detail`. `ProjectsFileMissing` raised after a successful `stat` (a race) is treated as `unreachable`
- [ ] Logging on transitions only, remembered per watch in memory: one ERROR when entering `unreachable` or `unrecognized`, one INFO when a watch leaves either for any other state. Never on a repeat scan. Neither failure raises: CF absent is not a sick store
- [ ] Never write into the CF data directory
- [ ] Add `tests/process/test_cf_watch_file_states.py`: no file → `unreachable`, one ERROR across several scans; file appears → INFO once and the state leaves `unreachable` (assert the state, not the snapshot, which Task 6.3 covers); `{}`, invalid JSON, an entry without `id`, and a duplicate `id` each give `unrecognized` with a distinct `detail`; an unrecognized file is not re-read on later scans until its signature changes (spy on the reader); a recognized file after it restores the state; a malformed entry in an unlinked project's record still blinds the watch (the LLD's deliberate trade-off)

**Success Criteria**:
- [ ] Tests pass; no snapshot and no feed entry is produced by any case here
- [ ] Commit, e.g. `feat(process): report unreachable and unrecognized Context Forge files`

**Files to Create**: `tests/process/test_cf_watch_file_states.py`
**Files to Modify**: `src/amoeba/process/cf_watch.py`

---

### Task 6.3: Per-watch diff, snapshot recording, and version label
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 4
**Objective**: Compare each active watch with its stored baseline and record one snapshot when anything moved, carrying the version label (LLD Data Flow; D2, D4). Covers records that are present; absence and catch-up are Task 6.4.

**Steps**:
- [ ] Writer guard (moved here from Task 3.6, where it would have passed vacuously): add an AST test in `tests/test_writer_guard.py` (or a sibling) that every call to `record_cf_snapshot` and `set_cf_watch_state` under `src/amoeba/` sits in a permitted-module set, defined once as a constant and equal to `{process/cf_watch.py}`. Assert equality, so the test fails if the tenant stops calling them. The `watch_cf` effect writes `cf_watches` itself inside `store/inbox.py` and is outside this set
- [ ] For each active watch (checking `host.stop_requested` between watches): `current = tracked_fields(record)`; `previous = store.latest_cf_snapshot(...)`; `changed = changed_keys(previous fields, current)`. Empty → state `ok`, no snapshot. Non-empty → one call to the Task 3.6 combined method with `present`, `fields`, `changed`, `cf_updated_at` taken as written from the record's `updatedAt` (`None` if absent; never parsed), and the label; state `ok`. The feed entry comes from the trigger; the tenant never writes `changes`
- [ ] The label: call `capture_label()` at most once per file read, and only when a snapshot is about to be recorded; store whatever it returns, parsing and comparing nothing. The real callable is wired in Task 7.2 and is `capture_version_label`, which already returns `VERSION_UNAVAILABLE` on failure; add no second copy of that logic. **Task-level reading of "one `cf --version` subprocess per detected change": a read that records nothing starts no subprocess, and an idle tick never does. This reading conflicts with the LLD's "no tick starts a subprocess" (Non-functional Requirements and Data Flow); report the conflict to the PM in Task 8.6 so the LLD can be amended**
- [ ] A watch whose record is absent from the file is not handled until Task 6.4. Until then dispatch leaves such a watch untouched (no state write, no snapshot, no error), with a comment pointing to Task 6.4; `test_cf_watch_snapshots` includes one case asserting an absent record raises nothing and records nothing
- [ ] The tenant never creates, updates, or blocks a node (D2) and does not consult `cf_write` journal entries (D5)
- [ ] Add `tests/process/test_cf_watch_snapshots.py` using the Task 1.3 harness (`real_cf` fixture; success paths use files written by the real `cf`): link → first snapshot with every key in `changed`; `cf set phase` → one snapshot, `changed == ["developmentPhase"]`, `cf_updated_at` equal to the record's `updatedAt`; a write touching only `updatedAt` records nothing; a write touching only `customData` (use `rewrite_projects_file`) records nothing and stores no `customData`; a change to an unlinked CF project records nothing. In each recording case assert the feed gained exactly one `cf_project_changed` with matching `changed`
- [ ] Add `tests/process/test_cf_watch_label.py`: two recordings with a fake `capture_label` whose value changes between them store the two labels; a fake returning `VERSION_UNAVAILABLE` stores exactly that; the fake is called once per recording read and not at all for a read that records nothing; with `subprocess.run` patched to raise, idle ticks and non-recording reads complete without a call, and a recording read still records, labelled `unavailable` when the real callable is used

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass; each new test file stays under about 300 lines
- [ ] Commit, e.g. `feat(process): record Context Forge snapshots from file changes`

**Files to Create**: `tests/process/test_cf_watch_snapshots.py`, `tests/process/test_cf_watch_label.py`
**Files to Modify**: `src/amoeba/process/cf_watch.py`, `tests/test_writer_guard.py`

---

### Task 6.4: Absence, reactivation, multiple writes, and catch-up
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: The remaining per-watch outcomes (LLD Functional Requirements; Errors, "Linked id never present" and "present before, now gone").

**Steps**:
- [ ] Absent with no previous snapshot, or previous `present = false` → state `missing`, no snapshot. Absent with a previous present snapshot → snapshot with `present = false`, `fields = {}`, `changed == ["$present"]`, state `missing`. A record that returns after a vanish diffs against the empty vanished baseline, so every key is changed
- [ ] Inactive watches are not visited. On reactivation (back to `pending`, Task 4.1) the next dispatch diffs against the last snapshot, so everything that moved while inactive becomes one snapshot
- [ ] Add `tests/process/test_cf_watch_absence.py` using the Task 1.3 harness: `cf project rm` → one `present = false` snapshot and one feed entry; restored (re-init with the same file content via `rewrite_projects_file`) → one snapshot with every key changed; a never-present id → `missing`, nothing recorded; an inactive watch records nothing while CF changes, and on reactivation one snapshot covers all of it; two `cf set` calls between scans → one snapshot listing both keys; a new tenant instance against an unchanged store records nothing (restart), and against a file changed meanwhile records exactly one snapshot (catch-up)

**Success Criteria**:
- [ ] Tests pass; file stays under about 300 lines
- [ ] Commit, e.g. `feat(process): record Context Forge disappearance and catch-up`

**Files to Create**: `tests/process/test_cf_watch_absence.py`
**Files to Modify**: `src/amoeba/process/cf_watch.py`

---

### Task 6.5: Bounded failure for recording errors
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 3
**Objective**: A store failure on one watch must not crash-loop the process (LLD Errors, last bullet; 106's bounded-failure rule). Counting, parking, and skipping here; the retry trigger is Task 6.6.

**Steps**:
- [ ] Create `src/amoeba/process/cf_layout.py` defining once the sidecar path `{store_dir}/cf/attempts/{project_id}/{sha256(cf_project_id).hexdigest()}.attempts.json` (D3: the id is never a path component). The tenant and the tests import it; no other module builds the path
- [ ] Around the recording transaction, using 106's `AttemptsSidecar` and durable-write helper (locations from Task 1.1): write or increment the sidecar first. Catch only the store's error base class and `sqlite3.Error`, never a bare `except` or `except Exception`. Below `cf_max_attempts`: `logger.exception` at ERROR, then re-raise. At the limit: `logger.exception`, then swallow, with a comment saying why swallowing is correct (the watch is parked `failed` and the other watches must continue); set the watch `failed` in its own transaction (if that write also fails, `logger.exception` and continue), leave the sidecar, update the cache entry's state, and go on to the next watch
- [ ] Skipping lives here: dispatch skips a `failed` watch (cache state) whose sidecar exists with attempts at or above `cf_max_attempts`, without reading its record. Task 6.6 only adds the retry trigger
- [ ] Sidecar deletion has exactly one owner, this task: delete the sidecar after a successful commit, and also in the empty-diff branch of a dispatch (a crash between commit and delete leaves a sidecar for a watch with nothing left to record). Task 6.6 never deletes a sidecar
- [ ] Add `tests/process/test_cf_watch_failure.py`; inject the failure by wrapping the store's combined record method to raise (as `tests/process/test_inbox_tenant.py` does): attempts 1 and 2 re-raise, log ERROR, and increment the sidecar; at the limit the watch is `failed`, nothing raises, a later scan skips the parked watch while a second watch still records; success after a transient failure removes the sidecar; a sidecar left over for a watch whose diff is now empty (stage it, simulating a crash between commit and delete) is removed on the next dispatch and records nothing new; the path contains no part of the raw CF id (use an id containing `/` and `..`)

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(process): bound Context Forge recording failures`

**Files to Create**: `src/amoeba/process/cf_layout.py`, `tests/process/test_cf_watch_failure.py`
**Files to Modify**: `src/amoeba/process/cf_watch.py`

---

### Task 6.6: Retry parked watches on sidecar removal
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 2
**Objective**: A `failed` watch is retried once its sidecar is deleted (LLD Functional Requirements, store-failure bullet). Skipping while parked is Task 6.5.

**Steps**:
- [ ] Each scan interval the tenant makes one existence check per `failed` watch (none exist in the normal case, so the idle path of Task 6.1 is unchanged). Where it sits: in `tick`, after the interval gate and before the signature comparison, iterate the cached watches (Task 6.1 keeps each one's state) whose state is `failed` and test their sidecar paths from `cf_layout.py`. A missing sidecar sets the cache entry back to `pending` (written to the store with `set_cf_watch_state`) and marks the tenant dirty, so the dispatch that follows in the same tick retries it even though the file's signature has not changed. A sidecar still at or above the limit leaves the watch skipped (Task 6.5). This task deletes nothing; deletion belongs to Task 6.5
- [ ] Add `tests/process/test_cf_watch_retry.py`: deleting the sidecar retries and succeeds once the failure is lifted, ending `ok` with the sidecar gone; with no `failed` watch, an idle scan makes no sidecar check (spy on the existence check); the retried watch passes through `pending` and ends `ok`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): retry parked Context Forge watches on sidecar removal`

**Files to Create**: `tests/process/test_cf_watch_retry.py`
**Files to Modify**: `src/amoeba/process/cf_watch.py`

---

## Section 7: Listings and Wiring

### Task 7.1: Add `inspect cf-watches` and `inspect cf-snapshots`, with tests
**Owner**: Junior AI
**Dependencies**: Task 3.6 (store reads; it does not need the tenant)
**Effort**: 4
**Objective**: Two registry entries (LLD CLI table), committed together with their tests.

**Steps**:
- [ ] Read `cli/inspect_evidence.py` and 106's `cli/inspect_feed.py` for how a sibling module registers listings and how `--json` carries columns beyond the table's (rows may hold extra keys, as the journal listing's `parameters` does)
- [ ] Create `src/amoeba/cli/inspect_cf.py` with `cf_watch_rows` and `cf_snapshot_rows`; register both in `LISTINGS` (project-scoped, `rows=`). `cf-watches` columns: `cf_project_id, active, state, detail, last_snapshot_at`. `cf-snapshots` columns: `observed_at, cf_project_id, present, changed, cf_updated_at, version_label`, a `--cf-project` value option, and `fields` present in the row but not in the table columns so only `--json` shows it
- [ ] `state` is read from the stored watch (the tenant keeps it current); the listing writes nothing. Update the test that pins the listing set
- [ ] Add `tests/cli/test_inspect_cf.py`: stage rows by writing through the store methods (not by running the tenant): `cf-watches` shows each of the six states and `last_snapshot_at` (empty when none); `cf-snapshots` shows history oldest first, filters with `--cf-project`, and `--json` adds `fields` while the table form omits it; table and JSON agree on the shared columns

**Success Criteria**:
- [ ] `amoeba inspect --help` lists both; tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(cli): add inspect cf-watches and cf-snapshots`

**Files to Create**: `src/amoeba/cli/inspect_cf.py`, `tests/cli/test_inspect_cf.py`
**Files to Modify**: `src/amoeba/cli/inspect.py`, the listing-set test

---

### Task 7.2: Wire the tenant into `start`, with tests
**Owner**: Junior AI
**Dependencies**: Task 6.6, Task 7.1 (the process test reads `inspect cf-snapshots`)
**Effort**: 4
**Objective**: Register the third tenant (LLD "Consumes from Other Slices"); prove it runs in the real `amoeba start` and honors `--cf-data-dir`. One commit with its test.

**Steps**:
- [ ] In `cli/lifecycle.py`, add `CFWatchTenant` to the tenant tuple after the tenants 106 registered (comment: a backlog of submissions, including `watch_cf`, drains first). Construct it with `clock=time.monotonic` and `capture_label` bound to `capture_version_label(settings.cf_timeout_seconds)`. If 106 extracted `build_tenants`, extend it instead of editing `start`. Recovery still runs before any tenant ticks (unchanged)
- [ ] Read `tests/cli_harness.py` and 106's `tests/process/test_review_detection_process.py` for how a long-lived `amoeba start` subprocess is launched. Reuse their helper
- [ ] Add `tests/process/test_cf_watch_process.py`: start the process with `--cf-data-dir` pointing at a temp directory holding a copy of `projects_two_projects.json`; submit `create-project` and `watch-cf`; wait on a condition until `inspect cf-snapshots` shows the first snapshot; `kill -9`, restart, and assert nothing new is recorded; change the file while it is down, restart, and assert one new snapshot. Waiting is on a condition with a deadline, never a fixed sleep

**Success Criteria**:
- [ ] `amoeba start` runs all tenants; `tests/test_cli_lifecycle.py` and the new test pass
- [ ] Commit, e.g. `feat(cli): register the Context Forge watch tenant in start`

**Files to Create**: `tests/process/test_cf_watch_process.py`
**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

## Section 8: End-to-End, Docs, Final Validation

### Task 8.1: End-to-end test through the real CLIs
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 4
**Objective**: The LLD Integration Requirement, as subprocesses.

**Steps**:
- [ ] Add `tests/cli/test_cf_watch_end_to_end.py` using the Task 1.3 harness (`real_cf` fails, never skips, when `cf` is missing). Temporary `AMOEBA_STORE_DIR` and the harness's data directory; its helpers create the project and read the id; start the process; `create-project`; start `amoeba feed --follow` as a subprocess collecting stdout
- [ ] Sequence: `submit watch-cf` → follower prints one `cf_project_changed` (`present` true); `cf set phase` → one more with `changed` equal to `["developmentPhase"]`; `kill -9` the process; `cf set slice` while it is down; start it → one more entry; restart with no CF change → nothing new
- [ ] Refusals: a link to an id not in the file shows `missing` in `inspect cf-watches` and prints no feed line; replacing `projects.json` with `{}` shows `unrecognized`, and restoring it returns the watches to `ok` and `missing` with no feed line; `cf project rm` prints `present` false
- [ ] Finally `inspect cf-snapshots --json` agrees with the follower's entries one for one (snapshot ids equal the entries' `subject_id`)

**Success Criteria**:
- [ ] Test passes, with no fixed sleeps
- [ ] Commit, e.g. `test(cli): end-to-end Context Forge watch through real CLIs`

**Files to Create**: `tests/cli/test_cf_watch_end_to_end.py`

---

### Task 8.2: Write `docs/cf-contract.md` and test it against the code
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 3
**Objective**: State what Amoeba depends on in CF, and what it does when that changes (LLD Integration Requirements). Follow `docs/inbox-contract.md` and 106's `feed-contract.md` for frontmatter and style.

**Steps**:
- [ ] Write `docs/cf-contract.md` with: the location rule and that it is copied from CF (and where in the code); the observed `projects.json` shape and its capture date and CF version from Task 1.2 (as a dated observation, not a pinned version); the two facts Amoeba depends on; that every other key is opaque and compared by value; `IGNORED_KEYS` and why; the reserved `$present` marker; the write method CF uses (copy, temp file, rename); the failure table (`unreachable`, `unrecognized`, `missing`, `failed`) and the deliberate whole-file blast radius; what to change if CF moves its storage (a new reader in `amoeba.upstream.context_forge`)
- [ ] Add to `tests/test_contract_docs.py` (106's file): the doc names every `CFWatchState` value, `IGNORED_KEYS` members, and the `$present` marker, each read from the code constants rather than retyped

**Success Criteria**:
- [ ] Doc test passes; every claim in the doc is traceable to a section of the LLD or a code constant
- [ ] Commit, e.g. `docs: add cf-contract and pin it to the code`

**Files to Create**: `docs/cf-contract.md`
**Files to Modify**: `tests/test_contract_docs.py`

---

### Task 8.3: Update the other contracts and `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 2
**Objective**: Additive updates to existing contracts (LLD Technical Scope, last Included bullet).

**Steps**:
- [ ] `feed-contract.md`: the `cf_project_changed` row (node null, subject = snapshot id, payload keys) and the new invariant rule
- [ ] `store-contract.md`: the six new store methods, the two tables, `cf_watch_revision` and why it is memory-only, and the in-process-only status of the two writers
- [ ] `inbox-contract.md`: the `watch_cf` kind, its payload, and its effect
- [ ] `process-contract.md`: the third tenant, the three settings and flags, the idle-tick guarantee (one `stat`, no query, no subprocess, plus one existence check per `failed` watch only while any exists), and the sidecar location
- [ ] `CHANGELOG.md`: one entry for the slice in the file's existing style
- [ ] Extend `tests/test_contract_docs.py` so each updated doc is checked for the new names, read from the code

**Success Criteria**:
- [ ] Doc tests pass
- [ ] Commit, e.g. `docs: document Context Forge watch in the contracts and changelog`

**Files to Modify**: the four contracts, `CHANGELOG.md`, `tests/test_contract_docs.py`

---

### Task 8.4: Pin the boundaries and run the full checks
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 2
**Objective**: Enforce LLD Technical Requirements mechanically.

**Steps**:
- [ ] Extend 106's `tests/test_import_boundaries.py`, parsing source with `ast` and inspecting import nodes (never text search): nothing under `amoeba.store` imports `amoeba.upstream` or `amoeba.process`; `amoeba.upstream` imports nothing from `amoeba.store`
- [ ] Add a test that `IGNORED_KEYS`, the `$present` marker, and the CF location rule each have one definition by `ast`, not text search: each of `IGNORED_KEYS`, the marker constant, and `resolve_cf_data_dir` is bound at module level in exactly one module under `src/`, and a string constant exactly equal to `"CONTEXT_FORGE_DATA_DIR"` (docstrings and comments excluded, substrings not matched) appears in exactly one module. If a legitimate second site is found, fix the duplication rather than loosening the test
- [ ] `tests/test_writer_guard.py` still passes; the record and state methods are not called outside `amoeba.process`
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; check no new source file exceeds about 300 lines (`wc -l`)

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean; file lengths within guidance
- [ ] Commit, e.g. `test: pin Context Forge import and definition boundaries`

**Files to Modify**: `tests/test_import_boundaries.py`

---

### Task 8.5: Run the Verification Walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 2
**Objective**: Compare real output with the LLD walkthrough.

**Steps**:
- [ ] Run steps 1–7 from the LLD in bash against scratch `AMOEBA_STORE_DIR` and `CONTEXT_FORGE_DATA_DIR` (never the real CF data), using a background job or second terminal for the follower
- [ ] For each step compare with the stated expectation. Write each difference (command, expected, actual) into a list in your final message to the PM. Do not edit the LLD. If a step cannot run, say which and why

**Success Criteria**:
- [ ] All seven steps run; every difference is reported (an empty list is stated as such)
- [ ] No commit needed unless the run exposes a defect; a fix is its own commit with a test

---

### Task 8.6: Report task-level decisions to the PM
**Owner**: Junior AI
**Dependencies**: Task 8.5
**Effort**: 1
**Objective**: Make sure choices the LLD left open reach the PM.

**Steps**:
- [ ] In the final message list, with the code location of each: the `cf_watch_revision` counter (Task 4.3); the `--cf-max-attempts` flag (Task 5.1); the label captured once per recording read rather than per file-signature change (Task 6.3); the per-scan existence check of `failed` watches' sidecars, an exception to the one-`stat` idle guarantee that applies only while a watch is `failed` (Task 6.6); the migration number actually used and the CF version the fixture was captured on (Tasks 1.1, 1.2); the conflict between per-recording label capture and the LLD's \"no tick starts a subprocess\", with a request to amend the LLD (Task 6.3); the new `cf_layout.py` module, absent from the LLD's component list (Task 6.5); every place the task wording on settings, flags, or the idle-check differs from the LLD
- [ ] Say whether a worktree-overlay fixture could be captured (Task 1.2)

**Success Criteria**:
- [ ] The list is in the final message; no commit needed

---

### Task 8.7: Trace requirements to tests
**Owner**: Junior AI
**Dependencies**: Task 8.6
**Effort**: 2
**Objective**: Every LLD Functional and Technical Requirement has a passing test (LLD Success Criteria).

**Steps**:
- [ ] Confirm each requirement is covered by the named test; run those tests by name. Where the named test lacks the assertion, add it there
  - First snapshot with every key; `cf set phase` gives one snapshot and entry; `updatedAt`-only and `customData`-only writes record nothing (the latter also tested at diff level in `test_cf_diff`); unlinked change records nothing: `test_cf_watch_snapshots`
  - Remove and restore; never-present id → `missing`; multiple writes between scans: `test_cf_watch_absence`
  - Down-time catch-up and restart-with-no-change: `test_cf_watch_absence`, `test_cf_watch_process`, end-to-end
  - `unreachable` and the four `unrecognized` shapes, re-read only on signature change: `test_cf_watch_file_states`
  - Deactivate and reactivate: `test_cf_watch_absence`, `test_watch_cf`
  - Bounded failure, parking, and sidecar retry: `test_cf_watch_failure`, `test_cf_watch_retry`
  - Idle tick is one `stat`, no read, no query, no subprocess: `test_cf_watch_idle`, `test_cf_watch_label`
  - Label provenance and `unavailable`: `test_cf_watch_label`
  - Diff rule and `IGNORED_KEYS` recursion: `test_cf_diff`
  - Reader on real fixture; two-fact contract: `test_cf_projects_file`
  - 7 → 8 upgrade: `test_migration_008`
  - Feed invariant with new step and rule: `test_feed_invariant`
  - Enums, SQL, and constants defined once; store imports nothing upstream: `test_import_boundaries`
  - `cf-contract.md` complete: `test_contract_docs`
  - Real fixtures and real-`cf`-written files in success paths: confirm by reading the fixture setup
- [ ] Report any requirement for which no test could be named, with the one you added

**Success Criteria**:
- [ ] Each bullet confirmed or fixed; the suite is green
- [ ] Working tree committed on the slice branch; no merge performed
- [ ] Commit any additions, e.g. `test: close slice 108 requirement coverage gaps`

---
