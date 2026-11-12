---
docType: review
layer: project
reviewType: slice
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: d87fc2dbbddab51ec2c709790f093db313be4b56
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 30
turns: 20
promptTokens: 1364908
cachedTokens: 1090048
completionTokens: 206772
reasoningTokens: 202882
durationSeconds: 1088.2
costUsd: 0.143134
costBasis: alias_pricing
runId: run-20261112-p4-1fa91a7d
squadronVersion: 0.24.27
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "The \"both stores exist and differ\" state has no exit but a human with no command"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:167"
  - id: F002
    severity: concern
    category: under-specification
    summary: "`status` grows by an uncapped number of 30-second `poll_run` subprocess calls, with no stated cap or target"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:200"
  - id: F003
    severity: note
    category: hidden-dependency
    summary: "A pruned resume log leaves `answers.resume_log` pointing at a file that no longer exists"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:265"
  - id: F004
    severity: note
    category: documentation
    summary: "Dangling cross-reference in D2"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:167"
  - id: F005
    severity: note
    category: architectural-boundary
    summary: "The `questions` rebuild in `003` is a live exception to a rule two completed slices rely on, recorded only in the migration file"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:171-185"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Scope, dependency direction and the architecture's principles are respected"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md"
---

# Review: slice — slice 228

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The "both stores exist and differ" state has no exit but a human with no command

D2 says that when a legacy store and a state-home store both exist and differ, the call raises `StoreRelocateError` "naming both paths, their row counts and their `MAX(answers.seq)`, and change nothing", and "The message says to remove the copy that should not be kept." That leaves `~/.config/amoeba/amoeba.sqlite3` and `<state>/amoeba.sqlite3` in conflict and tells the operator to delete a file by hand. The design's own rules (Amoeba Design Rules: "Every state has an exit… 'wait for a person who has no command to act with' is not an answer") forbid exactly this, and the state is reachable without PM action (crash between steps 4 and the delete, or an old install writing to the legacy path after the move — both named in the same paragraph). The design should give this state a command or an automatic rule: for example a `state_move --keep-legacy` / `--keep-new` style resolution, or a rule that the state-home store wins and the legacy file is renamed aside with a message naming the aside path (which is itself reversible), rather than a bare stop. This is the only state in the slice with no command-driven way out; D4/D5/D6/D9 all give theirs one.

### [CONCERN] `status` grows by an uncapped number of 30-second `poll_run` subprocess calls, with no stated cap or target

D4 has `sweep_scope` poll once per open question whose run is missing from the listing (`completed` runs are not listed, 224 D1), and the Integration Points section states the consequence only qualitatively: "The bound on `status`'s time grows by one `poll_run` per open question whose run is missing from the listing, and those rows close in that call" (line 335). Each such poll is a `sq` subprocess bounded by `deps.RUN_POLL_TIMEOUT_SECONDS` (30 s, `src/amoeba/operations/deps.py`). Nothing bounds the *count*: after a busy period there can be many open waiting rows whose runs are unlisted, and one `status` call then costs a multiple of 30 s. This matters because 226 must call `status` in-process under the MCP client's timeout, and the architecture/doc set makes bounded `status` the contract. The design already decided that these rows close on their first sighting; it should say what the specific bound is (a maximum number of polls per call, the order they are chosen in, and what the remaining rows report — presumably `run_state: unknown` with a reason) and restate the target that bound protects. Without that, this is the slice's one new path whose worst-case latency is unbounded and unstated.

### [NOTE] A pruned resume log leaves `answers.resume_log` pointing at a file that no longer exists

D9 removes `logs/resume/<run_id>/` files for runs with no open question, while `answers.resume_log` is a stored column naming the stdout log (223 D10). The architecture's "An exact record" goal (220-arch.program-tool.md, Design Goals) is met for the answer text, but the record keeps a stale path. The doc should say what a reader of that column sees once pruning has run (for example that `decisions` prints the path as stored and a missing file is not an error), or state why the path is kept as history. Otherwise 224's `decisions` output and `docs/store-contract.md` imply a file that may be gone.

### [NOTE] Dangling cross-reference in D2

D2 justifies the differ-and-stop choice with "(see \"weigh by likelihood\")". No section of that name exists in the slice document (sections are Overview, Value, Technical Scope, Dependencies, Architecture, Technical Decisions D1–D13, Implementation Details, Integration Points, Success Criteria, Risk Assessment, Implementation Notes). Either the rationale was cut and the reference was not, or it points at a section that should exist. Since the sentence is what justifies stopping on a differing double store, restore the rationale or drop the reference.

### [NOTE] The `questions` rebuild in `003` is a live exception to a rule two completed slices rely on, recorded only in the migration file

D3 rebuilds `questions` (drop, rename) to widen the `state` `CHECK`, which contradicts 222 D3 ("Later migrations use only `ALTER TABLE … ADD COLUMN`, so no table is rebuilt") and every migration since. The design argues the alternative (a `closed_at` column beside an unchanged `state`) correctly and says the migration's header comment explains why, and D13 updates `docs/store-contract.md`. Because 222 and 223 are complete and their docs cannot be edited, the exception should also be stated where the next migration author will look — the store contract description of the migration rule itself — so `ADD COLUMN` remains the default rather than becoming the historical note. The foreign-key handling (`foreign_keys = OFF` outside the transaction, `foreign_key_check` before commit) is otherwise correct for this rebuild: `answers` references `questions (run_id, paused_at)`, which the primary key of the rebuilt table still provides.

### [PASS] Scope, dependency direction and the architecture's principles are respected

Every item in the slice-plan entry for 228 is present: state moves out of `~/.config` with `config.yaml` left behind, a moved store verified before deletion, `dismiss`/`retract`, automatic closing in `status` and `handle_pause`, the answer limit reset by a PM answer, `set_up` removal, age-based pruning, `wrong_checkout`, and the calls log, with `AMOEBA_HOME` still redirecting both homes for tests. Nothing in the architecture is contradicted: no background process or watcher is introduced (explicitly excluded, and every cleanup runs inside an existing call), run state and slice state are still read from Squadron and Context Forge rather than mirrored, the call log is a record of Amoeba's own calls rather than mirrored run state, and the new `status` write is a store-only compare-and-set that the slice plan assigns to this slice. New I/O paths each name their failure handling (verified copy before delete, `PollFailure` leaves the row open and shows the error, per-entry `OSError` in prune, a calls-log write failure that leaves the exit code unchanged, `last_call` never raising), and the new vocabularies are single `StrEnum`s pinned by the existing test.

### Run Digest

- Response length: 7690 chars
- Response is newline-free: no
- Tool calls made: 30
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 835585
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1364908 / 1090048 / not computed / 206772 / 202882
- Duration: 1088.2 s
- Cost: $0.14 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

### Raw Response

## Summary
[overall assessment: CONCERNS]

The design is well aligned with the parent architecture: it adds no resident process or watcher, keeps run state in Squadron and slice state out of the store, keeps the single-store/one-env-var rule, preserves the documented import direction (`cli → operations → store, config, upstream`, with `store/relocate.py` taking both paths so `store` still imports nothing from `config`), and states failure handling for each new I/O path (move verified before delete, `PollFailure` leaves rows open, per-entry `OSError` in prune, calls-log write failure that does not change the exit code). It also restates the parent plan's items in its own scope. Two concerns and three notes follow.

## Findings

### [CONCERN] The "both stores exist and differ" state has no exit but a human with no command
category: error-handling
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:167

D2 says that when a legacy store and a state-home store both exist and differ, the call raises `StoreRelocateError` "naming both paths, their row counts and their `MAX(answers.seq)`, and change nothing", and "The message says to remove the copy that should not be kept." That leaves `~/.config/amoeba/amoeba.sqlite3` and `<state>/amoeba.sqlite3` in conflict and tells the operator to delete a file by hand. The design's own rules (Amoeba Design Rules: "Every state has an exit… 'wait for a person who has no command to act with' is not an answer") forbid exactly this, and the state is reachable without PM action (crash between steps 4 and the delete, or an old install writing to the legacy path after the move — both named in the same paragraph). The design should give this state a command or an automatic rule: for example a `state_move --keep-legacy` / `--keep-new` style resolution, or a rule that the state-home store wins and the legacy file is renamed aside with a message naming the aside path (which is itself reversible), rather than a bare stop. This is the only state in the slice with no command-driven way out; D4/D5/D6/D9 all give theirs one.

### [CONCERN] `status` grows by an uncapped number of 30-second `poll_run` subprocess calls, with no stated cap or target
category: under-specification
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:200

D4 has `sweep_scope` poll once per open question whose run is missing from the listing (`completed` runs are not listed, 224 D1), and the Integration Points section states the consequence only qualitatively: "The bound on `status`'s time grows by one `poll_run` per open question whose run is missing from the listing, and those rows close in that call" (line 335). Each such poll is a `sq` subprocess bounded by `deps.RUN_POLL_TIMEOUT_SECONDS` (30 s, `src/amoeba/operations/deps.py`). Nothing bounds the *count*: after a busy period there can be many open waiting rows whose runs are unlisted, and one `status` call then costs a multiple of 30 s. This matters because 226 must call `status` in-process under the MCP client's timeout, and the architecture/doc set makes bounded `status` the contract. The design already decided that these rows close on their first sighting; it should say what the specific bound is (a maximum number of polls per call, the order they are chosen in, and what the remaining rows report — presumably `run_state: unknown` with a reason) and restate the target that bound protects. Without that, this is the slice's one new path whose worst-case latency is unbounded and unstated.

### [NOTE] A pruned resume log leaves `answers.resume_log` pointing at a file that no longer exists
category: hidden-dependency
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:265

D9 removes `logs/resume/<run_id>/` files for runs with no open question, while `answers.resume_log` is a stored column naming the stdout log (223 D10). The architecture's "An exact record" goal (220-arch.program-tool.md, Design Goals) is met for the answer text, but the record keeps a stale path. The doc should say what a reader of that column sees once pruning has run (for example that `decisions` prints the path as stored and a missing file is not an error), or state why the path is kept as history. Otherwise 224's `decisions` output and `docs/store-contract.md` imply a file that may be gone.

### [NOTE] Dangling cross-reference in D2
category: documentation
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:167

D2 justifies the differ-and-stop choice with "(see \"weigh by likelihood\")". No section of that name exists in the slice document (sections are Overview, Value, Technical Scope, Dependencies, Architecture, Technical Decisions D1–D13, Implementation Details, Integration Points, Success Criteria, Risk Assessment, Implementation Notes). Either the rationale was cut and the reference was not, or it points at a section that should exist. Since the sentence is what justifies stopping on a differing double store, restore the rationale or drop the reference.

### [NOTE] The `questions` rebuild in `003` is a live exception to a rule two completed slices rely on, recorded only in the migration file
category: architectural-boundary
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:171-185

D3 rebuilds `questions` (drop, rename) to widen the `state` `CHECK`, which contradicts 222 D3 ("Later migrations use only `ALTER TABLE … ADD COLUMN`, so no table is rebuilt") and every migration since. The design argues the alternative (a `closed_at` column beside an unchanged `state`) correctly and says the migration's header comment explains why, and D13 updates `docs/store-contract.md`. Because 222 and 223 are complete and their docs cannot be edited, the exception should also be stated where the next migration author will look — the store contract description of the migration rule itself — so `ADD COLUMN` remains the default rather than becoming the historical note. The foreign-key handling (`foreign_keys = OFF` outside the transaction, `foreign_key_check` before commit) is otherwise correct for this rebuild: `answers` references `questions (run_id, paused_at)`, which the primary key of the rebuilt table still provides.

### [PASS] Scope, dependency direction and the architecture's principles are respected
category: architecture-alignment
location: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md

Every item in the slice-plan entry for 228 is present: state moves out of `~/.config` with `config.yaml` left behind, a moved store verified before deletion, `dismiss`/`retract`, automatic closing in `status` and `handle_pause`, the answer limit reset by a PM answer, `set_up` removal, age-based pruning, `wrong_checkout`, and the calls log, with `AMOEBA_HOME` still redirecting both homes for tests. Nothing in the architecture is contradicted: no background process or watcher is introduced (explicitly excluded, and every cleanup runs inside an existing call), run state and slice state are still read from Squadron and Context Forge rather than mirrored, the call log is a record of Amoeba's own calls rather than mirrored run state, and the new `status` write is a store-only compare-and-set that the slice plan assigns to this slice. New I/O paths each name their failure handling (verified copy before delete, `PollFailure` leaves the row open and shows the error, per-entry `OSError` in prune, a calls-log write failure that leaves the exit code unchanged, `last_call` never raising), and the new vocabularies are single `StrEnum`s pinned by the existing test.
