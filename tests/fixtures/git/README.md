# Captured `git status` output

Real output of `git --no-optional-locks status --porcelain=v2 --branch --untracked-files=normal`,
captured 20261026 with git 2.50.1 (Apple Git-155) in throwaway repositories built by
`tests/runner/git_repo.py`. One file per case: `status_<case>.txt`.

Cases: clean on `main`; a modified file; an untracked file; a staged file; a renamed file
(entry type `2`: the new path, a TAB, then the old path); an unmerged file from a real
conflicting merge (entry type `u`); a detached HEAD (`branch.head (detached)`); a path with a space.

The `branch.oid` values are those of the throwaway repositories, so tests compare the head
to the value in the file, never to a constant.
