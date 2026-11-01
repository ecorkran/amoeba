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
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/140-arch.question-answerer.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 868d602388f1fc174cb6606e7cb85502b1e25bbe
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
turns: 10
promptTokens: 506657
cachedTokens: 423586
cacheWriteTokens: 83055
completionTokens: 6953
durationSeconds: 81.1
costUsd: 0.889087
costBasis: provider
squadronVersion: 0.24.11
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "A PM answer that makes an exception to a rule can never become precedent"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#architectural-principles"
  - id: F002
    severity: concern
    category: feasibility
    summary: "\"An answer dropped for size can only cause an unnecessary decline\" is false"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F003
    severity: concern
    category: technology
    summary: "\"Submit and mark answered in one transaction\" doesn't fit the inbox's transaction model, and the submission can be rejected"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#architectural-principles"
  - id: F004
    severity: concern
    category: abstraction
    summary: "Telling PM precedent from answerer answers by `submitted_by` breaks the store's contract"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F005
    severity: concern
    category: consistency
    summary: "An over-limit run can't \"block with every question and answer in the payload\""
    location: "project-documents/user/architecture/140-arch.question-answerer.md#architectural-principles"
  - id: F006
    severity: concern
    category: completeness
    summary: "Answerer-off projects and already-resolved pending questions are not handled"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F007
    severity: note
    category: feasibility
    summary: "The answering stage has no concurrency bound"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F008
    severity: note
    category: consistency
    summary: "Leftover \"Otherwise\" in step 3"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F009
    severity: note
    category: consistency
    summary: "Writing the question record in ingest touches 132's outcome code"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#design-goals"
  - id: F010
    severity: note
    category: technology
    summary: "Finding \"the rule files it names\" means parsing prose"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
---

# Review: arch — initiative 140

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] A PM answer that makes an exception to a rule can never become precedent

The check step must confirm that "no other passage contradicts the answer". "Stale precedent and growth" counts on this, so that a newer rule beats an older PM answer. The check has no way to tell which passage is newer or carries more authority, so it also works the other way round. When the PM answers against a rule or design passage on purpose ("ignore the design here, keep the old API"), that rule stays in the passage set. It contradicts the PM's answer every time, so the check says no on every repeat, and the PM is asked again forever. That breaks the design goal "A question the PM already answered stays answered" for exactly the questions where precedent matters most. The architecture has to choose an ordering:
- A PM answer dated after the conflicting passage's last commit wins. The commit date is available, since sources come from `git show` on the target.
- Or the check is told the order in which passages take precedence.

Saying nothing leaves the outcome to the model's mood.

### [CONCERN] "An answer dropped for size can only cause an unnecessary decline" is false

The safety argument depends on the check step seeing every passage that could contradict an answer ("Because the check step sees the whole passage set…"). Once PM answers are trimmed ("most recent first, up to a configured size"), or rules and plan passages are cut down to fit one dispatch ("Assembling sources"), a contradicting passage can be the one that gets dropped. For example, an older PM answer that overrode a design passage is trimmed. The design passage is then uncontradicted, and the answerer confidently answers against what the PM decided. That is a wrong answer, not a decline. The answering slice gets the selection rule without being told what it must keep. At minimum, state that what gets trimmed is part of the risk model. Better, require any PM answer for the same slice, initiative or source path to be kept before others.

### [CONCERN] "Submit and mark answered in one transaction" doesn't fit the inbox's transaction model, and the submission can be rejected

`InboxOperations.apply_submission` (`src/amoeba/store/inbox.py:129-130`) opens its own `with self._connection:` and issues `BEGIN IMMEDIATE`. SQLite cannot nest that, so "submit the resolution and mark `answered`… in one store transaction" needs a new store operation in 100's store. That operation must run the resolution effect and the question-record update under one `BEGIN IMMEDIATE`, and read the answer count there too.

Also, `_apply_resolution` fills the block's resolution slot at submission time and returns a rejection reason if the block is already resolved (`inbox.py:227-230`). The "PM answered first" case is therefore usually found here, at submission, not by the answering stage beforehand. The combined operation must branch on the submission's outcome:
- `applied` → `answered`
- rejected because already resolved → "PM answered first"

Otherwise the record says `answered` for a rejected submission. The question record itself is a new 100 table with a migration. "The blocked listing" section's "No store change" reads as if 140 needs no store changes, and it does need them.

### [CONCERN] Telling PM precedent from answerer answers by `submitted_by` breaks the store's contract

Step 7 records a PM `resume` with instructions as precedent. The principles say "the answerer's own answers are never passages". Both arrive as the same `resolution` submission on the same `HUMAN` block, and the store documents `submitted_by` as "Free-form provenance. Never branched on" (`inbox.py:118`). 160's chat replies will add more `submitted_by` values. Telling the two apart by that string is the "user-accessible labels as logical structure" antipattern the project rules forbid, and it is the only thing that stops the answerer's answers from becoming precedent.

The fix is a structured origin, set by whoever writes the question record, not read back from the submission:
- the answerer writes `answered_by=answerer` itself, in the combined transaction above;
- step 7's ingestion marks a question answered by the PM only when its block's resolution came from a submission the answerer did not make, a rule the record itself can decide.

Write that rule down.

### [CONCERN] An over-limit run can't "block with every question and answer in the payload"

"One gate for every resolution" says a run past its answer limit "blocks with every question and answer in the payload". When the gate runs, the node already has 132's open `HUMAN` block for the current question. Step 1 itself notes that the store writes no second block on a blocked node (one open block per node). So no new payload can be written. The over-limit case can only decline, and the per-run history has to come from the question record through the listing and `amoeba inspect`. Change that sentence, or the gate slice will try to build a block write that cannot happen.

### [CONCERN] Answerer-off projects and already-resolved pending questions are not handled

Step 1 says "the question record is never skipped". "Recognising PM-reserved questions" says a project with no answerer section "behaves as 132 does". It is not said what state those records take. If they stay `pending`, the decline-based listing and 160's "notify on the declined state" never fire for answerer-off projects, so those questions vanish from the notification path.

Separately, step 2 launches an answering run for every `pending` question without first checking that its `HUMAN` block is still open. A PM reply that arrives through `serve` between ingest and the answering stage leads to a paid run whose result is always thrown away. Specify:
- an immediate decline (or a distinct state) when the answerer is off;
- an open-block check before launch.

### [NOTE] The answering stage has no concurrency bound

"Queue" takes "each `pending` question, in order". Answering runs hold no checkout, so the per-checkout limit that caps `sq_run` concurrency does not apply. A burst of questions across projects launches that many `sq` processes at once, limited only by the tick budget. A configured cap on concurrent `sq_answer` runs belongs with the other per-project answerer settings.

### [NOTE] Leftover "Otherwise" in step 3

Step 3 begins "Otherwise the answering stage assembles…", but no condition comes before it. This looks left over from the exact-match shortcut that the 20261101 revision removed. Delete it so readers don't go looking for a missing branch.

### [NOTE] Writing the question record in ingest touches 132's outcome code

"The outcome map does not change" lists only the new command kind and the latest-entry reader as changes to the supervisor. But "Order inside one tick" has 132's outcome path ("which also writes the question record on a `QUESTION`") also writing the record, and today that is the plan in `runner/ingest/outcome.py`. That makes a third change to 132-owned code. List it beside the other two.

### [NOTE] Finding "the rule files it names" means parsing prose

Step 3 builds rules passages from "`CLAUDE.md` and the rule files it names". In this project's own layout, rules come through `AGENTS.md`, `.claude/rules/*.md` and conditional per-language rule files listed by glob. None of that can be followed reliably by reading references out of `CLAUDE.md` prose. A configured list of rule paths, beside the reserved-terms list, avoids a fragile parser and fits the project's lenient-parsing rule.

### Run Digest

- Response length: 8885 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 506657 / 423586 / 83055 / 6953 / not computed
- Duration: 81.1 s
- Cost: $0.89 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
