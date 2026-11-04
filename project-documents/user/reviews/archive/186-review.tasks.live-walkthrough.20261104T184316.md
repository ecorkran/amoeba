---
docType: review
layer: project
reviewType: tasks
slice: live-walkthrough
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/186-tasks.live-walkthrough.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 6d7dda30a429bc3408a600d30d5970ffc2223188
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 672319
cachedTokens: 489561
cacheWriteTokens: 182746
completionTokens: 81989
durationSeconds: 412.7
costUsd: 0.278015
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Functional criteria, decisions and scope items all have tasks"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md"
  - id: F002
    severity: concern
    category: safety
    summary: "`register-program` is submitted without the isolated environment"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:141"
  - id: F003
    severity: concern
    category: coverage
    summary: "The design's \"real CF registry\" criterion conflicts with registry isolation"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:305"
  - id: F004
    severity: concern
    category: process
    summary: "Task 4.3 amends the parent design inside an implementation commit"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:144"
  - id: F005
    severity: concern
    category: verifiability
    summary: "Live-task waits name no listing, so the wait rule cannot be applied"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:215"
  - id: F006
    severity: concern
    category: verifiability
    summary: "Task 12.2's parser tests cannot all pass if a capture is a defect"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:306"
  - id: F007
    severity: concern
    category: coverage
    summary: "Reply captures carry no date, and the fixture format is unspecified"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:305"
  - id: F008
    severity: concern
    category: safety
    summary: "Captures are committed verbatim with no secret or local-path check"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:302"
  - id: F009
    severity: concern
    category: verifiability
    summary: "`uv run pyright` does not check `scripts/`, so the pyright criteria are unverifiable as written"
    location: "pyproject.toml:52"
  - id: F010
    severity: concern
    category: scope
    summary: "`answerer_walkthrough.py` is 292 lines, and `ProjectSpec` omits inputs the helpers need"
    location: "scripts/answerer_walkthrough.py:142"
  - id: F011
    severity: concern
    category: verifiability
    summary: "Task 5.2's success criterion accepts a probe failure, so it cannot fail"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:164"
  - id: F012
    severity: concern
    category: clarity
    summary: "The 10.3 rerun trigger is undefined"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:273"
  - id: F013
    severity: concern
    category: convention
    summary: "Prerequisite sub-items have no checkbox"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:196"
  - id: F014
    severity: note
    category: granularity
    summary: "Doc-update tasks and Task 11 are thin enough to fold"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:250"
  - id: F015
    severity: note
    category: granularity
    summary: "Tasks 5.2 and 7.1 both run the start-up probe"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:197"
  - id: F016
    severity: note
    category: sequencing
    summary: "Task 0.1 branches from the target while the planning file has uncommitted edits"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:72"
  - id: F017
    severity: note
    category: convention
    summary: "Commit types for 10.3 and 12 don't match their contents"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:315"
  - id: F018
    severity: note
    category: scope
    summary: "Task 8.3's merge sub-item needs its carve-out where it is used"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:227"
  - id: F019
    severity: note
    category: verifiability
    summary: "Search criteria need whole-word, case-insensitive matching"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:111"
  - id: F020
    severity: note
    category: clarity
    summary: "Some referenced helpers and paths are described, not named"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:118"
---

# Review: tasks — slice 186

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Functional criteria, decisions and scope items all have tasks

Cases 1 to 3 map to 8.1–10.2. The not-demonstrated path is covered by 8.4, 9.2, 10.4 and 12.3. The `readable` check is 7.1, the final registry check is 11.1, and the fixture test is 3.1. The refusals and subprocess stops are 4.1 and 4.4, the answerer parameter is 1.1 and 1.2, captures are 12.1 and 12.2, and the process-contract link is 6.2. D1 to D9 are all traced. The test-with pattern holds (3.1 follows the trees, 4.4 follows the script). The two parser tests in 12.2 are justified by the project rule for parsers, not scope creep.

### [CONCERN] `register-program` is submitted without the isolated environment

Task 4.2 sets `CONTEXT_FORGE_DATA_DIR=D/cf` and `AMOEBA_STORE_DIR=D/store` for the per-project steps. Task 4.3 submits `register-program` with no environment stated. The task-4.4 stubbed run (line 149) checks call order but not environment. The preamble (line 65) says the real registry and supervisor directory are never written, and the design requires both variables on every spawned `cf` and `sq` (slice design line 223). A literal reading of 4.3 could register the program in the real store. Name the variables for this call and make 4.4 assert them. `scripts/answerer_walkthrough.py:253-257` already builds that env once, so the program script can reuse the pattern.

### [CONCERN] The design's "real CF registry" criterion conflicts with registry isolation

Line 305 asks for `amoeba inspect program` to show all three members `readable` "against the real CF registry". The Overview (line 38), D6 registry isolation (line 223) and the task preamble (line 65) all keep the walkthrough in `D/cf`. Task 7.1 checks `readable` in the isolated registry, which is the only reading that keeps isolation. The criterion as written cannot hold alongside isolation. The PM should decide the wording, and the design should be corrected in planning before Task 7 runs.

### [CONCERN] Task 4.3 amends the parent design inside an implementation commit

Task 4.3 edits the slice design's D5 (line 214), D6 "Script" (line 222) and Technical Requirements (line 311). The edit lands in `feat: add program walkthrough setup script` (marker at line 153). The commit cadence keeps planning documents in their own planning commit, made after review. The change also removes the "refuse a non-`applied` registration" requirement during implementation. The requirement is relocated, not dropped: Task 7.1 checks `applied` after start (line 198). The deviation is sound, but it should be a reviewed design revision made before Task 4 begins.

### [CONCERN] Live-task waits name no listing, so the wait rule cannot be applied

The Waiting rule (line 63) ends a wait when "the listing named in the check" shows the expected state. Three waits name no listing: "Wait for the design question and the answering run" (215), "Wait for `notes-store`'s request run" (221) and "Wait until `notes-store` slice 700 is `done`" (226). A session cannot tell when those waits end. Name the listing for each (for example `inspect questions --json`, `inspect nodes`, `inspect program-blocked --json`).

### [CONCERN] Task 12.2's parser tests cannot all pass if a capture is a defect

Line 306 adds a parser test for each capture, says a non-parsing capture is a defect to file, and says "Do not change the parser." A deterministic defect would fail that test. Yet line 307 requires `uv run pytest tests/runner/answering tests/runner/request_run` to pass, and 12.4 (line 313) requires all tests to pass. Those cannot hold together. Say how a known-defect capture is held, for example an `xfail` tied to the issue number.

### [CONCERN] Reply captures carry no date, and the fixture format is unspecified

The integration requirement (slice design line 318) says every capture carries run id, date and `source: 186-walkthrough`. Task 12.1 gives the date (`captured`). Task 12.2 says only that each reply "keeps its run id and source", with no date. It also does not say how those fields sit in the reply-artifact and `reply.json` fixtures. Name the field and its carrier (sidecar, wrapper or in-file key) for each of the two kinds.

### [CONCERN] Captures are committed verbatim with no secret or local-path check

Tasks 12.1 and 12.2 copy question tails, reply artifacts and `reply.json` files from live run directories into committed fixtures. Those runs execute in checkouts that hold the provider `.env`, and their paths sit under the `$(mktemp -d)` directory. CLAUDE.md forbids committing credentials. The task has no step to scan captures for key material or machine-local paths before the commit at line 315. Add that step to 12.1 and 12.2.

### [CONCERN] `uv run pyright` does not check `scripts/`, so the pyright criteria are unverifiable as written

`[tool.pyright]` includes only `src` and `tests`. Task 1.1 (line 85) and Task 4.4 (line 151) require `uv run pyright` to be clean "on the script", but the script lives in `scripts/`, so the plain command reports nothing for it. Either name the files explicitly or widen the include, and say which. Also, the scratch trees' Python (`src/notes_store/jsonl.py`, `src/notes_export/text.py`) lives under `scripts/`, so repo-wide `uv run ruff check .` (line 312) lints it. Task 2 does not say those files must pass ruff.

### [CONCERN] `answerer_walkthrough.py` is 292 lines, and `ProjectSpec` omits inputs the helpers need

The file is already 292 lines. Task 1 adds a frozen `ProjectSpec` and splits `read_live_settings`, and the design forbids a new module (slice design line 221). The file will likely pass the project's ~300-line guideline (task file line 51), and the task has no plan for that. The spec as written (`ProjectSpec(project_id, tree, cf_artifacts, checkout)`, task line 83) also omits the env file that `build_checkout` copies as `.env` (`answerer_walkthrough.py:142`, `:182`) and the env mapping all three helpers take (`:185`, `:210`). Add both to the spec. Then decide where `ProjectSpec` and the live-variable helpers go if the file exceeds the guideline.

### [CONCERN] Task 5.2's success criterion accepts a probe failure, so it cannot fail

"the log shows the sq probe and the slice-writing and answering probes passing, or a probe failure" is met whatever the log says. Line 165 separately defines a defect. State the success as: the probes pass, or the only failure names 180's or 140's D8 capabilities.

### [CONCERN] The 10.3 rerun trigger is undefined

Line 59 says a case "that needs a rerun" gets one in 10.3, and 10.3 (line 273) gates it on "worth one more run". That is a judgment with no stated test, so a session cannot decide it. The design (slice design line 232) says only that a rerun goes on a new slice. State the rule: every case closed as shown in part gets one rerun, or a named condition triggers it.

### [CONCERN] Prerequisite sub-items have no checkbox

Ten "Prerequisite:" sub-items (lines 196, 214, 220, 225, 244, 262, 267, 272, 289, 301) lack the `[ ]` that CLAUDE.md requires for every item and subitem. Add the checkbox, or move the prerequisite into the task heading.

### [NOTE] Doc-update tasks and Task 11 are thin enough to fold

Tasks 9.2 and 10.4 are one line each ("As Task 8.4", lines 250 and 279). Fold each into its case's last sub-item and keep the case commit markers. Task 11 (effort 1) could join 12.4. Its prerequisite (line 289) names 10.2, but 10.4 should come first, so name 10.4.

### [NOTE] Tasks 5.2 and 7.1 both run the start-up probe

The first sub-item of 7.1 repeats 5.2. That is fine if re-running after the BLOCKED line is removed is the intent, but say so.

### [NOTE] Task 0.1 branches from the target while the planning file has uncommitted edits

At session start, git status showed the 186 task file as modified. The planning commit should land on the target before 0.1 creates the slice branch, so the branch starts from the reviewed plan.

### [NOTE] Commit types for 10.3 and 12 don't match their contents

Marker 12 is `docs:` but adds parser tests and fixtures. Marker 10 (line 282) bundles tree edits under `scripts/program_walkthrough/` into a `docs:` commit. Use `test:` for the test and fixture changes.

### [NOTE] Task 8.3's merge sub-item needs its carve-out where it is used

AGENTS.md says a merge is never written as a task or sub-item. The carve-out (the merge happens only in the scratch checkout, per line 49) makes 8.3 legitimate. Repeat it in the sub-item and keep `git -C D/checkouts/notes-store` on the command so it cannot run in this repository.

### [NOTE] Search criteria need whole-word, case-insensitive matching

A plain search for "tag" also matches "stage". The "markdown" search in 2.2 (line 105) is also unstated for case. Specify whole-word, case-insensitive matching.

### [NOTE] Some referenced helpers and paths are described, not named

Task 3.1 refers to "the shared assembly helpers 145 added beside `sources_repo.py`" without naming them. Task 2.1 says "open 182's design" (line 101) without a path. I confirmed that `tests/runner/answering/sources_repo.py` and `test_walkthrough_fixture.py` exist. Name the helpers and the 182 design path.

### Run Digest

- Response length: 12187 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 672319 / 489561 / 182746 / 81989 / not computed
- Duration: 412.7 s
- Cost: $0.28 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
