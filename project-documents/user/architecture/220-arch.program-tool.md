---
docType: architecture
layer: project
project: amoeba
archIndex: 220
component: program-tool
initiative: program-tool
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [140-arch.question-answerer]
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for Amoeba as a tool that agents and pipelines call. No Amoeba process stays running. Squadron optionally starts a short-lived Amoeba command when a run pauses; Amoeba answers through the answering pipeline and starts the resume, or records the question as waiting on the PM. Squadron never requires Amoeba. Members report their own releases through their agents, and run and slice state are read from Squadron and Context Forge rather than mirrored. Revised 20261106 and 20261107 from two architecture reviews and PM notes.
dateCreated: 20261106
dateUpdated: 20261112
status: in_progress
---

# Architecture: Program Tool

## Overview

Amoeba today is a resident supervisor: a long-running process that launches and watches Squadron runs, with a large store, an inbox and a network API. The concept replaces that with a tool that agents and pipelines call. It knows the program, handles first-level questions and keeps the record.

**Scope.** Scenarios A, B and C from the concept, the operations they share over MCP and a CLI, the store they need, and cutting today's code down to that.

**Motivation.** Nobody has run the current design, and nobody could say who would start it or when. This design has nothing to start.

## Design Goals

- **Fewer stops, not more.** Amoeba creates no new reasons for a run to stop. It takes question pauses off the PM's plate and adds nothing between pipelines.
- **Nothing to run.** In normal use no Amoeba process exists until something calls it, and it exits when the call is done. The work run it resumes is Squadron's own process, not Amoeba's.
- **Optional everywhere.** Squadron works exactly as before without Amoeba. A run can opt out, and so can a repo by not joining a program.
- **An exact record.** Every question, answer, source and PM override can be read back later.
- **Small.** The result is far less code than today, and new code is added only for a scenario.

## Architectural Principles

- **Read, don't mirror.** The store holds only what nobody else holds: the question and answer record, program membership and dependencies, reported releases, and the PM's read marker. Run state stays in Squadron and slice state in Context Forge.
- **One operation, two doors.** MCP and the CLI are thin layers over the same operations, with the same names and no logic of their own. The only difference is that long work over MCP starts a detached CLI process and returns at once.
- **Called, never calling around.** Amoeba starts no work, and the only run it resumes is the one that asked. It never walks the dependency graph.
- **Pull, never push.** Amoeba sends no notifications. A question waiting on the PM is a row in the store that agents read. Getting it to the PM is the job of chat and agent communication.
- **Squadron never depends on Amoeba.** Each Squadron change is general and off unless configured. Nothing in Squadron's built-in pipelines, skills or docs assumes Amoeba exists. Only repos that join a program carry anything that mentions it.
- **Short-lived and restart-safe.** Every operation is a process that can die at any point. Whatever it was doing can be seen in the store and picked up by the next call.
- **Fail where someone can see it.** A question that can't be handled stays visible in `status` with the reason. It is never dropped.

## Current State

Measured 20261106, about 34k lines in `src` and 69k in `tests`:

| Area | Lines | What it is | Expected result of the audit |
|---|---|---|---|
| `store/` | 11.7k | Nodes, blocks, journal, verdicts, feed, checks, inbox, questions, programs | Keep questions and programs, re-keyed (see below); most of the rest goes |
| `runner/` | 10.6k | Launch, tick, lifecycle, intents, resolutions, dispatch, answering | From `answering/` (about 2.1k), keep the pipeline, passages, decision logic and answer screen, and rewrite its launching and polling; most of the rest goes |
| `process/` | 4.2k | Resident host, lock, recovery, observers | Goes, apart from reading Squadron's output |
| `cli/` | 1.6k | Lifecycle, submission and inspection commands | Replaced by the operations |
| `inspection/` | 1.5k | Read views of the store | Mostly replaced by `status` and `decisions` |
| `serve/` | 1.3k | HTTP server | Goes |
| `upstream/` | 1.3k | Context Forge and Squadron readers | Keep |
| `inbox/` | 1.2k | Submission files | Goes |
| `feed/`, `program/` | 0.3k | Change feed; member readability | Feed goes; `program/` is kept and reworked |

The table is a starting expectation. The audit decides, one piece at a time. Today's answering code is tied to what this design removes: question records point at nodes, journal entries and blocked states, and launching needs the tick loop. Keeping it means re-keying it.

Facts read from Squadron 0.24.23 on 20261106 that shape this design:

- **Pipelines have no step that runs a command,** and phase steps such as design take no extra input files. The usage note's line that Squadron steps run shell commands is wrong.
- **Events can't see a question pause.** `post-action` stops at the first failing action, and the built-in `dispatch-artifact` is the one that reports the question, so a bound action never fires. Plugins must also import inside `sq`'s own tool environment, and only one `events.yaml` applies.
- **Run files don't say where the run was started.** A run can't be matched to a member or resumed from its file alone, because resume works from the checkout. `sq runs list` also has no JSON output. A run file does record its `status` and its `execution_mode`.
- **`sq runs wait --json` already gives the question,** along with the checkpoint kind, and `sq run --resume <id> --instructions` already accepts the answer.
- **A resume is the work run itself.** It runs in the foreground for as long as the work takes and holds the checkout's run lock, which fails at once when held. Its `--instructions` text is added to every dispatch the resumed run makes, and its cost cap starts again from zero.
- **Checkpoints have no id.** `paused_at` is the closest thing.
- **Pipelines have no extension mechanism.** To add a step to a built-in pipeline, a repo copies the file.
- **Costs are list prices.** Squadron records a cost as the provider's figure or as alias pricing, and has no notion of a subscription.

Context Forge resolves a directory to its project, and separate worktrees of a repo resolve to the same project id (checked on Squadron's worktrees, 20261106).

## Envisioned State

### Decisions on the concept's open questions

**1. Who notices a paused run? A Squadron hook, and no resident process.** When a run pauses, Squadron starts one configured command in the run's directory, passing the run id. It starts after the run state is saved and the run lock is released, in its own session, so closing the terminal doesn't kill it. Squadron doesn't wait for it, and its failure doesn't change the run. A run can opt out with a flag, and with nothing configured Squadron behaves as it does today. A watcher would bring back the background service the concept is trying to remove, to save one small change in a repo the PM also owns.

The cost is that a missed hook leaves a question waiting (machine asleep, command killed). `status` shows paused question runs with no finished record, and an agent can call `handle_pause` on them. A run that waits costs nothing, so this is enough.

**2. The operations.**

| Operation | Called by | Does | Scenario |
|---|---|---|---|
| `handle_pause` | Squadron's hook, or an agent catching up | Answers the question and starts the resume, or records it as waiting on the PM. With an answer already recorded for this pause, it only starts the resume | A |
| `answer` | An agent, for the PM | Records the PM's answer. Starts the resume if the run is still at that pause. Becomes the answer used for repeats, which also covers an override | A |
| `status` | An agent | Per member: running, blocked and why, questions waiting on the PM, answered but not resumed | A, C |
| `decisions` | An agent | What was answered, by whom and from what, since the PM's marker or a given time | A, C |
| `dismiss` | An agent, for the PM | Closes a `claimed` or `waiting_on_pm` question, or an `answered` one whose answer was never delivered, with a reason. The run is not resumed and stays paused in Squadron | A, C |
| `retract` | An agent, for the PM | Marks a PM answer retracted, so it stops being precedent. The answer stays delivered and stays in `decisions` | A, C |
| `mark_read` | An agent | Moves the PM's marker for `decisions` forward to the last record the caller saw | C |
| `report_release` | An agent or release skill | Records what this member released and what that touched | B |
| `changes` | An agent | What this member's dependencies reported since a point the caller gives | B |
| `set_up` | An agent | Registers programs, members, dependencies and per-member settings | Set-up |

**3. Dependencies and releases.** Set-up declares which members a member depends on, as member-to-member pairs. Each repo reports its own releases, because only the repo that made a change knows what it means. A report holds the commit, a version if there is one, what changed and what that touched.

Each dependency pair carries a `consumed` value (`from_source` or `from_release`) that says which reports the consumer sees: every report, or only those with a version. So a repo that publishes no versions reports when it merges, and its consumers are `from_source`. A consumer can only see what its provider reports, so a `from_source` consumer of a repo that reports only at releases sees only those.

A report is identified by member and commit, and holds the commit's current version. Reporting the same thing twice changes nothing. A release tagged on a commit already reported at merge adds the version to that report. `from_release` consumers then see it, and `from_source` consumers, who already saw the commit, don't see it again.

**4. How a repo reaches program state: through its agents, by a line in its rules file.** There is no pipeline step and no Squadron change. A repo that joins a program adds two lines to its own rules file:

- **As a consumer:** before designing a slice, check Amoeba for changes in what this repo depends on. The design agent calls `changes` with a starting point, usually its branch's last merge, and judges what it finds. Nothing is marked read, so each design sees everything since its own starting point, and parallel worktrees don't hide changes from each other. To stop, the agent ends on a question or a `BLOCKED:` line, and the run pauses as it does today.
- **As a provider:** when a slice changes something other repos use, call `report_release`. The repo's release skill gets the same line.

Each repo adds lines, not pipeline copies, and a repo outside a program carries nothing. The cost is that nothing forces the agent to follow the line. If agents skip it in real use, a Squadron pipeline step (`ecorkran/squadron#304`, on hold) is the fallback.

From inside a repo, the member is the Context Forge project for the working directory, so callers there pass no paths or ids. All worktrees of a repo are one member. MCP sessions can start anywhere, so `status`, `decisions` and `answer` take an explicit program or question.

**5. Which agent gets told: none.** Amoeba pushes nothing. A question the answering pipeline declines is recorded as waiting on the PM, with the reason, and any agent sees it through `status`. The PM answers by telling an agent, which calls `answer`. Getting a waiting question in front of the PM sooner belongs to chat and agent communication, which are outside Amoeba.

**6. Requests, hold, release and ordering: out.** None is in a scenario, and hold and ordering walk the graph. Scenario B's "stop with a reason" is a member's own agent holding its run. An agent that needs a change in another member asks a question like any other. If the repo's rules or the PM's earlier answers settle it (for example, "open an issue on the provider and carry on with a stub"), it is answered and the agent acts on it with its own tools. Otherwise it waits on the PM. This retires slices 183 to 186 and makes slice 180's slice-writing pipeline a delete candidate.

### How scenario A runs

1. A run pauses and its `sq` process exits. Squadron starts `handle_pause`.
2. `handle_pause` reads the run. It handles only an agent's question from an in-process run in a program member. Every other checkpoint kind stays with Squadron and shows in `status`. A prompt-only run (by its `execution_mode`) belongs to the agent driving it. A repo in no program is ignored.
3. It claims the question in the store, recording the checkout. A second caller backs off.
4. It works out the context. The slice comes from the run's parameters and the rest from Context Forge in that checkout. A run with no slice still gets the rules, the program concept and the PM's earlier answers.
5. It starts the answering run from a scratch directory, always with the hook's opt-out, records that run's id on the claim, and waits for it. If the answering run pauses or fails, the question waits on the PM.
6. With an answer that passes the check and the answer screen, it records the answer and starts the resume. Otherwise it records the question as waiting on the PM, with the reason.
7. The process exits. The work run carries on as its own process, and the next pause starts this again.

**The test for scenario A** is how many real questions get answered without the PM. If most still wait on the PM, Amoeba costs more than it saves, and the design is rethought before scenario B is built. The PM's answers become precedent, and a standing call written into a repo's rules file answers itself, so the share should rise with use.

### The resume

Every resume, from `handle_pause` or `answer`, works the same way:

1. Re-read the run and compare its checkpoint with the question's. If the run is no longer paused at that `paused_at`, someone else resumed it, so the answer is recorded as **not delivered** and nothing is resumed.
2. Start `sq run --resume` detached from the recorded checkout, logging to a file named in the record.
3. Wait briefly for the run's `status` to become `running`, which means the resume took the lock. Record it as **resumed**, or as **refused** with the reason.

After that the run is Squadron's. If it fails at a later step, that is a failed run in `status` like any other, and the answer stays recorded as delivered. A refused resume, or one whose process died before step 3, leaves the run at the same pause, so calling `handle_pause` again resumes with the recorded answer and spends nothing. There is no background retry.

### What an answer may authorize

An answer is text that reaches agents with tools, so what it may authorize is a setting. By default an answer may not authorize a push, a merge to the main branch, a release, a destructive database statement or a policy change. The PM asked to be able to allow some of these per repo, so a member can change the list, and "yes, merge it" can be allowed in one repo and not another. This applies in every phase, merge included, and it only governs what Amoeba answers. It never adds a step a pipeline doesn't have.

The list is a policy about meaning, so models enforce it. The answer step is told not to answer past it, and the independent check step rejects an answer that authorizes anything on it. The deterministic answer screen is a coarse backstop. It matches a short list of unambiguous phrases, and a false match sends the question to the PM and shows up in the scenario A test.

### The question record

A question is identified by run id and `paused_at`, so the same words asked at a later pause are a new question. It moves from claimed to answered or waiting on the PM, and a PM answer moves a waiting question to answered. A delivered answer is then resumed, refused or not delivered, as above.

A question can also be **closed**, with one of three reasons: `dismissed` (the PM or an agent for the PM closed it with `dismiss`), `run_moved_on` (the run left that pause, or finished, so nobody can answer it) or `run_gone` (Squadron no longer knows the run). A closed question is terminal, except that a later `answer` reopens it as answered. `handle_pause` closes a run's older open questions when the run pauses again, and `status` closes those whose run has moved on or gone, so every open question has an exit with nobody editing files.

PM answers are kept per member as the precedent for repeats. Sharing them across a program waits until use shows the need. The per-run answer limit counts only automatic answers, never the PM's, and it counts those given since the PM's last answer on that run, so a PM answer resets it. A retracted PM answer is not precedent, and an older PM answer to the same question is not brought back. There is one PM, so the PM's `decisions` marker is a single one across all programs.

### Where things live

One store at a fixed per-user location, with no flags. State and config live in two homes: the config file in `~/.config/amoeba/`, and the store, answering scratch and logs in `~/.local/state/amoeba/`. Tests point both at one directory through one environment variable, read in one config place, so a test run never touches the real store. Programs of one are allowed, so a lone repo needs no separate "no program" path.

Amoeba's settings (models, cost cap, per-run answer limit, what answers may authorize) sit in one user-level config file, set once. Per-member settings go on the member at set-up: its rule file paths, which depend on the repo's layout, and any change to what its answers may authorize. The concurrent-run limit goes, because nothing is left to enforce it, so simultaneous pauses start simultaneous answering runs, each under its own cost cap.

`status` now writes: it closes question records whose run has gone, and prunes old scratch and log files. This is still bounded and adds no `sq` call: it judges from the one `sq runs list` listing it already makes, and the pruning is a file walk.

The new baseline schema drops what the old program record held for requests: `requests_initiative` goes, `consumed` moves to the dependency pair, and the overrides table goes.

### Squadron changes

All are general Squadron features that are off or unused unless configured. None mentions Amoeba.

| Change | Needed for | Status |
|---|---|---|
| Tool-less Claude steps | A, on Claude models | `ecorkran/squadron#299`, closed |
| Command started on pause, in the run's directory, with a per-run opt-out | A | `ecorkran/squadron#302`, open |
| Working directory in the run file, and JSON from `sq runs list` | C, and A's catching up on a missed hook | `ecorkran/squadron#303`, open |
| Command step in pipelines | Only if agents skip the scenario B rule lines | `ecorkran/squadron#304`, on hold |

## Technical Considerations

- **What an answer can reach.** The answer step has no tools, but its reply goes into `--instructions`, which reaches every dispatch of the resumed run, and those have tools. That is intended, since it is how a question gets answered at all. What limits it is that passages come from the PM's own repos and earlier answers, the independent check enforcing what answers may authorize, and the screen behind it. The record shows every answer afterward.
- **Unattended spend.** Each answering run has its own cost cap through `pipeline.max_cost_usd`. A work run's cap restarts on each resume, so its unattended spend can reach the per-run answer limit times its cap. A run that keeps asking hits the answer limit and waits on the PM. Two limits are likely later and are not designed yet: a cap per time window, and different treatment for subscription models, whose dollar figures are list prices rather than spend.
- **Taking over a watched run.** A run started at a terminal gets answered and resumed too, because that is exactly scenario A: the person starts a run at night and walks away. Someone watching can pass the opt-out, and the answer shows in `decisions`. A resumed run has no terminal, so a later interactive checkpoint pauses instead of prompting, and it shows in `status` like any other pause.
- **Many short-lived writers.** Today's store assumes one resident writer holding a lock. SQLite's busy timeout handles the small number of writers here, but the single-writer checks go. The start-up race in `amoeba#32` is in an inbox load test, so it goes with the inbox.
- **Double handling and dead claims.** The hook and a catching-up agent can reach the same question, and the uniqueness of run id and `paused_at` decides the winner. Because the claim records the answering run's id, a later explicit call can check that run first. If it finished, its result is used. If it is still running, the caller backs off. If it never started, a new one starts. The only case that spends twice is a process that died between claiming and starting the answering run, which is rare and bounded by the cost cap.
- **Someone resumes outside Amoeba.** The checkpoint comparison before each resume catches this, apart from a very small window, where the run lock usually refuses the second resume.
- **The resume's environment.** A resume inherits the environment of whatever started it, which over MCP is the MCP server's. A missing credential shows up in the resume's log and in `status`.
- **The answer screen stays in Amoeba.** The concept puts checks on an answer in the answering pipeline, but Squadron has no deterministic step to hold this one while `#304` is on hold. Amoeba owns the answering pipeline and nobody copies it, so keeping the screen beside it costs nothing.
- **Rule lines are soft.** An agent can skip a rule line, so a consumer can miss a change and a provider can forget a report. These get fixed when someone notices. If it keeps happening, `#304` is the fallback.
- **MCP and the synchronous store.** The first MCP slice names the library and runs store calls off the async loop, as the project's Python rules require.
- **No data to migrate.** Nobody has run Amoeba, so the store starts from a new baseline schema and the old migrations go.
- **Tests follow the code.** Most of the 69k lines of tests cover code that goes. The live answering tests stay and become the check on scenario A.

## Anticipated Slices

Provisional. The audit and the slice plan decide.

- **Audit:** a sorted list of keep, move to Squadron or delete. This is a document, and it comes before the slice plan.
- **The cut:** remove what the audit rejects, and move to the single store and config.
- **Pause handling:** `handle_pause`, `answer`, `status`, `decisions` and `mark_read`, through the CLI. This is the first proof, scenario A on a real run, measured by the test above.
- **MCP:** the MCP server over those operations. This completes scenario C.
- **Program dependencies:** dependency declarations, `report_release`, `changes` and the rule lines. Scenario B, built only if scenario A passes its test.

## Related Work

- `user/project-guides/000-concept.amoeba.md` and `user/notes/005-usage-scenarios.amoeba.md`: what this design has to do.
- `140-arch.question-answerer` and slices 140, 141, 143 and 144: the answering pipeline, question record and passages this design keeps and re-keys.
- Slice 181 (program record): kept and reworked. Slice 182 (program concept as a source), parked on its branch: its passage kinds are wanted, but its no-program path isn't, so the audit decides whether to merge or redo it.
- `100-arch`, `120-arch` and `180-arch`: describe what was built. This document replaces them for new work.
- Squadron `docs/EVENTS.md` and `docs/PIPELINES.md`: the pause, resume and event behavior read for this design.
- `user/reviews/220-review.arch.program-tool.md`: the second review of this document; the first is in `user/reviews/archive/`.
