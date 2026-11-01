---
docType: review
layer: project
reviewType: arch
slice: question-answerer
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/architecture/140-arch.question-answerer.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 41c0ed55a411da9d07c2d3e04ae0e84c8c42c06e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
turns: 11
promptTokens: 436104
cachedTokens: 338917
cacheWriteTokens: 97173
completionTokens: 6383
durationSeconds: 80.3
costUsd: 0.973689
costBasis: provider
squadronVersion: 0.24.11
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "An `sq_answer` entry on the slice node breaks both the answerer's resume and the PM's resume"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F002
    severity: fail
    category: consistency
    summary: "The stale-precedent defence relies on a check that cannot see the newer rule"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F003
    severity: concern
    category: completeness
    summary: "The PM has no handle on a `JUDGE` block, so the \"PM wins\" race cannot happen as written"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F004
    severity: concern
    category: completeness
    summary: "The new stage's place in the tick, and how its runs are observed and ingested, are not specified"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F005
    severity: concern
    category: completeness
    summary: "The question-record transitions and inbox submissions are not stated to be atomic"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#architectural-principles"
  - id: F006
    severity: concern
    category: completeness
    summary: "Where the PM-reserved screen's list comes from is undefined"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F007
    severity: note
    category: feasibility
    summary: "Prior-answer passages grow without bound"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F008
    severity: note
    category: completeness
    summary: "Questions that arrive while a node is already blocked are lost"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
---

# Review: arch — initiative 140

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] An `sq_answer` entry on the slice node breaks both the answerer's resume and the PM's resume

The document journals the answering run "as a journaled `sq_answer` entry on the slice node" (Envisioned State step 3). Its only warning is that the entry "must not be mistaken for the slice's pipeline run when the supervisor finds the slice's latest `sq_run`". The code has the opposite problem. It does not look for the latest `sq_run`. It looks at the latest entry of any kind:

- **The PM's resolution is rejected while an answering run is in flight.** `runner/resolutions/classify.py:24-26` returns `Situation.UNRESOLVABLE` whenever the slice's latest entry is unresolved. `judge.py:67-71` then rejects the PM's resolution. Step 7 says "the PM wins: the tick applies the PM's resolution first". In fact the PM's resolution is rejected and the node is blocked again with `resolution_rejected`.
- **The answerer's resolution fails after the answering run ends.** `supervise.run_to_resume` (`supervise.py:199-205`) returns `None` unless the latest entry is a resolved `sq_run`. Once `sq_answer` resolves, it is the latest entry, so the situation becomes `NO_RUN`. A `resume` with instructions is then rejected as `instructions_not_applicable` (`judge.py:80-84`). The happy path of step 6 never resumes anything.
- **Other code makes the same latest-entry assumption.** `dispatch/hold.py` and `dispatch/state.py` filter on `SQ_RUN`, and `ingest/record.py` counts resumes from `SQ_RUN` entries. Any reader that takes "latest entry" without filtering by kind will misread the slice.

The architecture has to pick one of two fixes, because it decides the journal contract:
- change `classify` and `run_to_resume` (and every latest-entry reader) to filter by kind, or
- journal `sq_answer` somewhere other than the slice node.

Either way it changes code 132 owns. That contradicts "nothing else in the supervisor changes shape".

### [FAIL] The stale-precedent defence relies on a check that cannot see the newer rule

"Stale precedent" says that "a newer rule outweighs an older answer through the two checks rather than through an invalidation scheme". The Architectural Principles say the check step "sees only the question, the answer and the cited passages". So when the answer step cites only an old dated PM or answerer answer, the check step never sees the newer rule that contradicts it. Both checks pass:
- the cited id exists;
- the cited passage does settle the question as stated.

The only thing that can weigh new against old is the answer step, which is the very party the checks are meant to doubt. Either the check step needs more than the cited passages (for example, every passage from the same source, or all current rules passages), or there has to be a mechanical rule that a prior-answer passage alone cannot ground an answer.

### [CONCERN] The PM has no handle on a `JUDGE` block, so the "PM wins" race cannot happen as written

Step 1 writes a `JUDGE` block "with no payload, because the record holds the question". In `store/_block_writer.py:35`, `ESCALATING_KINDS` is only `{HUMAN}`, so a `JUDGE` block writes no escalation message. As a result:
- 132's blocked listing and 160's notification source, which both read escalations, will not show the block;
- the PM has no escalation to answer and no question text to read.

Step 7's race ("PM resolves the block while an answering run is in flight") assumes the PM can see and target the block. "The store change" says the listing "must show both kinds", but that is a change to the listing's query and to inspection. It is not the one new store operation the document describes. Say:
- how a `JUDGE` block appears to the PM and with what text (read from the question record?);
- whether the inbox accepts a submission against a block that has no escalation row.

### [CONCERN] The new stage's place in the tick, and how its runs are observed and ingested, are not specified

"A stage after observe and ingest" leaves the hard part to chance. In `tick.py`:
- `_run_entries` (`tick.py:220-225`) observes only `SQ_RUN` entries;
- finished runs flow straight into `record_finished` and 132's outcome classification;
- launches happen only in `ActStage`, under the budget and fault context.

`sq_answer` therefore needs four things the document does not mention:
- observation, either by widening the observer's filter or with a second observer pass;
- an explicit exclusion from `record_finished` and outcome classification, or a parallel ingest path;
- a launch path through `ActStage`, or a second subprocess-issuing stage;
- a decision about where the `JUDGE` block is written. Today `ingest/outcome.py:126` writes `HUMAN` inside 132's outcome plan, so writing `JUDGE` there edits the outcome map that the design goal says "does not change".

Name the modules this touches and the order of events inside one tick.

### [CONCERN] The question-record transitions and inbox submissions are not stated to be atomic

"The record is the memory" covers crash recovery for in-flight `sq_answer` runs. It does not cover the steps after the run ends:
- submit the resolution and move the record to `answered`;
- run the decline store operation and move the record to `declined`;
- discard the result and record "PM answered first".

If a crash lands between the submission and the record update, the answer can be submitted twice, which also counts twice against the per-run limit. A crash in the other order can leave the record `answered` with nothing in the inbox, and the slice stays blocked on `JUDGE` forever. State that each transition commits in the same store transaction as its submission or block change, and that the gate's answer count is read from the record within that transaction.

### [CONCERN] Where the PM-reserved screen's list comes from is undefined

"The reserved list lives in each project's rules as prose", yet "a deterministic screen on the question and the answer catches the obvious cases". A deterministic screen needs a concrete pattern set. The document does not say where it comes from:
- hard-coded in Amoeba, which would be a scattered magic list against the project rules;
- per-project configuration beside the pipeline;
- parsed from `CLAUDE.md`, which is fragile prose parsing.

This screen is one of two safeguards behind "no shadow mode", and it ships in the deterministic slice, so it has to be defined before that slice is designed. "Together they do [bound it]" is asserted, not shown. The check step is told to refuse reserved actions, but it is an LLM judging passages that may not mention the reservation at all.

### [NOTE] Prior-answer passages grow without bound

"The project's prior questions and answers" are included as passages, and the record only grows, so the dispatch will eventually overflow. "How prior answers are selected" is deferred to the slice, which is reasonable. Note, though, that any selection rule (most recent N, same slice or initiative) feeds straight into the stale-precedent finding above, because what is left out cannot be weighed.

### [NOTE] Questions that arrive while a node is already blocked are lost

`ingest/record.block_once` does nothing if the node is already blocked. If a `QUESTION` outcome arrives on a node that is already blocked (for example by a status or fault block), no `JUDGE` block is written. Step 1 also does not say whether the question record is still written in that case. Say which happens, so the record does not silently miss questions.

I made no changes to any files.

### Run Digest

- Response length: 8631 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 436104 / 338917 / 97173 / 6383 / not computed
- Duration: 80.3 s
- Cost: $0.97 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
