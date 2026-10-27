---
docType: review
layer: project
reviewType: code
slice: gates-git-and-human-steps
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/128-slice.gates-git-and-human-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261027
dateUpdated: 20261027
reviewedSha: b064cfc44a25d3a3123afb07c4d6189e04b20016
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 197189
cachedTokens: 3232
cacheWriteTokens: 193955
completionTokens: 3794
durationSeconds: 36.9
costUsd: 0.903739
costBasis: provider
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Silent empty-string fallbacks passed to external commands"
    location: "src/amoeba/runner/gates/merge.py#observe_merges"
  - id: F002
    severity: concern
    category: style
    summary: "`TYPE_CHECKING` block splits the import section"
    location: "src/amoeba/runner/finish.py"
  - id: F003
    severity: concern
    category: structure
    summary: "`observe_merges` is well over the function-size guideline"
    location: "src/amoeba/runner/gates/merge.py#observe_merges"
  - id: F004
    severity: concern
    category: typing
    summary: "Test helper missing return annotation under strict pyright"
    location: "tests/runner/gates/test_stage_dispatch.py#Setup.view"
  - id: F005
    severity: concern
    category: security
    summary: "Design path from CF is joined to the checkout without containment"
    location: "src/amoeba/runner/gates/outcome.py#_design"
  - id: F006
    severity: concern
    category: dry
    summary: "Repeated slice/step parent-lookup logic in `GateStage`"
    location: "src/amoeba/runner/gates/stage.py#GateStage"
  - id: F007
    severity: note
    category: maintainability
    summary: "Invisible literal and source-grep tests"
    location: "src/amoeba/runner/gates/hatches.py"
  - id: F008
    severity: note
    category: testing
    summary: "No dedicated load test for the new subprocess reads"
    location: "tests/load/test_runner_tick_load.py"
  - id: F009
    severity: pass
    category: security
    summary: "Read-only git boundary and budget discipline"
    location: "src/amoeba/runner/git_read.py"
---

# Review: code — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Silent empty-string fallbacks passed to external commands

`observe_merges` calls `read_target(checkout, slice_node.cf.project or "", ...)` and `is_ancestor_args(head or "", target)`. Both turn a missing value into `""` and run `cf -p ""` or `git merge-base --is-ancestor "" <target>`. This breaks the "never use silent fallback values" rule. `head` is already guaranteed non-None by `unobservable_reason`, and a missing `cf.project` should be an explicit `Unobservable` or read-failed result. `_recorded_git` is also called twice for the same entry, in `observe_merges` and in `merge_state`.

### [CONCERN] `TYPE_CHECKING` block splits the import section

The `if TYPE_CHECKING:` block sits between `from amoeba.runner.resolutions.vocabulary import ...` and `from amoeba.store import (...)`. This leaves a module-level import after non-import code, which ruff `E402` and `I` flag, and the Python rules require ruff in pre-commit and CI. Move the `TYPE_CHECKING` block below all imports. `ingest/record.py` has the same pattern but puts the block after the imports, so it is fine.

### [CONCERN] `observe_merges` is well over the function-size guideline

The function is about 60 lines. It mixes iteration, three kinds of read, fault creation and the completion write. It has five early exits (`return`/`continue`) and a hand-rolled `wrote` accumulator. The project guideline is functions of about 50 lines. Extract the per-slice step, for example `_observe_one(...)`, returning an observation, a fault, or a cut-off marker.

### [CONCERN] Test helper missing return annotation under strict pyright

`def view(self, ...):  # type: ignore[no-untyped-def]` suppresses a missing return type instead of annotating it. The Python rules require strict pyright on tests with zero errors. Annotate it `-> ProjectView`. `crash_entry.py` also assigns `tick_module.GateStage = PassingGates  # type: ignore[misc]`. That patches a module global in a non-test entry point, and an injectable stage or factory would be cleaner.

### [CONCERN] Design path from CF is joined to the checkout without containment

`(checkout / design_file).read_text()` uses a path taken from `cf list slices` output. An absolute path or one containing `..` escapes the checkout. Only the frontmatter is parsed, but YAML error text is stored in the check's `examined` record and could leak file content. Resolve the path and require it to be inside the checkout, otherwise return `DesignMissing`.

### [CONCERN] Repeated slice/step parent-lookup logic in `GateStage`

The step node → slice parent → initiative lookup is rewritten in `_predecessor`, `_record_disagreement` and `_observe`. `_record_disagreement` also calls `_predecessor` again after `_accepted` already did. Factor out one helper that returns the step, slice and predecessor nodes. The module docstring is also stale. It says "This task adds the outcome stage; the merge observation and the pre-dispatch reads join it in later tasks", but both are already present.

### [NOTE] Invisible literal and source-grep tests

`_BYTE_ORDER_MARK` holds a literal U+FEFF character, which is invisible in review. Use `"\ufeff"`. `test_the_module_does_no_io` in `test_hatches.py` and `test_predispatch.py` assert on source text, which is brittle. An import-level check would be sturdier.

### [NOTE] No dedicated load test for the new subprocess reads

The tick now makes up to several `git` and `cf` subprocess calls per candidate and per pending merge. The load test was only updated for the new constructor argument. `test_budget_coverage.py` checks that no call starts after the deadline, which is good. The Python rules also ask for a load test of a realistic configuration with latency or throughput assertions on these paths.

### [PASS] Read-only git boundary and budget discipline

`git_read` is the single entry point and has a subcommand allowlist. It also checks the budget, closes stdin, disables prompts and rejects option-like refs. An AST test enforces that no other module builds a git command. `decide()` refuses any launch or resume without a passed pre-dispatch check, and failed reads raise a project-scoped fault rather than defaulting. Test coverage is thorough.

### Run Digest

- Response length: 4868 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 197189 / 3232 / 193955 / 3794 / not computed
- Duration: 36.9 s
- Cost: $0.90 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
