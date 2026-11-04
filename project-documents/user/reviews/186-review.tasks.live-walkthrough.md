---
docType: review
layer: project
reviewType: tasks
slice: live-walkthrough
targetKind: slice
rulesSource: project
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
reviewedSha: 5abf3b7742da49399a8029c3070e5f46d661e9b4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: xhigh
turns: 13
promptTokens: 744031
cachedTokens: 606406
cacheWriteTokens: 137611
completionTokens: 75714
durationSeconds: 403.1
costUsd: 0.21883
costBasis: provider
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:297-319"
  - id: F002
    severity: concern
    category: consistency
    summary: "Task 4.5 corrects the design after the code is built against it"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:154-158"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 3 commits constants that Task 4.1 later moves"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:117-124"
  - id: F004
    severity: concern
    category: sequencing
    summary: "The preflight gate blocks Tasks 1 and 2, which do not need 180–185"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:71-76"
  - id: F005
    severity: concern
    category: process
    summary: "Start-up and provider failures default to Task 4 or Task 2 fixes"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:170"
  - id: F006
    severity: concern
    category: process
    summary: "`fix:` commits on the slice branch conflict with the Fixes rules"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:59"
  - id: F007
    severity: concern
    category: clarity
    summary: "Task 8.3's branch lookup has no stop for an empty result"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:232"
  - id: F008
    severity: concern
    category: consistency
    summary: "Task 9.1 expects `requested` after the release has happened"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:248"
  - id: F009
    severity: concern
    category: sequencing
    summary: "A product-defect block in case 1 has no stated effect on cases 2 and 3"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:59"
  - id: F010
    severity: concern
    category: coverage
    summary: "\"Nothing written outside D\" is asserted but never checked"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:282"
  - id: F011
    severity: concern
    category: consistency
    summary: "Task 11's success criteria cannot all hold as written"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:310"
  - id: F012
    severity: note
    category: clarity
    summary: "Task 3.1 leaves two choices to guess"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:119-120"
  - id: F013
    severity: note
    category: granularity
    summary: "Shared stubs belong in a conftest, not a new module"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:87"
  - id: F014
    severity: note
    category: consistency
    summary: "`answerer_walkthrough.py` will exceed the line guideline, and the stated justification is wrong"
    location: "scripts/answerer_walkthrough.py"
  - id: F015
    severity: note
    category: scope
    summary: "The manifest in 11.2 is a convention the design does not ask for"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:302"
  - id: F016
    severity: note
    category: granularity
    summary: "The 3.1 mutation check edits a committed tree by hand"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:122"
  - id: F017
    severity: note
    category: clarity
    summary: "0.1 says \"change nothing\" and then creates the branch"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:72"
  - id: F018
    severity: note
    category: consistency
    summary: "The design's frontmatter omits 144"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:6-13"
  - id: F019
    severity: note
    category: clarity
    summary: "11.3 asks for a claim without saying where it goes"
    location: "project-documents/user/tasks/186-tasks.live-walkthrough.md:307"
---

# Review: tasks — slice 186

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria trace to tasks

Each functional, technical and integration criterion has a task. Cases 1 to 3 map to 8.1–10.2. The "not demonstrated" closure appears in 8.3, 9.1, 10.2 and 11.3. The `inspect program` readable check is 7.1. The trees and fixture test are 2 and 3. Setup refusals and the subprocess stop are 4.1 and 4.4. The `answerer_walkthrough.py` behaviour is 1.1. Captures are 11.1–11.2. The doc and its link are 6.1–6.2. Validation is 11.4. The only criterion removed, the refusal of a non-`applied` registration, is handled by 4.5.

### [CONCERN] Task 4.5 corrects the design after the code is built against it

The cause is real. 145's task file says a submission is applied only when the resident process runs (`project-documents/user/tasks/145-tasks.live-walkthrough.md:121`), and 181's design applies it inside the resident tenant (`project-documents/user/slices/181-slice.program-record.md:121`). The slice design still requires the script to stop unless `applied` (`186-slice.live-walkthrough.md:214`), to print node ids (222), and to refuse a non-applied registration (311). Tasks 4.1–4.4 are written against that LLD, and 4.5 comes last. Move 4.5 to the start of Task 4 so the implementer reads the corrected LLD first, and keep the edit under the planning-commit rule rather than on the slice branch.

### [CONCERN] Task 3 commits constants that Task 4.1 later moves

3.1 imports the ids from `program_walkthrough.py` "once Task 4 creates it" and defines them in the test until then. The design puts them only at the top of the script (`186-slice.live-walkthrough.md:265`). So the marker at line 124 commits the duplicate the design forbids, and Task 4 later moves it. 3.1 also does not say how the test loads the script; 4.4 says to load it as `test_answerer_walkthrough_script.py` does. Create the constants module as the first step of Task 3 and state the load method there.

### [CONCERN] The preflight gate blocks Tasks 1 and 2, which do not need 180–185

0.1 writes `BLOCKED:` and stops if any 180–185 code is missing, and it gates the whole file. Task 1 needs only 145's helpers. Task 2 needs only 182's concept-format design document (line 101). Neither needs 180–185 code. Scope the gate so it applies before Task 3 (which needs 182's `program_rig.py`) and before 4.3 (which needs the config keys from 184 and 185). Tasks 1 and 2 can then proceed.

### [CONCERN] Start-up and provider failures default to Task 4 or Task 2 fixes

5.2 says any error other than 180's or 140's D8 probe failure "is a defect in Task 4: fix it there". An absent `sq`, a key error or a model problem is an environment cause. 7.1 (line 204) says an unreadable member or rejected registration "is a defect in Task 2 or Task 4". A cause inside 180–185 is a product defect under D7 (line 59), filed as an issue and never fixed here. These instructions would push the worker to change scratch trees or setup to work around a cause it cannot fix. Classify each failure by D7's four causes, and fix only fixture causes in Tasks 2 and 4.

### [CONCERN] `fix:` commits on the slice branch conflict with the Fixes rules

The markers at lines 174 and 210 and the rule at line 59 commit slice-internal corrections as `fix: {summary}` on the slice branch. The project's Fixes rules say a bug in the slice's own code is part of the slice, and work committed as `fix:` follows the fixes path: a small fix on the target, or a standing-fixes group for multi-step work. Corrections to this slice's trees or setup should use the slice's commit type. Line 59 also says the fix commit "is a marker of every live task", and 10.3 (line 275) makes a tree change with no marker of its own. Say which commit that is.

### [CONCERN] Task 8.3's branch lookup has no stop for an empty result

The step gets the slice branch name from `git branch --list '700-slice.*'`, with that literal pattern beside it and no stop condition. If the list is empty, a worker could guess a name and merge the wrong branch into `main`, which is the only PM action in this run that changes a repository's `main`. Add: if no branch matches, stop, record the empty output under the Result, and merge nothing.

### [CONCERN] Task 9.1 expects `requested` after the release has happened

9.1 waits until slice 101 is `done` and then checks that the question record is `requested`. Task 8.3 (line 233) expects `answered` once the edge releases, and slice 101 cannot be `done` until that release has happened. The two checks contradict each other. Check `requested` at the request hop (after the first wait), and check `answered` at release.

### [CONCERN] A product-defect block in case 1 has no stated effect on cases 2 and 3

Line 59 says a product defect marks the case `BLOCKED:` on its issue. Slice 101 cannot be driven until slice 100 is `done` (the index rule), and 9.1 and 10.1 name the prior task as a prerequisite. So a blocked case 1 stops cases 2 and 3 as well. The breakdown does not say whether that is intended, or whether a defect closes through resolution the way other failed attempts do. State which, so the worker does not have to decide.

### [CONCERN] "Nothing written outside D" is asserted but never checked

The design requires that nothing is written outside D (`186-slice.live-walkthrough.md:306`). The doc's final checks repeat the claim (line 186), and 10.4 checks the real supervisor directory and this repository's `git status`. Neither would catch a write elsewhere. The design says the real registry and supervisor directory are never written (line 38). Record a listing of both in 5.1 and compare them in 10.4.

### [CONCERN] Task 11's success criteria cannot all hold as written

11.4 requires every not-demonstrated case to have its issue linked. Line 59 files issues only for product defects, so a model-judgement or environment closure has no issue. 11.1 and 11.2 require the captured counts to match the records and runs, but the screening at line 294 says a hit means the capture is "not added". State that counts exclude captures the screening withheld, and that the issue link applies only to product defects.

### [NOTE] Task 3.1 leaves two choices to guess

Line 119 says to commit the three trees "on `main` of three repositories" without saying they are created under the test's `tmp_path`. The trees also live in this repository (`scripts/program_walkthrough/`), so a literal reading commits them to Amoeba's `main`. Line 120 calls `assemble_sources`, the production function (`src/amoeba/runner/answering/sources.py:103`), while 0.1 lists the test helper `assemble` (`tests/runner/answering/sources_assembly.py:78`). Name the one to call.

### [NOTE] Shared stubs belong in a conftest, not a new module

1.2 moves the `stubs` and `env_file` fixtures into a new helper module that the tests import back. Both test files sit in `tests/`, so `tests/conftest.py` would share them with no import and no new module. D6 adds no module on the script side, so the conftest is the simpler fit.

### [NOTE] `answerer_walkthrough.py` will exceed the line guideline, and the stated justification is wrong

The file is 292 lines (verified). 1.1's note (line 80) says the LLD (D6) accepts about 15 more lines. D6 says nothing about size, and the project guideline is about 300 lines per source file. Remove the claim, or trim the file to stay near the guideline.

### [NOTE] The manifest in 11.2 is a convention the design does not ask for

D8 requires that each fixture keep its run id, date and source. The task adds a manifest per fixture directory that tests read and never glob. That is justified only if the reply files cannot carry `source` without changing what the parser reads, and the task does not say so. Either state that reason, or put the source in the file name beside the run id.

### [NOTE] The 3.1 mutation check edits a committed tree by hand

"Temporarily removing the Markdown sentence… restoring it" asks the worker to edit a committed file and put it back before the marker. The design asks for the assertion (line 225), not a manual mutation run. Do the removal on a copy inside `tmp_path`, or drop the step.

### [NOTE] 0.1 says "change nothing" and then creates the branch

The heading says "change nothing", and the first bullet says "Create the branch". Line 49 gives the same branch step. Keep it in one place.

### [NOTE] The design's frontmatter omits 144

The frontmatter lists 145 and 180–185 but not 144. The design's Technical Scope and D8, and Task 11.1, all write into 144's `question_tails.json`, and the task file lists 144. Add 144 to the design's dependencies.

### [NOTE] 11.3 asks for a claim without saying where it goes

"State milestone 5's end-to-end claim only for the cases shown" does not say where the claim goes: the doc, the task Result, or the Verification Walkthrough. Name the location.

### Run Digest

- Response length: 12380 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 744031 / 606406 / 137611 / 75714 / not computed
- Duration: 403.1 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19

## Resolution

- [concern] Task 4.5 corrects the design after the code is built against it: fixed. The design (D5, D6, Technical Requirements, Functional Requirements, the setup-script row) was corrected in a planning commit and Task 4.5 was removed.
- [concern] Task 3 commits constants that Task 4.1 later moves: fixed. Task 3.1 creates `scripts/program_walkthrough.py` holding only the constants; Task 4.1 builds on them.
- [concern] The preflight gate blocks Tasks 1 and 2: rejected. The slice starts after 180 to 185 are merged (LLD Prerequisites); a partial start has no use.
- [concern] Start-up and provider failures default to Task 4 or Task 2 fixes: fixed. Tasks 5.2 and 7.1 classify by D7's four causes and fix only fixture causes.
- [concern] `fix:` commits conflict with the Fixes rules: fixed. Corrections to this slice's own files use `feat:`; Task 10.3's rerun commit is named as a marker.
- [concern] Task 8.3's branch lookup has no stop for an empty result: fixed.
- [concern] Task 9.1 expects `requested` after the release: fixed. `requested` is checked at the request hop, `answered` at the end.
- [concern] A product-defect block in case 1 has no stated effect on cases 2 and 3: rejected. A `BLOCKED:` line already means stop; the later cases cannot run.
- [concern] "Nothing written outside D" is never checked: rejected. 10.4 checks the real supervisor directory, the real registry and this repository's `git status`; a stray write elsewhere is rare and has no cheap check.
- [concern] Task 11's success criteria cannot all hold: fixed. Counts exclude withheld captures; the issue link applies to product defects only.
- [note] Task 3.1 leaves two choices to guess: fixed (`tmp_path`; the assemble call is the one 145's fixture test makes).
- [note] Shared stubs belong in a conftest: rejected. 145 owns the helper layout; either works.
- [note] `answerer_walkthrough.py` size claim: fixed (claim removed).
- [note] The manifest in 11.2: rejected. It keeps the run id, date and source D8 requires without changing what the parsers read.
- [note] The 3.1 mutation check edits a committed tree: fixed (done on a copy in `tmp_path`).
- [note] 0.1 says "change nothing" then creates the branch: rejected. The sentence scopes "change nothing" to the reading that follows the branch step.
- [note] The design's frontmatter omits 144: fixed.
- [note] 11.3 asks for a claim without saying where it goes: rejected. The doc is the only place the claim can live (11.3 reads it).
- [pass] Success criteria trace to tasks: no change needed.
