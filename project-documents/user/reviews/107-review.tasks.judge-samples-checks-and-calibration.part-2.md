---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 16b074042139b5b5f54b3bf2388a2858e29304a8
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 284436
cachedTokens: 184025
cacheWriteTokens: 100403
completionTokens: 5485
durationSeconds: 45.7
costUsd: 0.475552
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Closing GitHub issue #2 is an outward-facing action before review and merge"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:320"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The PM-blocking fixture task sits earlier than its first consumer"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:147-154"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "No test ties `CheckPayload` field names to the constants in `check_models.py`"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:74"
  - id: F004
    severity: concern
    category: test-design
    summary: "The no-metrology test can fail on an explanatory comment in new code"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:28-55"
  - id: F005
    severity: note
    category: spec-consistency
    summary: "Task 6.4 correctly follows D9 over the LLD's \"two new kinds\" wording"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:351"
  - id: F006
    severity: note
    category: proportionality
    summary: "Test coverage is proportionate and the cadence holds"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Closing GitHub issue #2 is an outward-facing action before review and merge

Task 8.3 has the junior run `gh issue close 2 --comment "... Commit <sha>."` straight after the walkthrough commit. That commit sits on the unmerged slice branch, and Task 8.3 itself says Phase 7 code review follows. Review fixes or a rebase can change or orphan the sha, and the issue would be closed before the fix reaches the target branch. The slice's Technical Requirements only say the issue is "closed with a pointer to D4". They don't say when. Move the close to after merge, or make it an explicit PM-confirmed step instead of an automatic one.

### [CONCERN] The PM-blocking fixture task sits earlier than its first consumer

Task 6.5 stops and asks the PM if the judge fixture is missing. Task 7.1 depends on 6.5, but 7.1 only adds a flag and a helper and never touches the fixture. The task text says 7.2, 8.1 and 8.3 are the only consumers. As written, a missing capture also blocks 7.1, which doesn't need it. Move 6.5 to just before Task 7.2 (or drop 7.1's dependency on it) so more work proceeds unblocked.

### [CONCERN] No test ties `CheckPayload` field names to the constants in `check_models.py`

Task 6.1 requires `CheckPayload`'s field names to be the constants defined in `check_models.py`. The slice's Technical Requirements say they are defined once. Task 6.2's tests cover validation, rejection, replay and the CLI. None checks that the pydantic model and the constants agree, so the two can drift apart silently. 104 has an analogue for verdicts in `tests/store/test_verdict_payload_types.py` and `test_verdict_to_payload.py`. Add one assertion that the model's field set equals the constant set.

### [CONCERN] The no-metrology test can fail on an explanatory comment in new code

The Task 5.2 test scans all of `src/` for the substring `metrology`, case-insensitively. `src/` has no match today (I grepped it). The slice text repeatedly discusses the metrology constraint, though, so a junior writing `calibration.py` could easily put "never reads Squadron's metrology store" in a docstring and trip the test. The LLD only requires that `src/` not reference the directory or config key. Either tell Task 5.1 not to use the word in comments, or narrow the test to the actual directory and key strings.

### [NOTE] Task 6.4 correctly follows D9 over the LLD's "two new kinds" wording

The LLD Technical Requirements say the invariant test passes with "the two new kinds". D9 defines only `check_recorded`. Task 6.4 flags this and follows D9, which is right. The LLD line itself is stale and should be fixed in the slice design when the walkthrough is updated in Task 8.3. That task is limited to editing the walkthrough section, so the fix needs a PM decision.

### [NOTE] Test coverage is proportionate and the cadence holds

Every success criterion in this file's scope maps to a task:
- **Calibration:** Tasks 5.1–5.2.
- **Check kind, including inbox rejection of a negative count:** Tasks 6.1–6.2.
- **Check feed change:** Tasks 6.3–6.4.
- **Judge fixture:** Task 6.5.
- **Sample ids:** Tasks 7.1–7.2.
- **Listings and columns:** Tasks 7.3–7.5.
- **End-to-end:** Task 8.1.
- **Contract docs and CHANGELOG:** Task 8.2.
- **Walkthrough and validation:** Task 8.3.

The paired "committed with" tasks keep untested behavior out of commits. The one overlap is the field-name equality assertion in Task 5.2, which duplicates the D3 list; it is cheap and harmless. Splitting across two task files is justified by the amount of work (29 tasks across eight sections).

### Run Digest

- Response length: 4769 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 284436 / 184025 / 100403 / 5485 / not computed
- Duration: 45.7 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
