---
docType: reference
purpose: Provenance of the real Squadron recordings the pause-handling tests replay
dateCreated: 20261110
dateUpdated: 20261110
---

# Squadron recordings

Every file is **byte-real `sq` output**, captured 20261110 with `sq --version` =
`squadron 0.24.25` (a dated observation, not a pin). Nothing is hand-written or
edited. The tests that read them are `tests/upstream/squadron/test_squadron_fixtures.py`,
`tests/upstream/test_run_file.py` and the fake-`sq` tests that replay them.

## `sq runs wait <id> --timeout 0 --json`

Each is stdout of one call (the exit code is in the second column).

| File | Exit | Case |
| --- | --- | --- |
| `wait_paused_agent_question.json` | 3 | `agent_question` pause from `tests/live/pause/asks_question.yaml` (run in a throwaway Context Forge project with the `haiku-xhigh` alias) |
| `wait_paused_interactive_checkpoint.json` | 3 | A pause of another checkpoint kind: `interactive_checkpoint`, from a real local `slice` run |
| `wait_running.json` | 4 | A run still running (`outcome` `timed_out`, `status` `running`), taken while a real run was in flight |
| `wait_completed.json` | 0 | A completed run (a one-step dispatch that replies `done`) |

## Run file

`run_file_schema5.json` is the real `~/.config/squadron/runs/<run_id>.json` of the
`agent_question` run above (`schema_version` 5, `params`, `execution_mode` `sdk`).
It is unedited, so it holds this machine's path to the pipeline file in
`pipeline_path`. Its `paused_at` is written `…Z`; `sq runs wait --json` prints the
same instant as `…+00:00` (slice 223, D1: only the `wait` form is ever stored).

`run_file_schema5.json` has `working_directory` (`sq` writes it from 0.24.24 on, slice
228 D10; this run was made on 0.24.25), and its value is that test run's throwaway
directory. `run_file_schema5_no_working_directory.json` is the real run file of
`run-20261105-effort-walkthrough-none-e65efbbe` (the `prompt-only` demo run in the
listing recording below), copied unedited from before 0.24.24: schema 5 with no such
key. The two pin both shapes.

## The run lock (slice 223, task 6.0a)

Captured 20261110 with `sq` 0.24.25 on a real `agent_question` run
(`tests/live/pause/asks_question.yaml`, run id `amoeba-fixture-lock-3`): one
`sq run --resume <id> --instructions ...` was started and left running, then a second
`sq run --resume <id> --instructions "second resume"` was started on the same run.

| File | What it is |
| --- | --- |
| `resume_lock_before.json` | `sq runs wait --timeout 0 --json` before either resume: `paused`, exit 3 |
| `resume_lock_during.json` | the same call 1.2 s after the first resume started: `timed_out` / `running`, exit 4 |
| `resume_lock_refused.stdout.txt` | stdout of the **second** resume |
| `resume_lock_refused.stderr.txt` | stderr of the second resume: **empty** |
| `resume_lock_after.json` | the same call right after the second resume exited: still `running` (the first holds it), exit 4 |

Observed: the second resume **exits 1** (not 2), prints
`Error: Run '<id>' is still running under pid <pid> on <host>.` on **stdout**, and
leaves stderr empty. The run was `running` under the first resume, not at the pause.
So a refusal detail read from stderr alone is empty; `resume` reads stderr and falls
back to stdout. A held lock is judged by "child exited, run still at this pause" and
never by the exit code (D8); when the poll after the refusal already shows the
holder's `running`, the loser reports `resumed` too (the run is running).

## `sq runs list --json` (slice 224, tasks 3.1 and 5.1)

Captured 20261111 with `sq` 0.24.26 on the PM's machine (a dated observation, not a
pin), called with no `--all` (a 224 recording; see below). `runs_list/list_mixed.json` is **a selection of eleven
elements of that real listing, each element unedited** (the array holds only the chosen
ones, in the listing's order, re-indented). The full listing had 98 runs. The cases:

| Run id | Case |
| --- | --- |
| `run-20261111-p6-fe470d63` | running, with a directory |
| `demo-push-3` | newer paused `agent_question`, with a directory |
| `demo-pause-1` | older paused `agent_question`, same directory (made by 223's live fixtures) |
| `amoeba-20261110T150234Z-8bf24f09cfbb` | paused `agent_question` in another directory (a throwaway test member) |
| `run-20261105-p6-7dc230a3` | paused `awaits_human`, `working_directory` `null` (run before `sq` 0.24.24) |
| `run-20261015-p5-8a59ee89` | paused `other`, `null` directory |
| `run-20261004-p6-8bc5e634` | paused `interactive_checkpoint` with `step`, `verdict` and `review_file` (the extra checkpoint fields), `null` directory |
| `run-20261110-p6-9ea18232` | failed, with a directory |
| `run-20261105-effort-compact-acbbe8e8` | failed, `null` directory |
| `run-20261105-effort-walkthrough-none-e65efbbe` | running, `null` directory |
| `run-20261106-tasks-plan-711d0fe6` | completed, `null` directory (the default listing still includes some) |

Every listed run is real; none is hand-written or edited. No paused run of another
checkpoint kind **with** a directory exists on the machine and none could be made
cheaply (`checkpoint: always` on a dispatch step does not pause), so that case is
built in test code from a real element by the tests that need it.

`runs_list/list_stderr.txt` is the real stderr of the same call: one warning that 13
runs reference unavailable pipelines. `--json` stdout is unaffected by it.

**Was `--all` needed?** Not for 224, which only acted on running and paused runs: the
same machine listed 189 runs with `--all` and 98 without, and all 32 paused runs were
in the default listing. Slice 228 (D4) calls `sq runs list --json --all`, because
`status` now closes questions whose run is absent from the listing, and an absent run
must mean "unknown to `sq`", not "a completed run the default listing left out" (checked
on `sq` 0.24.27, 20261112: the default listing held 8 of 100 completed runs, `--all`
all of them). The recording above is a selection of the default listing, so the fake
`sq` prints it for `--all` and drops its `completed` runs without `--all`, as the real
`sq` does. The warning's unavailable pipelines do not hide runs: the
paused runs it concerns are in the stdout JSON (the null-directory ones above).
