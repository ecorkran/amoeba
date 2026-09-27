---
docType: review
layer: project
reviewType: tasks
slice: findings-verdicts-and-provenance
targetKind: slice
rulesSource: project
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: e406ad9cc0489c1e3177ba9353eec79894a6dac1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
findings:
  - id: F001
    severity: fail
    category: test-data
    summary: "The captured 102 review fixtures Task 1.1 depends on do not exist in the repo"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md:350-351"
  - id: F002
    severity: concern
    category: task-scope
    summary: "Task 7.1 omits `cli/main.py`, where inspect parser options are actually wired"
    location: "src/amoeba/cli/main.py:142-171"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "No task names a round-trip test for `score`, `criteria`, and the nullable SQ-927 fields"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md"
  - id: F004
    severity: pass
    category: coverage
    summary: "Every slice success criterion traces to a task across the two files"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md"
  - id: F005
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pairing, and commit distribution are correct"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md"
  - id: F006
    severity: pass
    category: accuracy
    summary: "The tasks' claims about existing code all verify against the repo"
    location: "src/amoeba/cli/submit.py:62"
  - id: F007
    severity: note
    category: load-testing
    summary: "No load test added — correctly, since the slice restates no NFR, and CI already gates on `tests/load`"
    location: ".github/workflows/ci.yml:54"
  - id: F008
    severity: note
    category: test-data
    summary: "Captured rounds may predate `verdictSource` in frontmatter — worth pinning when the files are restored"
    location: "unverified"
---

# Review: tasks — slice 104

**Verdict:** FAIL
**Model:** z-ai/glm-5.3-flash

## Findings

### [FAIL] The captured 102 review fixtures Task 1.1 depends on do not exist in the repo

The slice's Technical Requirements table names the four captured files ("all tracked in git"): `archive/102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md`, `…part-2.20260921T112635.md`, `archive/…part-1.md`, and `archive/…part-2.md` under `project-documents/user/reviews/`. I verified the ground truth:

- `project-documents/user/` contains only `architecture/`, `notes/`, `project-guides/`, `slices/`, `tasks/` — there is no `reviews/` directory at all.
- A repo-wide search for `102-review.tasks.resident-process-and-recovery` finds matches only inside the slice document itself (and a prior review note recorded inside `tests/fixtures/sq_reviews/stdout-slice-104-concerns-glmflash.json`, which independently documents the same absence).
- `.gitmodules` is empty, so the directory is not a submodule. I cannot inspect git history with the tools available, so the files may exist in a prior commit and need restoring — that is a PM action either way.

Consequence: Task 1.1's step 3 ("If any file is missing or differs, stop and ask the PM") fires on the very first implementation task, and Tasks 1.3 (captured-rounds test with pinned 9/7 counts), 5.2 (real rounds through the store), 8.1 ("every finding traceable to a fixture"), and 8.2/8.4 all inherit the gap. To its credit, the breakdown fails loudly instead of fabricating fixtures — but a plan whose first task can never complete as written is not approvable. The PM must either restore/commit the four files or amend the design before implementation starts.

### [CONCERN] Task 7.1 omits `cli/main.py`, where inspect parser options are actually wired

Task 7.1 adds `value_options` to `Listing` and says `_add_inspect_parser` adds them, but its "Files to Modify" lists only `src/amoeba/cli/inspect.py`. The parser construction lives in `cli/main.py` (`_add_inspect_parser` at line 142; the per-listing option loop at line 171 iterates `listing.choice_options`), which is why the slice design itself says "`store.py`, `cli/inspect.py`, and `cli/main.py` are near their line budgets" — main.py is expected to change. A junior AI following the task literally will modify `inspect.py`, discover the wiring in `main.py`, and have to improvise. Add `src/amoeba/cli/main.py` to Task 7.1's modified-files list.

### [CONCERN] No task names a round-trip test for `score`, `criteria`, and the nullable SQ-927 fields

The design explicitly justifies storing `score` and `criteria` ("stored now because review files carry them. Slice 109 adds what uses them") plus `requested_model` and `diff_truncated` ("their columns hold null until Squadron ships them"). Storage tasks exist (2.1 models, 3.1 schema, 3.2 mapping), but the test tasks never name these fields: Task 4.2 tests checks/findings/observations/retry, Task 4.4 tests ordering/filtering/per-key summary, and the e2e listing columns (Task 7.2) don't include `score`. As written, a verdict's `score`/`criteria`/`tool_calls_made`/`sq_run_id` could silently fail to persist and nothing would catch it — and Task 3.2's mapping raises on unknown enums but has no stated test of its own beyond the migration test. Add one line to Task 4.2 (or 4.4) asserting a `VerdictInput` with `score`, `criteria`, `tool_calls_made`, `sq_run_id`, `requested_model`, and `diff_truncated=None` reads back identical.

### [PASS] Every slice success criterion traces to a task across the two files

Cross-referencing the full matrix (Section 1–5 file plus `104-tasks.findings-verdicts-and-provenance-2.md`): migration 005 → 3.1/3.3; matching rule → 1.2/1.3; trust label and word lists → 2.1/2.2; `record_verdict` and the four read methods → 4.1–4.4; `finding_changes` including skip-on-failure → 5.1/5.2; `verdict` inbox kind with quarantine and id-equals-submission-id → 6.1/6.2; submit flag rule → 6.3/6.4; `value_options` and both listings with the re-pinned registry test → 7.1–7.3; demo script, writer-guard widening, e2e CLI test → 8.1/8.2; `docs/evidence-contract.md`, contract drops/updates, CHANGELOG → 8.3; walkthrough and final validation → 8.4. Each functional requirement maps to named test steps, including the subtle ones (replay no-op, unrecognized derivation rejected at envelope validation, unknown `--verdict` exits non-OK, listings work stopped and running). No scope creep: the frontmatter helper is explicitly fenced as "not the slice 108 parser", the store is kept pydantic-free, and nothing reaches into slices 105/108/109. No task is too large; Task 7.1 (effort 1) is small but is a distinct plumbing change with its own regression criterion, which is defensible.

### [PASS] Sequencing, test-with pairing, and commit distribution are correct

The dependency chain 1.1→1.2→1.3→2.1→2.2→3.1→3.2→3.3→4.1→4.2→4.3→4.4→5.1→5.2→6.1→6.2→6.3→6.4→7.1→7.2→7.3→8.1→8.2→8.3→8.4 is acyclic and respects every data dependency (fixtures before the rule, models before SQL/mapping, checks/insert helpers before the inbox effect reuses them — the cross-file handoff from 5.2 to 6.1 is documented in the second file's context summary). Every implementation task is immediately followed by its test task (test-with), with Task 1.1 correctly placing test infrastructure first. Commits sit at 14 checkpoints across the sequence, each after a green test run — none batched at the end. The file split honors the ~450-line guide rule, and correctly no task contains a merge step (Task 8.4 ends at commit on the slice branch, per the Phase 5 rule that merging belongs to Phase 7).

### [PASS] The tasks' claims about existing code all verify against the repo

Every seam the tasks cite exists where claimed: `_takes_object` (`cli/submit.py:62`), `KIND_PAYLOAD_MODELS` (`inbox/envelope.py:88`), `KIND_EFFECTS` (`store/inbox.py:266`), `SubmissionKind` (`store/inbox_models.py:21`), `StoreError`/`NodeNotFoundError` side by side (`store/models.py:162/186`), `EXPECTED_SCHEMA_VERSION = 4` (`store/migrations.py:36`), `LISTINGS` (`cli/inspect.py:149`), `PERMITTED_SCRIPTS` with the pinned-set assertion (`tests/test_writer_guard.py:63,288`), the pin to be replaced (`tests/test_cli_inspect.py:380` including the "findings not registered" assertion at lines 375–395), and the pattern files `tests/store/test_migration_004.py` and `tests/cli/test_inbox_end_to_end.py`. The two existing JSON captures Task 1.1 references are in `tests/fixtures/sq_reviews/`. This gives the junior AI reliable anchors.

### [NOTE] No load test added — correctly, since the slice restates no NFR, and CI already gates on `tests/load`

The slice design states no non-functional requirement requiring a load test, so the breakdown rightly adds none; the existing `tests/load/` suite remains, `.github/workflows/ci.yml:54` already runs `uv run pytest tests/load` (CI gating is not implicit), and Task 8.4 re-runs it as final validation. No action needed.

### [NOTE] Captured rounds may predate `verdictSource` in frontmatter — worth pinning when the files are restored

The captured files are dated 20260921 while the design records `verdictSource` being observed in frontmatter on 20260926, so the restored files may lack `derivation` entirely — their standing would then be `unattested` (still comparable per `COMPARABLE_STANDINGS`, so the tests remain valid). Because the files are absent I cannot verify their frontmatter. Tasks 1.1 and 1.3 only pin `verdict` and the reviewed commit, which keeps them consistent either way; if the PM restores the files, the fixture guard should also record what the `derivation` situation actually is so Task 5.2's `VerdictInput` construction (`not_reported` vs. a stated value) is deliberate rather than guessed.

### Run Digest

- Response length: 9087 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 2
- Stop reason: stop
- Reasoning characters: 32415
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Resolved 20260926 against `e406ad9`.

- **F001 (fail): premise wrong, no change.** All four captured files are tracked in git: `git ls-files project-documents/user/reviews/archive` lists `102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md`, `…part-1.md`, `…part-2.20260921T112635.md`, and `…part-2.md`. The reviewer's tools could not see `project-documents/user/reviews/` at all (it reported the directory missing, even though this review is written there). The slice 104 design review hit the same blind spot. This is a Squadron tool-visibility gap, not a gap in the plan. Task 1.1's stop-if-missing step stays as written.
- **F002 (concern): accepted.** Task 7.1 now names `src/amoeba/cli/main.py` (`_add_inspect_parser`, the `choice_options` loop) as modified, with a success criterion that `main.py` grows by only the new option loop.
- **F003 (concern): accepted.** Task 4.2 gains a round-trip test: a `VerdictInput` with every optional field set reads back equal, and one with each set to `None` reads back `None`. That covers `score`, `criteria`, `tool_calls_made`, `sq_run_id`, `requested_model`, and `diff_truncated`.
- **F008 (note): settled.** Both part-1 captured files carry `verdictSource: stated`. Task 1.3's fixture guard now pins it, so Task 5.2 builds those rounds with `derivation=stated` from the file.
- **F007 (note):** no action.
