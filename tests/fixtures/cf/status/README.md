# Captured `cf status --json` and `cf config get --json` output

Real output of Context Forge (`cf` 0.19.19, a dated observation, not a pin), captured 20261026
for slice 128 (D1). Byte-for-byte as printed on stdout; nothing is edited.

They were captured from a scratch project (`cf init --lite`) in a temporary directory, run under a
throwaway `HOME` so the real CF data directory was never touched. The scratch project, its worktree
and its data were deleted afterwards. `workflow.review_enabled` and `workflow.decision_gate_enabled`
were `true`. The project's one slice is `900-slice.alpha`, and the paths and project name in the files
are the scratch ones.

## `status/`

| File | `activeSlice.status` | `gateInfo.reviewType` | How the state was reached |
| --- | --- | --- | --- |
| `no_active_slice.json` | `no-active-slice` | | A project with no slice set |
| `needs_design.json` | `needs-design` | | `cf set fileSlice 900-slice.alpha`, no design file |
| `pending_decision.json` | `pending-decision` | | Design holding a `Status: pending-pm` line (carries `pendingDecisions`) |
| `pending_review_slice.json` | `pending-review` | `slice` | Design, no slice review |
| `review_failed_slice.json` | `review-failed` | `slice` | Slice review with `verdict: FAIL` |
| `gate_exempt_review_none.json` | `needs-tasks` | | Design with `review: none`, no review: `gateExempt: review-none` |
| `needs_tasks.json` | `needs-tasks` | | Slice review `verdict: PASS`, no task file |
| `pending_review_tasks.json` | `pending-review` | `tasks` | Task file, nothing done, no tasks review |
| `review_failed_tasks.json` | `review-failed` | `tasks` | Tasks review `verdict: FAIL` |
| `in_implementation_no_task_done.json` | `in-implementation` | | Tasks review `PASS`, nothing done yet |
| `in_implementation.json` | `in-implementation` | | One of three tasks done: no gate at partial progress |
| `pending_review_code.json` | `pending-review` | `code` | All three tasks done, no code review |
| `review_failed_code.json` | `review-failed` | `code` | Code review `verdict: FAIL` |
| `complete.json` | `complete` | | Code review `verdict: PASS` |
| `worktree.json` | `complete` | | `cf status --json --worktree <worktree id>` for a worktree registered with `cf worktree init`; carries `worktree` and `resolutionSource: worktree` |

Review files were `reviews/900-review.<slice|tasks|code>.alpha.md` with `verdict` frontmatter. The
`--worktree` option takes the worktree's id (`wt_...`) as well as its name.

## `config/`

`cf config get <key> --json` run in the scratch project: `git.integration_branch` and
`workflow.review_gate_effective_date`, each empty (`source: default`) and set.
