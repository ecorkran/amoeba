---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 83153c08b9faacf705a3f27a258826318111750f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 51.0
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Task 3.5 expects `sq_run_id` from the new 0.15.0 file, which the CLI capture will not have"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:297"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 4.2 does not cover every branch of the `findings_parsed` rule"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:344"
  - id: F003
    severity: concern
    category: clarity
    summary: "Task 1.2 does not say which review to run or what the command is"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:76"
  - id: F004
    severity: note
    category: test-design
    summary: "Task 3.3's \"defined once\" grep test is fragile and is deferred"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:256"
  - id: F005
    severity: note
    category: scoping
    summary: "Task 3.2's file-split wording is ambiguous"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:233"
  - id: F006
    severity: note
    category: redundancy
    summary: "Task 4.2 lists the trailing-line check twice"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:343-345"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria for Sections 1–5 trace to tasks, with no scope creep"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence are sound"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:26-30"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 3.5 expects `sq_run_id` from the new 0.15.0 file, which the CLI capture will not have

Task 3.5 says "the 106 file and the new 0.15.0 file give `sq_run_id` and `upstream_version`". The slice design says `run_id` is null on the CLI, and `runId` appears in frontmatter "only on pipeline runs" (design lines 72 and 81). The new pair from Task 1.2 comes from a plain `sq review` CLI run, so it will most likely have no `runId`. The design's criterion ("The 0.15.0 file yields `sq_run_id` and `upstream_version`") fits the 106 fixture, which has `runId`. Task 1.1 also checks that the 106 fixture has `runId`. The test as written will fail on a correct parser, or push the implementer to doctor the fixture. Fix: expect `sq_run_id` from the 106 file only. For the new file, expect `upstream_version` (`squadronVersion`) and assert `sq_run_id` matches whatever its frontmatter actually has (likely `None`).

### [CONCERN] Task 4.2 does not cover every branch of the `findings_parsed` rule

The design's D3 rule for stdout has three outcomes: false, `None` when `fallback_used` is absent, and otherwise true. The synthetic variants in 4.2 cover only `fallback_used: true` with `stated`, and `true` with `derived`. Missing cases:
- `fallback_used` absent gives `findings_parsed=None`.
- `fallback_used: true` with `verdictSource` null gives `False` (`not_reported`).
- `fallback_used: false` gives `True`.

The `None` branch is the easiest to get wrong silently. Add these as explicit rows.

### [CONCERN] Task 1.2 does not say which review to run or what the command is

"Run `sq review` for a slice, with a slice number" names no slice, template or arguments. A junior can't tell which slice document to review, or whether the throwaway copy contains it. Later tasks (3.5, 4.2, 5.2) rely on this pair, so the exact command matters. The task has a good stop-and-ask rule for a missing `sq` or key. Add the same for an ambiguous command. Better, give the slice and template to use, or tell the junior to ask the PM before running. The README entry for the pair should also repeat the secrets and hand-edit scan from Task 1.1, since the pair is new model output.

### [NOTE] Task 3.3's "defined once" grep test is fragile and is deferred

Common keys such as `"verdict"`, `"score"`, `"model"`, `"id"` and `"slice"` can legitimately appear as quoted strings in error messages or docstrings. Because the test is written in 3.3, before any mapping code exists, it passes trivially at that point and only bites once 3.4 and 4.1 land. Consider making it AST-based (string constants used as dict keys or `.get` arguments) and say explicitly that it must stay green through 3.4, 4.1 and 5.3.

### [NOTE] Task 3.2's file-split wording is ambiguous

Task 3.2 says helpers go in `review.py` "(or `review_artifact.py` if already split)". Nothing splits the file before Task 4.1, and 4.1 makes the split conditional on line count. Make the split rule a single decision point. For example, 4.1 performs it, and the helpers are moved in that step with the existing tests as the safety net.

### [NOTE] Task 4.2 lists the trailing-line check twice

The "trailing-line tolerance" bullet and the later "appended text after the object" bullet test the same thing. Merge them. The task also notes that no existing capture carries a trailing line, which differs from the design's success-criterion wording about 0.14.0 captures. That's fine, since the synthetic append covers it. Mention the discrepancy in the README or the test docstring so a reader isn't confused.

### [PASS] Success criteria for Sections 1–5 trace to tasks, with no scope creep

The design's fixture list maps to Tasks 1.1–1.3, including the known-gap edited copy. PyYAML maps to 2.1, the shared provider-failure rule to 2.2–2.3, and `review_fields` to 2.4. The file reader maps to 3.1–3.5, the stdout reader to 4.1–4.2, the record id to 5.1–5.2, and `to_verdict_input` with the D4 cases to 5.3–5.4. The import-direction test (5.5) matches a stated technical requirement. The parser error cases the design requires each have a test, and the provider-failure contradiction cases are in 3.5. Task 3.4 and Task 5.3 both honour the exclusion of `source_document` and `slice` from `VerdictInput`.

### [PASS] Sequencing and commit cadence are sound

There are no circular dependencies. The PyYAML move is placed before the parser, with a note explaining why it departs from the design's step 8. Implementation tasks are paired with an immediately following test task and share a commit (3.2/3.3, 3.4/3.5, 5.1/5.2, 5.3/5.4). The commit cadence statement matches this. Commits are spread across all five sections rather than batched at the end. Task sizes (effort 1–3) are reasonable, and none needs splitting or merging.

### Run Digest

- Response length: 6196 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 51.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
