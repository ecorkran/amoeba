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
