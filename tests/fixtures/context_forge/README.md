Real `cf get --json` output, recorded by running the command (not hand-written).
Recorded with `cf --version` 0.19.26 on 20261109.

| File | Where it was run | Stream |
|---|---|---|
| `default_worktree.json` | the default worktree of the amoeba project | stdout, exit 0 |
| `non_default_worktree.json` | a throwaway `git worktree add` checkout, registered with `cf worktree init --name fixture-wt --range 800-899 -o` (removed afterwards) | stdout, exit 0 |
| `subdirectory.json` | `src/amoeba/answering` inside the default worktree | stdout, exit 0 |
| `outside_any_project.json` | `/tmp`: the `PROJECT_NOT_FOUND` error document | **stderr**, exit 1 |

The first three share one project `id`; the non-default worktree differs in
`projectPath` and `worktree`. Used by `tests/cf_fixtures.py` and the `project_of`,
member-resolution and `set_up` tests. To refresh, repeat the captures above and
update the version and date here.
