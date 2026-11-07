---
docType: review
layer: project
reviewType: arch
slice: program-tool
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/architecture/220-arch.program-tool.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: cc4c1d0cde24167bd5578da48e78f7f46da0a2a4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 30
turns: 31
promptTokens: 804662
cachedTokens: 656665
cacheWriteTokens: 147981
completionTokens: 19007
durationSeconds: 190.4
costUsd: 1.69623
costBasis: provider
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "Resume is a foreground, long-running process, but scenario A says nothing is left running"
    location: "project-documents/user/architecture/220-arch.program-tool.md:102-110"
  - id: F002
    severity: concern
    category: completeness
    summary: "Nothing can retry a resume that didn't happen"
    location: "project-documents/user/architecture/220-arch.program-tool.md:129"
  - id: F003
    severity: concern
    category: consistency
    summary: "The \"run and checkpoint\" uniqueness key has no checkpoint id to use, and only covers Amoeba's own callers"
    location: "project-documents/user/architecture/220-arch.program-tool.md:128"
  - id: F004
    severity: concern
    category: consistency
    summary: "\"Bounded answers\" overstates what a resume can do"
    location: "project-documents/user/architecture/220-arch.program-tool.md:34"
  - id: F005
    severity: concern
    category: abstraction
    summary: "The kept answering code assumes things this design removes"
    location: "project-documents/user/architecture/220-arch.program-tool.md:53"
  - id: F006
    severity: concern
    category: completeness
    summary: "\"Member from the working directory\" has no defined mapping, and it breaks for worktrees and cwd-less agents"
    location: "project-documents/user/architecture/220-arch.program-tool.md:96"
  - id: F007
    severity: concern
    category: consistency
    summary: "One user-level config can't hold per-repo answer settings"
    location: "project-documents/user/architecture/220-arch.program-tool.md:114"
  - id: F008
    severity: concern
    category: feasibility
    summary: "The PM's reply path is undefined when the agent told is headless"
    location: "project-documents/user/architecture/220-arch.program-tool.md:98"
  - id: F009
    severity: concern
    category: feasibility
    summary: "Scenario B's steps don't fit a command step, and the provider's report has no content source"
    location: "project-documents/user/architecture/220-arch.program-tool.md:92-96"
  - id: F010
    severity: concern
    category: completeness
    summary: "\"Since the PM last looked\" has no owner"
    location: "project-documents/user/architecture/220-arch.program-tool.md:86"
  - id: F011
    severity: concern
    category: consistency
    summary: "The slice order leaves the first proof without its own recovery path and morning list"
    location: "project-documents/user/architecture/220-arch.program-tool.md:143-144"
  - id: F012
    severity: concern
    category: technology
    summary: "Blocking operations over MCP aren't addressed"
    location: "project-documents/user/architecture/220-arch.program-tool.md:40"
  - id: F013
    severity: concern
    category: consistency
    summary: "An interactive run gets taken over without the person knowing"
    location: "project-documents/user/architecture/220-arch.program-tool.md:32"
  - id: F014
    severity: concern
    category: completeness
    summary: "The hook's timing and process contract aren't specified"
    location: "project-documents/user/architecture/220-arch.program-tool.md:75"
  - id: F015
    severity: note
    category: other
    summary: "The program record still carries the removed requests model"
    location: "project-documents/user/architecture/220-arch.program-tool.md:94"
  - id: F016
    severity: note
    category: antipattern
    summary: "Proportionality is sound, but `mark_read` might not need to be separate"
    location: "project-documents/user/architecture/220-arch.program-tool.md:88-89"
---

# Review: arch — initiative 220

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] Resume is a foreground, long-running process, but scenario A says nothing is left running

Steps 5 to 7 have `handle_pause` resume the run and then exit with "Nothing is left running". But `sq run --resume` is the work run itself: it executes in that process and holds the run lock for the whole run (`squadron/cli/commands/run.py:1076-1085`). That leaves two options, and the document chooses neither:

- **Wait for it:** `handle_pause` lives for the rest of a possibly hours-long `p6` run, which breaks "exits when the call is done". An `answer` over MCP would hold a tool call open for the same time.
- **Detach it:** the failures that matter happen after Amoeba has gone. The lock refusal is raised at once in the child (`run_lock.py:8`), so nothing is left to write the "answered but not resumed" state that line 129 promises.

The same gap affects these:

- **Logs:** nothing says where the detached run's output goes.
- **Environment:** a resume started by an MCP server inherits that server's environment, not the original run's.

The design needs an explicit resume contract. One workable shape:

1. Spawn the resume detached, with a log path.
2. Wait a short time for the lock result or for the run state to change.
3. Have `status` work out "not resumed" by comparing the recorded answer with the run's current checkpoint, rather than relying on a written outcome.

### [CONCERN] Nothing can retry a resume that didn't happen

"It isn't retried in the background" is fine, but no foreground path is defined either. In the operations table:

- `answer` records a PM answer.
- `handle_pause` answers a question.

Neither says what happens when a question already has an answer and the run is still paused, whether from a refused resume or from a process that died between recording and resuming. A second `handle_pause` could spend money answering again, or could back off and leave the run stuck, because the claim is already settled. The operation needs a defined rule: reuse the recorded answer and only resume. The answer states also need to be listed (claimed, answered, resumed, escalated), since the principle at line 43 depends on them.

### [CONCERN] The "run and checkpoint" uniqueness key has no checkpoint id to use, and only covers Amoeba's own callers

Squadron's `CheckpointState` holds `reason`, `step`, `verdict` and `paused_at`, with no id (`pipeline/state.py:168-174`). The key has to be `(run_id, paused_at)` or similar, and that choice decides what counts as "the same question". Step and question text would wrongly merge an agent asking the same thing twice.

The constraint also misses people and agents who resume without Amoeba. An agent that launched `sq run`, or the PM at a terminal, can run `sq run --resume` while `handle_pause` is mid-answer. Amoeba would then resume a run that has moved on, delivering an answer to the wrong pause. Before any resume, including one from `answer`, the current checkpoint must be re-read and matched against the claimed key. "Still waiting" in the operations table needs this definition.

Dead-claim detection is also unspecified. "A claim whose process has died" needs a pid plus start time, or a lease, and it must handle the case where `handle_pause` died but its answering `sq run` child is still running. Otherwise a retake spends twice and produces two answers.

### [CONCERN] "Bounded answers" overstates what a resume can do

The goal and concept say an answer "can only resume the run that asked" and that a steered passage "can at worst produce a wrong reply". But `--instructions` "prepends text to every dispatch the resumed run makes" (`squadron/docs/PIPELINES.md:391`), and those dispatches have tools, commit code and can merge. So a passage that steers the tool-less answer step can reach a tool-using implement agent as trusted instruction text.

What is actually bounded is which run receives the answer, not what that run does with it. The reserved-term screen is the only deterministic mitigation, and it matches substrings only. The document should state this risk and say what the check step and the screen are relied on to catch.

The cost cap has a related gap. Line 130 caps each answering run, but each `sq run --resume` of the work run starts counting from $0 (`PIPELINES.md:1179`). Unattended spend on the work run is therefore roughly the answer limit times the run's cap.

### [CONCERN] The kept answering code assumes things this design removes

"Keep `answering/`, about 2.1k" and "keep questions" understate the work, and step 4 ("gathers passages") hides the hard part:

- **Foreign keys:** `question_records` has foreign keys to `nodes`, `command_journal` and `blocked_states` (`store/schema/013_question_records.sql:15-23`).
- **Launch path:** `launch_answering` needs a `TickBudget`, a `LaunchTracker`, the supervisor directory and a journal entry.
- **Sources:** `assemble_sources` needs a slice node with a CF index and an initiative parent, plus a CF snapshot row (`sources.py:94-127`).
- **Polling:** `stage.py` finishes answering runs by polling them across ticks.

For a run Amoeba didn't launch, none of those nodes exist. The document never says how `handle_pause` gets the slice and initiative for a foreign run, or what happens for a run with no slice. Today `locate_sources` treats a missing slice plan as a decline (`source_reads.py:222-226`), so every non-slice pipeline would go to the PM.

This is the core of scenario A. The architecture should define the new question record's identity (run, checkpoint, member) and how slice context is derived, not leave it to the audit.

### [CONCERN] "Member from the working directory" has no defined mapping, and it breaks for worktrees and cwd-less agents

`program_members` stores only `project_id`, with no path. Today's readability code resolves checkouts through `cf_links` and `latest_cf_snapshots` (`program/members.py:108-121`), which are the kind of mirrored tables the "read, don't mirror" principle removes. The document doesn't say what identifies a member from a directory: the CF project id, a git remote, or a registered path.

Three cases need an answer:

- **Worktrees:** the PM's Squadron has several checkouts (`squadron-240`, `squadron-bug` and others). They must all resolve to one member, yet each has its own run lock (`run_lock.py:5-6`).
- **MCP sessions:** the server's working directory is wherever the session started, and the chat agent has no repo at all. "A caller passes no paths or ids" can't hold for `status`, `decisions` or `answer`, so these need explicit program or member arguments.
- **`answer` from another session:** resume only works from the checkout, so the checkout must be recorded at claim time. It isn't in the store contents at line 39, though it could be recorded for question runs without mirroring run state.

### [CONCERN] One user-level config can't hold per-repo answer settings

The settings listed are models, cost cap, answer limit and notify command. `AnswererSettings` also has `rules_paths`, `reserved_terms`, `passages_max_chars` and `max_concurrent_runs` (`runner/project_config.py:67-97`). `rules_paths` is relative to a repo and fails hard when an entry matches no file (`source_reads.py:196-199`), so a single user-wide value would decline every question in a repo laid out differently. Reserved terms are also likely to differ per program.

Either pick a convention that needs no per-repo value, or put per-member settings in the program record. Also say whether `max_concurrent_runs` survives, because with nothing resident there is no scheduler to enforce it, and simultaneous pauses all start answering runs at once.

The per-repo rules and PM precedent also raise a scoping question for the single store. `pm_precedent` reads by `project_id` today, and the document doesn't say whether precedent stays per member or spans a program.

### [CONCERN] The PM's reply path is undefined when the agent told is headless

Decision 5 defers only whether a headless session can reach the PM's phone. The harder part is the way back. A headless session sends a push and exits, so "the PM's reply comes back through `answer`" (line 109) has no receiver and no session holding the question id. The concept's "you answer from wherever you are" is what scenario A promises, and the chat app that could do it isn't finished.

The first proof needs a stated path, even if it is only "the PM opens any agent session, which reads `status` and calls `answer`". That path should be written down as the accepted limit.

Also specify how the question reaches the command. It is untrusted model output, so it must go as an argument or file with no shell interpretation. "Fails" also needs a definition: is that only a non-zero exit, and is there a timeout?

### [CONCERN] Scenario B's steps don't fit a command step, and the provider's report has no content source

Several parts of decisions 3 and 4 don't work out as written:

- **Pick up or stop:** the scenario needs a judgment, but a command step can only pass or fail. Is `changes` non-zero when anything has changed, or only on error? If it fails on any change, every slice stops. If it never does, "stop with a reason" never happens. A later dispatch would have to make that decision, and the pipeline needs a way to act on it.
- **Report content:** "what changed and what that touched" is meaningful text, but the report is a CLI call in a deterministic step. Line 96 describes output flowing from a command to a dispatch, not from an earlier dispatch into the command. `ecorkran/squadron#304` needs to specify both directions.
- **`mark_read`:** no pipeline step is allotted to it. Decision 4 lists one report step and one ask step. If it runs at slice start, a change is lost when the slice is abandoned. If it runs at the end, a second worktree running in parallel sees the same change, because the cursor is per member and not per checkout.
- **Duplicate reports:** resuming a pipeline re-runs a failed step, and a merge report plus a release skill can cover the same commit. `report_release` needs an idempotency key, probably member plus commit.
- **Report timing:** "the end of a provider's pipeline" must come after the merge. Otherwise a failed merge leaves a report for code that never landed. The project's merge happens in Phase 7, outside the implementation steps.
- **Adoption cost:** the design relies on "each repo adds its report once". Pipelines have no extension mechanism: lookup is first match wins, and you copy a built-in file to change it (`PIPELINES.md:897-899`). Each member would carry a forked copy of each built-in pipeline it uses, and those drift from Squadron's versions. This is a larger cost than line 132 implies, and worth raising on #304.

### [CONCERN] "Since the PM last looked" has no owner

Scenario C and the morning list need "what was answered since the PM last looked". `decisions` takes "a given point", but the caller is an agent session with no memory of the last look, and the store contents at line 39 include no such marker. Either add a per-reader marker, like `mark_read`, or accept a time window and say so. As written, every new session has to guess a point.

### [CONCERN] The slice order leaves the first proof without its own recovery path and morning list

The operations table marks `decisions` as part of scenario A, and the concept says the PM sees "a short list of what was decided". The failure handling also depends on `status`: missed hooks, escalation reasons, and answered-but-not-resumed. But the anticipated slices put `status` and `decisions` in the later "MCP and status" slice for scenario C. So the first proof has no way to see a missed hook or read the record.

Move CLI versions of `status` and `decisions` into pause handling, and leave MCP for later. Note that the missed-hook part of `status` needs `ecorkran/squadron#303`, not just #302, because run files live in a shared per-user directory with no working directory (`state.py:334-335`). That makes #303 a requirement for A's recovery path, even though line 122 lists it as C and catching up.

### [CONCERN] Blocking operations over MCP aren't addressed

"One operation, two doors" treats all operations as equal, but `handle_pause` runs an LLM pipeline for minutes, and possibly a resume after that. "An agent catching up" would call it through MCP, where a long tool call risks client timeouts. The store is also synchronous SQLite, while the project's Python rules forbid synchronous work over 1ms inside async functions, so an async MCP SDK needs an executor or subprocess. The document names no MCP library.

Either make `handle_pause` over MCP start a detached CLI process and return, or remove it from MCP and have the agent run the CLI. Both are a difference between the doors, so line 40 needs to allow for it.

### [CONCERN] An interactive run gets taken over without the person knowing

"Works on any Squadron run" means a PM watching `sq run` at a terminal also has their question answered and the run resumed in a detached process they can't see. That run is then non-interactive, so a later interactive checkpoint exits and pauses instead of prompting (`PIPELINES.md:390`). A scripted caller that handles paused exit codes itself also collides with this (see the checkpoint finding).

Decide whether `handle_pause` applies to runs with a terminal attached, or whether the hook gets a per-run opt-out. This is one flag in #302 if settled now, and a change to the hook contract later.

### [CONCERN] The hook's timing and process contract aren't specified

Line 75 says Squadron starts the command and doesn't wait. #302 should also pin down:

- **Timing:** the hook must fire after the run state is saved and, ideally, after the run lock is released, since the lock fails at once with no waiting (`run_lock.py:8`). A fast repeat answer could otherwise lose to the exiting parent.
- **Isolation:** the child must be in its own session, so that closing the terminal doesn't kill an answering run in progress.
- **Answering runs:** the answering run is itself a Squadron run that can pause. Its hook is ignored only because its scratch directory is in no program, which is implicit and worth stating. `handle_pause` must treat a paused answering run as a failure.

### [NOTE] The program record still carries the removed requests model

`program_members.requests_initiative` is `NOT NULL` and exists for requests, which decision 6 removes. `consumed` is stored per provider with a separate `consumption_overrides` table (`program_schema/001_program_record.sql:33-50`). With dependency pairs now declared, `consumed` belongs on the pair and the overrides table can go. The new baseline schema is the time to do this, so "kept and reworked" should say so. Also, a from-source consumer of a repo that reports only at releases sees no merge-level changes, which should be stated.

### [NOTE] Proportionality is sound, but `mark_read` might not need to be separate

The design cuts heavily, and I found nothing large to remove. If the pipeline finding above resolves into a single step, `changes --mark-read` could replace one of the eight operations.

### Run Digest

- Response length: 17293 chars
- Response is newline-free: no
- Tool calls made: 30
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 31
- Tokens — prompt / cached / cache write / completion / reasoning: 804662 / 656665 / 147981 / 19007 / not computed
- Duration: 190.4 s
- Cost: $1.70 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
