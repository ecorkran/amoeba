---
docType: review
layer: project
reviewType: code
slice: pipeline-supervisor
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/132-slice.pipeline-supervisor.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261030
dateUpdated: 20261030
reviewedSha: 1695062e30244b72887c7705a1a3019759082791
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: true
turns: 2
promptTokens: 543100
cachedTokens: 16608
cacheWriteTokens: 526488
completionTokens: 5949
durationSeconds: 49.5
costUsd: 2.281486
costBasis: provider
squadronVersion: 0.24.9
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "Routing leftovers remain in the store and inspection layers"
    location: "src/amoeba/store/journal.py:300"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Auto-resume candidates are read every tick before the resume is ready"
    location: "src/amoeba/runner/dispatch/candidates.py:50"
  - id: F003
    severity: concern
    category: documentation-drift
    summary: "Stale docs and comments after the step and routing removal"
    location: "src/amoeba/runner/dispatch/planner.py:18"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "Silent empty-string fallback for the blocked listing's `reason`"
    location: "src/amoeba/inspection/core.py:70"
  - id: F005
    severity: note
    category: test-debt
    summary: "Weak or odd test assertions"
    location: "tests/contract/test_runner_report_completion.py:78"
  - id: F006
    severity: note
    category: correctness
    summary: "Resume counting also counts skipped resumes"
    location: "src/amoeba/runner/supervise.py:127"
  - id: F007
    severity: note
    category: type-contract-debt
    summary: "`ProjectSettings.params` default is a mutable `{}`"
    location: "src/amoeba/runner/project_config.py:33"
---

# Review: code — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5
**Diff:** truncated: 512000 of 1101777 characters reached the model

## Findings

### [CONCERN] Routing leftovers remain in the store and inspection layers

Routing is gone from the Runner (`routing/`, `gates/`, `--routing-table` and the `routing-decisions` listing are all deleted). A grep of `src/` still finds the following, with no caller left in the Runner:
- `Store.unrouted_outcomes`
- `record_routing_decision` and `routing_table_version` (in `store/routing_decisions.py`)
- the `awaits_routing` column, index and model field
- the `awaits_routing` column in the `inspection/__init__.py` and `inspection/core.py` journal listings

Some of this is schema history that must stay, but the Python API and the models should either be removed or marked as retained deliberately. The same goes for the `drive_until_step` column. `intent/merge.py` now writes `drive_until_step=None` unconditionally.

### [CONCERN] Auto-resume candidates are read every tick before the resume is ready

`launch_candidates` treats every `AUTO_RESUME` slice as a candidate. `CheckStage.check_dispatch` then runs `git status` and `cf config get` for each one. `DispatchPlanner._auto_resume` discards the result with `resume_ready(...)` when a `usage_limit` pause has not reached `resets_at`. A slice waiting hours for a limit reset therefore costs two subprocess calls, and budget, on every tick. The candidate set should skip a resume that is not yet ready. `resume_ready` is pure, so it can be applied there.

### [CONCERN] Stale docs and comments after the step and routing removal

- The planner docstring still says "Within a free checkout the steps go by `(initiative index, slice index, step rank)`". The sort key is now `(initiative, slice)`.
- The `record_runner_report` docstring (`store/runner_report.py:56`) still says the resolution "marks the entry as awaiting routing".
- `decide.py` still describes `ready_unbusy` as "kept for slice 125 to narrow".
- Several planner and continuation docstrings still say "current pipeline step" where the node is now a slice.

### [CONCERN] Silent empty-string fallback for the blocked listing's `reason`

`payload.get("reason") or payload.get("fault_kind") or ""` yields an empty string when the escalation has neither key, or has no escalation message at all. That hides the case "blocked with no recorded reason" from an operator. `CLAUDE.md` says never to use silent fallback values. Use an obviously-placeholder value, or make the absence visible.

### [NOTE] Weak or odd test assertions

- The last assertion of `test_without_the_option_the_node_status_is_untouched` checks the project id, which has nothing to do with the behaviour under test. It needs a `# type: ignore[union-attr]` under strict pyright, and it is the only reason `PROJECT` is imported.
- `tests/runner/dispatch/test_params.py` keeps an unused `PARAMS_FILE` constant. Its `"merge"` string scan still excludes `steps.py`, which no longer exists.
- The `"merge"` scan is brittle. It matches any string constant equal to `"merge"` anywhere under `runner/`.

### [NOTE] Resume counting also counts skipped resumes

`resume_count` counts trailing entries whose `resume_cause` is `transient`. `journal_continuation` also stamps `PARAM_RESUME_CAUSE` on the observation entry written when a resume is skipped because the run had already moved on (`Continuation` is `None`). If that run then stops again at the same step, the skipped resume is counted against `auto_resume_limit`. This errs toward blocking early, which is safe, but it probably isn't intended. Either stamp the cause only on real resumes or document the behaviour.

### [NOTE] `ProjectSettings.params` default is a mutable `{}`

`params: dict[str, StrictStr] = {}` on a frozen model leaves the dict itself mutable, and it is shared through `PROJECT_DEFAULTS`. Pydantic copies defaults per instance, so this is not a bug today. A `Mapping` type or `Field(default_factory=dict)` would be more explicit. `_semantic_problems` also checks `pipeline` with `.strip()` but stores the unstripped value.

### Run Digest

- Response length: 4929 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 543100 / 16608 / 526488 / 5949 / not computed
- Duration: 49.5 s
- Cost: $2.28 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution (20261030)

- **F001** Declined. Slice 132 keeps the store's routing tables, API, `awaits_routing` and `drive_until_step` in 100's contract, unwritten by the Runner (design non-goal, D9). The docs say so.
- **F002** Fixed. `launch_candidates` takes `now` and drops an `AUTO_RESUME` slice whose `usage_limit` has not reset; tests added.
- **F003** Fixed. Planner, build_view, decide and resolutions docstrings now say slice and `(initiative, slice)`; `ready_unbusy` was dead and is deleted with its test; the `record_runner_report` note says nothing reads the flag.
- **F004** Fixed. The blocked listing's missing reason is `(no reason recorded)`.
- **F005** Fixed. The unrelated assertion and the dead constant and `steps.py` exclusion are gone.
- **F006** Documented, not changed. Stamping no cause on an observation would end the trailing count and let a stalling run resume past the limit; counting it errs toward blocking.
- **F007** Fixed. `params` uses a default factory and `pipeline` is stored stripped.

The review's diff was truncated (512000 of 1101777 characters reached the model).
