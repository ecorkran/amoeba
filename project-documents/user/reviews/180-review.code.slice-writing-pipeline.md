---
docType: review
layer: project
reviewType: code
slice: slice-writing-pipeline
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/180-slice.slice-writing-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 99bc85a0be41b8c4b6a00e2a48ac7c315c7aefbf
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 23
diffTruncated: false
effort: xhigh
turns: 24
promptTokens: 1377220
cachedTokens: 1153223
cacheWriteTokens: 223979
completionTokens: 66352
durationSeconds: 312.1
costUsd: 0.410056
costBasis: provider
runId: run-20261104-p6-637a3f21
squadronVersion: 0.24.22
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "A launcher that exits inside the grace leaves its descendants running"
    location: "tests/live_harness.py:136-140"
  - id: F002
    severity: concern
    category: security-hygiene
    summary: "The write step's limits are prompt text only"
    location: "src/amoeba/runner/request_run/slice_writing.yaml:22-48"
  - id: F003
    severity: concern
    category: documentation-drift
    summary: "Docstring says the wrong conftest reads the live settings"
    location: "tests/live_settings.py:3-4"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Same `git diff-tree` call written twice"
    location: "tests/live/request_run/harness.py:68-71"
  - id: F005
    severity: note
    category: test-debt
    summary: "The initiatives check asserts almost nothing"
    location: "tests/live/request_run/harness.py:194-195"
  - id: F006
    severity: note
    category: test-debt
    summary: "Path glob guard is looser than the commit's pathspec"
    location: "tests/live/request_run/harness.py:189"
  - id: F007
    severity: note
    category: error-handling-observability
    summary: "Negative exit code reads as sq's own exit"
    location: "tests/live/request_run/harness.py:163-164"
  - id: F008
    severity: note
    category: test-debt
    summary: "Parser test repeats the parser's logic, and one test name overstates"
    location: "tests/runner/request_run/test_read_reply.py:60-64"
  - id: F009
    severity: note
    category: documentation-drift
    summary: "Public reply types have no docstrings"
    location: "src/amoeba/runner/request_run/reply.py:24"
  - id: F010
    severity: note
    category: error-handling-observability
    summary: "`uv build` and `-I` import failures lose their output"
    location: "tests/runner/request_run/test_wheel_contents.py:31-36"
---

# Review: code — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] A launcher that exits inside the grace leaves its descendants running

`watch_run` kills the launcher's session in `finally` only when the launcher is still alive (`process.poll() is None`). If the launcher exits on its own inside `exit_grace_seconds`, nothing kills the rest of its session. `contained_popen`'s atexit hook (tests/process_containment.py:71-80) kills only the launcher pid, not its process group, so descendants of a clean launcher exit can survive pytest. The docstring (lines 99-103) says the session is killed "so no child keeps spending". The request tier spends real money under `--max-cost`. No test covers a descendant: `test_launcher_that_exits_within_the_grace_reports_its_own_exit` launches a process with no children. The `reap_orphans` backstop acts only after 300 s, at a later session start, and only when the command line names the pytest temp root. Fix: send SIGKILL to the group in `finally` unconditionally, tolerating `ProcessLookupError` when the group is already gone. Add a test where the launcher spawns a child that outlives it.

### [CONCERN] The write step's limits are prompt text only

The write step declares no tool restriction (`test_pipeline_yaml.py` asserts that absence on purpose). Its limits are the prompt alone: read-only git, two files, no `cf set`, no push. The commit step's `paths` (lines 95-100) constrain only the commit it makes. Nothing mechanical stops a `git push`, a commit the model makes itself, or an edit to a third file that is left uncommitted. The live harness checks local strays after each run (clean status, at most one commit, commit touches only the globs). The scratch repos have no remote, so a push would never show. The `need.md` text comes from another project's slice, so it is not fully trusted input. If the broad tool set is deliberate, record the prompt as the only control. Add a live case against a bare remote that asserts nothing was pushed, and a runner check (slice 184) that the tree is clean apart from the commit. If Squadron supports a tool allow-list, use it.

### [CONCERN] Docstring says the wrong conftest reads the live settings

The docstring says `tests/live/conftest.py` calls `read_live_settings` at collection. This diff moved that call to `tests/live/answering/conftest.py:22`, and `tests/live/conftest.py` no longer reads settings. The docstring now contradicts the code. Name the answering sub-tier conftest.

### [NOTE] Same `git diff-tree` call written twice

`RequestRun.files_changed_by` and `_check_every_run` (line 184) both run `git diff-tree --no-commit-id --name-only -r <commit>` and split the output. `_check_every_run` runs before `RequestRun` exists, so it cannot call the method. Extract a module-level `_files_changed_by(repo, commit)` and use it in both places.

### [NOTE] The initiatives check asserts almost nothing

`initiatives` comes from `cf list initiatives --json -a`, and the only assertion is that the result is a list. The function's docstring says it checks what every run guarantees, so a reader expects a plan check. The real check is only that cf exits 0. To check the plan model, pass the output to `parse_initiatives`, as `probes.py` does. Otherwise drop the line.

### [NOTE] Path glob guard is looser than the commit's pathspec

`fnmatch.fnmatchcase` lets `*` cross `/`, and the commit step's globs do not. A commit touching a deeper file under the same prefix and suffix passes the "outside the globs" check. Match path segments one at a time, and add a test with a nested path that must be refused.

### [NOTE] Negative exit code reads as sq's own exit

When the launcher is killed after the grace, `exit_code` is negative and the assertion reads `sq exited -9`. That looks like sq's own exit, not a kill by the wait. `PipelineRun` documents the negative case, so name it in the message.

### [NOTE] Parser test repeats the parser's logic, and one test name overstates

Line 64 checks `result.index == int(str(index).strip())`, which repeats the parser's own normalization, so a bug shared by both would pass. Use explicit expected values in the parametrize list. Line 133, `test_malformed_replies_name_a_cause`, asserts only the MALFORMED kind. The `_problem` helper checks only that the detail is non-empty, not that it names a cause. Rename the test or assert a cause phrase per case.

### [NOTE] Public reply types have no docstrings

`ProblemKind` (line 24), `NewSlice` (37), `AlreadyMet` (42) and `ReplyProblem` (47) are public and undocumented. `ReplyKind` and `RequestInput` have docstrings. `ReplyProblem` is the value callers branch on, so it needs one most.

### [NOTE] `uv build` and `-I` import failures lose their output

Both `subprocess.run` calls (lines 31-36 and 47-52) use `check=True` with `capture_output=True`. On failure, `CalledProcessError` carries the command and exit code but not the captured output. Use `check=False` and `assert completed.returncode == 0, completed.stdout + completed.stderr`, as `tests/live/request_run/test_validate.py` does.

### Run Digest

- Response length: 7639 chars
- Response is newline-free: no
- Tool calls made: 23
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 24
- Tokens — prompt / cached / cache write / completion / reasoning: 1377220 / 1153223 / 223979 / 66352 / not computed
- Duration: 312.1 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
