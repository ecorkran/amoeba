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
reviewedSha: 157bbb34e9c0e3e4bd7d3699f8cc525b31507933
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 56.6
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: clarity
    summary: "Fixture references use ellipses where two files share a stem"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:254"
  - id: F002
    severity: concern
    category: prompt-hygiene
    summary: "Task 1.2 puts a hardcoded version next to a \"record the actual value\" instruction"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:77"
  - id: F003
    severity: concern
    category: scope
    summary: "review.py may exceed ~300 lines after Section 5, but the size check happens only in Task 4.1"
    location: "src/amoeba/upstream/squadron/review.py"
  - id: F004
    severity: concern
    category: testing
    summary: "The \"defined once\" test in Task 5.5 can false-positive on short, common strings"
    location: "tests/upstream/test_field_names_defined_once.py"
  - id: F005
    severity: note
    category: sizing
    summary: "Task 3.5 is large"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:288"
  - id: F006
    severity: note
    category: traceability
    summary: "The task file correctly diverges from the slice on trailing stdout lines"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:363"
  - id: F007
    severity: note
    category: sequencing
    summary: "Minor dependency and scope tidy-ups"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:123"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 1–5"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-374"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:28"
  - id: F010
    severity: pass
    category: nfr
    summary: "No NFR or load-test obligation"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Fixture references use ellipses where two files share a stem

`tests/fixtures/sq_reviews/` holds two files for each 102 part: `…part-1.20260921T112529.md` and `…part-1.md`, and `…part-2.20260921T112635.md` and `…part-2.md`. Tasks 3.3 and 3.5 refer to "`102-…part-2.md` (round 2)" and "the round 1 part 1 file". Task 3.5 also calls part-2 "the 0.14.0 `102-…part-2.md` heading-only". A junior AI can't tell which of the two part-2 files is the heading-only provider failure. The unstamped `…part-1.md` is round 2 per the slice walkthrough, which makes "round 1 part 1" easy to mix up. Spell out the full filenames, or use the `tests/review_fixtures.py` constants by name. Task 1.3 already gives the full name for one of them.

### [CONCERN] Task 1.2 puts a hardcoded version next to a "record the actual value" instruction

Step 3 tells the implementer to run `sq --version` and record the actual value, and in the same sentence names "0.15.0" as the expected value. The project's CLAUDE.md calls this pattern a hallucination trap. If the command output is empty or odd, the nearest plausible token is the literal. Later steps and Tasks 4.2 and 5.4 also say "0.15.0 pair". Reword to say: print the version, and stop with an error if no version is printed. Refer to the pair by its fixture constant rather than a version.

### [CONCERN] review.py may exceed ~300 lines after Section 5, but the size check happens only in Task 4.1

Task 4.1 is the only place that tells the implementer to split `review.py` into `review_json.py` and `review_artifact.py` if it passes ~300 lines. Tasks 5.1 and 5.3 then add `review_record_id`, `to_verdict_input`, and the re-exports. The project limit applies to the file as it stands after each addition. Add a size check to Task 5.3, with the same split instruction. Task 3.2's note about moving the helpers should also name the split.

### [CONCERN] The "defined once" test in Task 5.5 can false-positive on short, common strings

The test fails on any string constant equal to a Squadron key. Keys such as `id`, `score`, `model`, `slice`, `location`, and `verdict` are also ordinary words. They may legitimately appear as `getattr` names, dict keys for non-Squadron data, or short messages. The step says to fix the source and not loosen the test, which could push a junior AI toward contortions. Say how to handle a legitimate non-key use of such a word, for example by scoping the scan to subscript and `.get()` arguments. Alternatively, tell the implementer to stop and ask the PM when the hit is not a Squadron key access.

### [NOTE] Task 3.5 is large

Task 3.5 combines a table over about eight fixtures, seven named cases, three missing-key tests, five finding-error tests, two provider-failure error tests, and an unknown-key test. Effort 3 looks low for the volume. It could be split into "real-file table and named cases" and "error cases". Both halves are completable as written, so this is not blocking.

### [NOTE] The task file correctly diverges from the slice on trailing stdout lines

The slice's success criteria say "The 0.14.0 captures, which have a trailing stdout line, parse the same as a pure-JSON capture." A grep of `tests/fixtures/sq_reviews/` finds no `Saved review to` line in either existing stdout capture. Task 4.2 handles this by appending the line to a real capture's text, and that satisfies the intent. The slice wording is inaccurate, and the PM may want to correct it. Task 4.1's criterion also says "the new pair's stdout file", which means two existing captures plus the new one.

### [NOTE] Minor dependency and scope tidy-ups

- Task 2.1 lists "Dependencies: None (branch from Task 1.1 exists)". It actually needs the branch Task 1.1 creates, so it should list Task 1.1.
- Task 3.1 says `tests/upstream/__init__.py` "(if other test packages use one)". Check `tests/store/` once and state the answer.
- Task 4.1 has no commit line. Add "committed with Task 4.2", as 3.2, 3.4, 5.1, and 5.3 do.
- Task 5.5 does not trace to a bullet in the "Development Approach" list. It does trace to the Technical Requirements ("A test asserts both"), so it is not scope creep.

### [PASS] Success-criteria coverage for Sections 1–5

The following slice criteria map to tasks:
- Every fixture parses, with the table-driven expectations: Task 3.5.
- Both provider-failure files: Task 3.5.
- *Findings Not Parsed*, with the edited-copy known gap: Tasks 1.3 and 3.5.
- PR review with `pr:` ignored: Task 3.5.
- 0.15.0 `sq_run_id` and stamp: Task 3.5.
- Stdout captures, the `findings_parsed` branches, and `requested_model` handling: Task 4.2.
- File/stdout finding-key equality on the new pair, and `template_name` equal to `reviewType`: Tasks 1.2 and 4.2.
- Record-id stability under hand edits, and change under summary edits: Task 5.2.
- All listed `SquadronParseError` and `UpstreamVersionError` cases: Tasks 3.3, 3.5, 4.2, and 5.4.
- `provider_failure_problem` as the single definition: Tasks 2.2 and 2.3.
- Import direction and single key definitions: Task 5.5.
- PyYAML as a runtime dependency: Task 2.1.

I found no scope creep in Sections 1–5.

### [PASS] Sequencing, test-with pattern, and commit cadence

Dependencies run in a single chain, with no cycles. Fixtures come before the code that reads them. PyYAML moves to runtime before the first `import yaml`. Each implementation task is followed immediately by its test task and committed with it (3.2/3.3, 3.4/3.5, 5.1/5.2, 5.3/5.4). Commits land throughout the file, not batched at the end. The task file states its commit rule explicitly. Tasks 1.1 and 1.2 have sensible "stop and ask the PM" guards. These cover a hand-edited fixture, a missing `sq`, and non-JSON stdout, and they prevent hand-built fixtures.

### [PASS] No NFR or load-test obligation

The slice design restates no performance or load NFR. No `tests/load/` task or CI-gating task is required for this breakdown.

### Run Digest

- Response length: 7582 chars
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
- Duration: 56.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
