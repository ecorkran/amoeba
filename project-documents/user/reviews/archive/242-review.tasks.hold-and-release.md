---
docType: review
layer: project
reviewType: tasks
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/242-tasks.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: cbff187dd26c1d6006c198d1ea1e02cb78472a31
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 39
effort: xhigh
turns: 40
promptTokens: 2309053
cachedTokens: 2088912
cacheWriteTokens: 220111
completionTokens: 111019
durationSeconds: 488.3
costUsd: 0.589651
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "No test that held answering runs and resumes happen outside a store transaction"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:132-135"
  - id: F002
    severity: concern
    category: coverage
    summary: "`rm` of the addressee is never checked against its reason"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:170"
  - id: F003
    severity: concern
    category: coverage
    summary: "A refused-resume retry has no test for held questions"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:191"
  - id: F004
    severity: concern
    category: verification
    summary: "The final-verification lists do not match what the tasks edit"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:232"
  - id: F005
    severity: concern
    category: process
    summary: "Section 10's commit marker has nothing to commit, and section 9's commit has the wrong type"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:236"
  - id: F006
    severity: concern
    category: trap
    summary: "The live-store check gives the expected value beside a query that may return nothing"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:243"
  - id: F007
    severity: concern
    category: sizing
    summary: "No task splits modules that are over the size limit"
    location: "src/amoeba/wiring.py"
  - id: F008
    severity: concern
    category: docs
    summary: "The request-result passage kind is not documented"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:214"
  - id: F009
    severity: note
    category: sequencing
    summary: "The prerequisite check misses 240's test files, and step 54 offers two methods"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:53"
  - id: F010
    severity: note
    category: naming
    summary: "Names and signatures drift from the design and the code"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:88"
  - id: F011
    severity: note
    category: sequencing
    summary: "The source of `Deps.amoeba_script` is not stated"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:157"
  - id: F012
    severity: note
    category: sizing
    summary: "`status` and `list` gain up to `START_BOUND_SECONDS` with no bound check"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:171"
  - id: F013
    severity: note
    category: process
    summary: "The backup step has no `mkdir -p`"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:245"
  - id: F014
    severity: note
    category: docs
    summary: "The candidate-answer sentence is in the plan, not the architecture"
    location: "project-documents/user/architecture/240-slices.agent-messaging.md:66"
  - id: F015
    severity: note
    category: scope
    summary: "Density, an extra test, and a placeholder arm"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:149"
  - id: F016
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md"
  - id: F017
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and gating are sound"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:51"
  - id: F018
    severity: pass
    category: verification
    summary: "Cited paths and symbols exist, and release-log cleanup holds"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:59"
  - id: F019
    severity: pass
    category: process
    summary: "Amoeba design rules hold, with one exit gap"
    location: "project-documents/user/tasks/242-tasks.hold-and-release.md:240"
---

# Review: tasks — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] No test that held answering runs and resumes happen outside a store transaction

The slice design's Technical Requirement (`project-documents/user/slices/242-slice.hold-and-release.md:294`) says no store transaction is open while an answering run, a resume or a release spawn runs. Only 6.3 (line 164) tests this, and only for the release spawn. Nothing in 4.3 or 5.3 asserts it for the held claim. 5.1 (line 143) says `handle_held` reads "in one read transaction, then acts" but does not say that transaction closes before `start_held_claim` runs `cf` and `sq`. Add the assertion to 4.3 and state the close in 5.1.

### [CONCERN] `rm` of the addressee is never checked against its reason

The design (line 279) and D8 (line 217) require `rm` of the addressee to move the held question to `waiting_on_pm` with `request_cancelled`, and to put `member_removed` in `waiting_detail`. 6.5 (line 170) checks only that the held question is started afterward. 5.3 (line 149) covers decline, cancel, expiry and pruning. The `test_rm.py` item in 1.5 covers the sender side. Add the addressee case to 5.3 with both the reason and the detail.

### [CONCERN] A refused-resume retry has no test for held questions

D7 (design line 209) and the Operator Walkthrough (line 348) make a refused resume an exit for a held question: the status shows `answered_unresumed` with `next = handle_pause`, and the retry starts no new answering run. The parent plan's criterion says the same (`project-documents/user/architecture/240-slices.agent-messaging.md:73`). The exit list in 7.4 omits it. Add a held-question test, or name the existing 223 test that covers this path with a held fixture.

### [CONCERN] The final-verification lists do not match what the tasks edit

10.2 gives a fixed list of edited existing code and says "the only edited existing tests are the pins and builders named in tasks 1.1, 1.3, 6.1 and 6.5". The tasks edit more than that. Code missing from the list: `store/vocabulary.py` and `store/migrations.py` (1.1), `store/models.py` and `store/question_rows.py` (1.3), `operations/pause_models.py` (2.6), and `operations/pause_context.py` (4.1). Tests missing from the exception: `test_vocabulary_pinning.py` (1.2), five existing files in 1.5, `test_pipeline_yaml.py` (2.5), `test_pause_existing.py` (4.3), the status and decisions files (7.2 and 7.3), the dismiss, answer and exits files (7.4), and `test_program_rules_doc.py` (9.1). An agent following 10.2 will fail its own check or mark it wrong. Derive the list from the tasks, or check with `git diff --stat {target}`.

### [CONCERN] Section 10's commit marker has nothing to commit, and section 9's commit has the wrong type

CLAUDE.md says never to make a commit that only checks boxes or only adds notes. Section 10 changes no code. 10.1 records a rehearsal in notes, and 10.2 checks boxes and records a commit in the slice notes. Remove the marker at line 236 and run section 10 before the section 9 commit (line 221), so its check-offs and notes ride in that commit. Also, 9.1 (line 210) changes the MCP `INSTRUCTIONS` constant in `src/amoeba/mcp/server.py:51` and its tests, but that commit is typed `docs:`. Type it `feat:` or split it out.

### [CONCERN] The live-store check gives the expected value beside a query that may return nothing

P7.1 reads `schema_meta.version` from the live store and says an empty result is BLOCKED. The same line supplies the expected answer in brackets, "(241's, 7)". That is the nearest plausible token the project's rule warns about. P7.3 (line 250) does the same with "is 8". Define the expected value as the last migration file number in `store/schema/` before 008, computed from the directory listing. Compare P7.3 to `EXPECTED_SCHEMA_VERSION`. An empty or unexpected result should stop the step.

### [CONCERN] No task splits modules that are over the size limit

`wiring.py` is 342 lines. 6.4 (line 167) adds `START_AFTER_OPERATIONS`, the call in `invoke` and the `handle_pause` call, and the task context (line 39) says a module over about 300 lines is split by concern. Move the constant and the start call into `operations/request_release.py` so `wiring.py` grows by two or three lines. `operations/pause_claim.py` is 233 lines, and 4.1 and 4.2 add the held path to it. The design (line 67) keeps that path beside the private `_prepare` and `_run`. Decide in 4.1 whether to accept the overrun with a note or to expose the helpers.

### [CONCERN] The request-result passage kind is not documented

The design's Technical Requirement (line 296) requires every new kind to be documented. 9.2 names no document for `request_result`. `docs/rules.md:80` describes how passages are dropped ("Plan and program passages are never dropped"), and the new passage is never trimmed. Add `docs/rules.md` to 9.2 and state the kind there. `tests/test_contract_docs.py` does not check passage kinds, so the requirement is met only if the task adds the text.

### [NOTE] The prerequisite check misses 240's test files, and step 54 offers two methods

Step 53 does not check `tests/store/test_migration_006.py`, which 1.2 models its test on, or `tests/test_message_timing.py`, which 6.5 edits. Neither exists yet, which is expected for 240's output, so add both to the BLOCKED check. Step 54 says to run the live fixture "(or read ...)". Choose the read of `tests/live/answering/question_tails.py`, which spends nothing. Also, D1 reads the whole text, so this note cannot change any decision. Say so, or cut the step.

### [NOTE] Names and signatures drift from the design and the code

2.1 gives `find_request_link(question, resolve)`. The design's Component Structure (line 86) gives `find_request_link(question)`. The callable keeps the function pure, which is the right call, so record the change in the design under 9.3. 4.1 (line 127) refers to "the 223 `pause_claim` tests", but no test references `pause_claim`, `start_new_claim` or `restart_dead_claim`. The claim paths are tested through the `handle_pause` tests, so name those files. 1.5 (line 80) says "`test_rm.py` (or the `member_open_questions` test)". Choose one.

### [NOTE] The source of `Deps.amoeba_script` is not stated

`production_deps` is at `src/amoeba/operations/deps.py:74`, inside the operations layer, which may not import `mcp`. 6.1 says `production_deps` sets the callable but not where the callable comes from. Say that `production_deps` imports the root module `amoeba_script`, and that the root module imports nothing from the layers, so `tests/test_import_boundaries.py` stays green.

### [NOTE] `status` and `list` gain up to `START_BOUND_SECONDS` with no bound check

6.4 (line 167) runs the start after `status` and `list` too. 6.5 adds `START_BOUND_SECONDS` only to `send`, `reply` and `cancel`. The design calls `status` and `list` "outside that bound already", which was true only before this slice. The 226 deadline wrapper still caps the call and names the CLI as the fallback, so this is a timeout risk rather than a broken requirement. Say so in 6.5, or add the arithmetic.

### [NOTE] The backup step has no `mkdir -p`

240's hand-off (`project-documents/user/tasks/240-tasks.requests.md:311`) creates `~/.local/state/amoeba/backups/` with `mkdir -p`. This step works only because 240 has already run. Add the same `mkdir -p`.

### [NOTE] The candidate-answer sentence is in the plan, not the architecture

9.3 (line 217) asks for the architecture's sentence to be reworded in both 240 documents. "makes its result the candidate answer" appears only in `240-slices.agent-messaging.md:66`. `240-arch.agent-messaging.md:156` already says the result "is given to the answering pipeline as a passage". Name the file that needs rewording. The quote "Independent of 241" at `240-slices.agent-messaging.md:77` is accurate.

### [NOTE] Density, an extra test, and a placeholder arm

5.3 packs about eight scenarios into one checkbox. Split it by outcome so each can be checked. 7.1 (line 179) touches five status modules in one bullet. 1.2 (line 67) tests the existing newer-schema refusal, which no criterion asks for. Keep it only if it is cheap. 1.4 (line 74) commits a `NotImplementedError` arm that 5.2 removes. It is unreachable before 5.2 and pyright needs an arm, so accept it, and record in the task note that it is temporary.

### [PASS] Success criteria trace to tasks

Each of the 13 functional and 6 technical criteria maps to a named test or live step, except the gaps above. Examples: link shapes (2.2), migration 8 on a populated v7 store (1.2), the three live replies (8.2), the start trigger through both doors (6.5), the race (5.3), every held exit (7.4), and the cap and never-attempted-first order (6.3). No task adds a feature the design does not name.

### [PASS] Sequencing, test-with pattern, and gating are sound

Dependencies run in one direction: vocabulary and migration (1), then pure link and passage (2), store (3), claim (4), hold (5), start trigger (6), status and decisions (7), live (8), docs (9). Each implementation section ends with its tests. 0.1 stops the work if 240 or 241 is missing. The only commit-cadence problem is the section 10 marker above.

### [PASS] Cited paths and symbols exist, and release-log cleanup holds

I checked the modules, symbols and test helpers the tasks name. These include `store/schema/001`–`005`, `QUESTION_COLUMNS`, `_OPEN_QUESTION_CLAUSE`, `_OPEN_PARAMETERS`, `dismiss_question`, `_prepare`, `_settle_dead_claim_waiting`, `wiring.invoke`, `MISSED_HOOK_CLASSES`, `resolve_amoeba_script` in `mcp/detached.py`, `result_entry` and `error_entry` in `operations/calls_log.py`, `Deps.logs_dir`, and the helper files in 0.1. `optional_text` and `optional_timestamp` live in `store/row_values.py`, which 1.3 should name. The 240 outputs (`store/messages.py`, migrations 006 and 007, and two 240 tests) are absent, as expected. `prune` walks all of `logs/`, so `logs/request-release/` is cleaned up without change.

### [PASS] Amoeba design rules hold, with one exit gap

No task defers in-scope behavior or waits on real use. The live tier uses fixtures. The Phase 7 waits are bounded by `answering_wait_seconds` or the 60-second limit. Config stays in the config home, and the held-question record and logs stay in the state home. Every state has an exit except the refused-resume case above. The Phase 7 steps have a restore path.

### Run Digest

- Response length: 15831 chars
- Response is newline-free: no
- Tool calls made: 39
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 40
- Tokens — prompt / cached / cache write / completion / reasoning: 2309053 / 2088912 / 220111 / 111019 / not computed
- Duration: 488.3 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19
