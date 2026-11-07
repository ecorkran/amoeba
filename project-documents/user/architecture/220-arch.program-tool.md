---
docType: architecture
layer: project
project: amoeba
archIndex: 220
component: program-tool
initiative: program-tool
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [100-arch.substrate-run-state-store, 120-arch.runner-routing-engine, 140-arch.question-answerer]
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for Amoeba as a tool that agents and pipelines call. Nothing stays running. Squadron starts a short-lived Amoeba command when a run pauses; Amoeba answers through the answering pipeline, resumes the run or tells an agent, and records the decision. Program knowledge is read from git, Context Forge and Squadron rather than mirrored. Answers the concept's six open questions and lists the Squadron changes they need.
dateCreated: 20261106
dateUpdated: 20261106
status: in_progress
---

# Architecture: Program Tool

## Overview

Amoeba today is a resident supervisor: a long-running process that launches and watches Squadron runs, with a large store, an inbox and a network API. The concept replaces that with a tool that agents and pipelines call. It knows the program, handles first-level questions and keeps the record.

**Scope.** Scenarios A, B and C from the concept, the operations they share over MCP and a CLI, the store they need, and cutting today's code down to that.

**Motivation.** Nobody has run the current design, and nobody could say who would start it or when. This design has nothing to start.

## Design Goals

- **Nothing to run.** In normal use no Amoeba process exists until something calls it, and it exits when the call is done.
- **Works on any Squadron run.** A question is handled whether a person, an agent or a script started the run.
- **An exact record.** Every question, answer, source and PM override can be read back later.
- **Bounded answers.** An answer can only resume the run that asked.
- **Small.** The result is far less code than today, and new code is added only for a scenario.

## Architectural Principles

- **Read, don't mirror.** The store holds only what nobody else holds: the question and answer record, program membership and dependencies, and how far each member has read each dependency. Run state stays in Squadron, slice state in Context Forge, and releases in git.
- **One operation, two doors.** MCP and the CLI are thin layers over the same operations, with the same names. Neither has logic of its own.
- **Called, never calling around.** Amoeba starts no work, and the only run it resumes is the one that asked. It never walks the dependency graph.
- **Squadron gets the checks.** A check on an answer is a step in the answering pipeline, not Amoeba code.
- **Short-lived and restart-safe.** Every operation is a process that can die at any point. Whatever it was doing can be seen in the store and picked up by the next call.
- **Fail where someone can see it.** A question that can't be handled stays visible in `status` with the reason. It is never dropped.

## Current State

Measured 20261106, about 34k lines in `src` and 69k in `tests`:

| Area | Lines | What it is | Expected result of the audit |
|---|---|---|---|
| `store/` | 11.7k | Nodes, blocks, journal, verdicts, feed, checks, inbox, questions, programs | Keep questions and programs; most of the rest goes |
| `runner/` | 10.6k | Launch, tick, lifecycle, intents, resolutions, dispatch, answering | Keep `answering/`, about 2.1k of it; most of the rest goes |
| `process/` | 4.2k | Resident host, lock, recovery, observers | Goes, apart from reading Squadron's output |
| `cli/` | 1.6k | Lifecycle, submission and inspection commands | Replaced by the operations |
| `inspection/` | 1.5k | Read views of the store | Mostly replaced by `status` and `decisions` |
| `serve/` | 1.3k | HTTP server | Goes |
| `upstream/` | 1.3k | Context Forge and Squadron readers | Keep |
| `inbox/` | 1.2k | Submission files | Goes |
| `feed/`, `program/` | 0.3k | Change feed; member readability | Feed goes; `program/` is kept and reworked |

The table is a starting expectation. The audit decides, one piece at a time.

Facts read from Squadron 0.24.23 on 20261106 that shape this design:

- **Pipelines have no step that runs a command.** The step types are branch, collection, commit, compact, devlog, dispatch, fan-out, gate, loop, phase, review and summary. The usage note's line that Squadron steps run shell commands is wrong.
- **Events can't see a question pause.** `post-action` stops at the first failing action, and the built-in `dispatch-artifact` is the one that reports the question, so a bound action never fires. Plugins must also import inside `sq`'s own tool environment, and only one `events.yaml` applies.
- **Run files don't say where the run was started.** A run can't be matched to a member or resumed from its file alone, because resume works from the checkout. `sq runs list` also has no JSON output.
- **`sq runs wait --json` already gives the question,** along with the checkpoint kind, and `sq run --resume <id> --instructions` already accepts the answer.

## Envisioned State

### Decisions on the concept's open questions

**1. Who notices a paused run? A Squadron hook, and no resident process.** When a run pauses, Squadron starts one configured command in the run's directory, passing the run id. It doesn't wait for the command, and the command's failure doesn't change the run. A watcher would bring back the background service the concept is trying to remove, to save one small change in a repo the PM also owns.

The cost is that a missed hook leaves a question waiting (machine asleep, command killed). `status` shows paused question runs with no finished record, and an agent can call `handle_pause` on them. A run that waits costs nothing, so this is enough.

**2. The operations.**

| Operation | Called by | Does | Scenario |
|---|---|---|---|
| `handle_pause` | Squadron's hook, or an agent catching up | Answers the question, then resumes the run or tells an agent | A |
| `answer` | An agent, for the PM | Records the PM's answer. Resumes the run if it is still waiting. Becomes the answer used for repeats, which also covers an override | A |
| `status` | An agent | Per member: running, blocked and why, unhandled questions | C |
| `decisions` | An agent | What was answered, by whom and from what, since a given point | A, C |
| `changes` | A pipeline or agent | What this member's dependencies released since it last marked them read | B |
| `mark_read` | A pipeline or agent | Moves that point forward | B |
| `set_up` | An agent | Registers programs, members and dependencies | Set-up |

**3. Dependencies and releases.** Set-up declares which members a member depends on, as member-to-member pairs. The program record's existing `consumed` value (`from_source` or `from_release`) says what counts as a release: a new commit on the provider's target branch, or a new version tag. So a repo that publishes no versions is simply `from_source`.

**Amoeba reads this from the provider's git history instead of being told.** This changes the concept's scenario B, where the provider's pipeline reports its release. Reporting would need a step in every provider's pipeline and in release skills that aren't pipelines at all, and a missed report would silently hide a change. Reading git needs nothing from the provider, and the commits and changelog are what a consumer needs anyway.

**4. How a pipeline reaches program state.** Through the CLI, from a new Squadron command step. The member is worked out from the working directory, so a pipeline passes no paths or ids. A pipeline stops with a reason when the step fails, and passes its output to a later dispatch as a prompt file.

**5. Which agent gets told.** Amoeba runs one configured command with the question and run id, and that command's job is to reach the PM through an agent. It can start a headless agent session, so it doesn't need an open one, and the chat app replaces it later by changing the setting. If it is unset or fails, the question stays in `status` with that reason. Whether a headless session can reach the PM's phone gets proven during scenario A.

**6. Requests, hold, release and ordering: out.** None is in a scenario, and hold and ordering walk the graph. Scenario B's "stop with a reason" is a member's own pipeline holding itself. An agent that needs a change in another member asks a question, and that reaches the PM. This retires slices 183 to 186 and makes slice 180's slice-writing pipeline a delete candidate.

### How scenario A runs

1. A run pauses. Squadron starts `handle_pause` and exits.
2. `handle_pause` reads the checkpoint. Any kind but an agent's question stays with Squadron and shows in `status`. A repo in no program is ignored.
3. It claims the question in the store, so that a second caller backs off.
4. It gathers passages and runs the answering pipeline from a scratch directory.
5. With an answer that passes the check, it records the answer and resumes the run.
6. Otherwise it records why and runs the notify command. The PM's reply comes back through `answer` and takes the same resume.
7. The process exits. Nothing is left running, and the next pause starts the same way.

### Where things live

One store at a fixed per-user location, with no flags. Programs of one are allowed, so a lone repo needs no separate "no program" path. Amoeba's settings (models, cost cap, per-run answer limit, notify command) sit in one user-level config file, set once.

### Squadron changes

| Change | Needed for | Status |
|---|---|---|
| Tool-less Claude steps | A, on Claude models | `ecorkran/squadron#299`, open |
| Command started on pause, in the run's directory | A | Not filed |
| Working directory in the run file, and JSON from `sq runs list` | C, and catching up on a missed hook | Not filed |
| Command step in pipelines | B, and deterministic checks on answers | Not filed |

## Technical Considerations

- **Many short-lived writers.** Today's store assumes one resident writer holding a lock. SQLite's busy timeout handles the small number of writers here, but the single-writer checks go. The start-up race in `amoeba#32` is in an inbox load test, so it goes with the inbox.
- **Double handling.** The hook and a catching-up agent can reach the same question. A uniqueness constraint on run and checkpoint decides the winner. A claim whose process has died can be retaken, which `status` makes visible.
- **Resume can be refused.** Squadron holds one run lock per checkout, so a resume fails while another run is active there. The answer is already recorded by then, so `status` shows it as answered but not resumed. It isn't retried in the background.
- **Runaway loops and spend.** A run that keeps asking hits the per-run answer limit and goes to the PM. Each answering run has its own cost cap through `pipeline.max_cost_usd`.
- **Answer checks move in two stages.** The deterministic reserved-term screen in `runner/answering/gate.py` becomes a pipeline step once the command step exists. It stays where it is until then, since dropping it would widen what an answer can say.
- **Stale provider checkouts.** Reading git sees only what the local checkout has. `changes` fetches the provider first, and a failed fetch is reported in the result, not treated as "nothing changed".
- **Prompt-only runs.** An agent driving `/sq:run` is already in a session and handles its own questions. These runs are outside `handle_pause`.
- **No data to migrate.** Nobody has run Amoeba, so the store starts from a new baseline schema and the old migrations go.
- **Tests follow the code.** Most of the 69k lines of tests cover code that goes. The live answering tests stay and become the check on scenario A.

## Anticipated Slices

Provisional. The audit and the slice plan decide.

- **Audit:** a sorted list of keep, move to Squadron or delete. This is a document, and it comes before the slice plan.
- **The cut:** remove what the audit rejects, and move to the single store and config.
- **Pause handling:** `handle_pause`, `answer` and the notify command, through the CLI. This is the first proof, scenario A on a real run.
- **MCP and status:** the MCP server, `status` and `decisions`. Scenario C.
- **Program dependencies:** dependency declarations, `changes` and `mark_read`. Scenario B.
- **Answer checks in the pipeline:** move the deterministic screen into a pipeline step.

## Related Work

- `user/project-guides/000-concept.amoeba.md` and `user/notes/005-usage-scenarios.amoeba.md`: what this design has to do.
- `140-arch.question-answerer` and slices 140, 141, 143 and 144: the answering pipeline, question record and passages this design keeps.
- Slice 181 (program record): kept and reworked. Slice 182 (program concept as a source), parked on its branch: its passage kinds are wanted, but its no-program path isn't, so the audit decides whether to merge or redo it.
- `100-arch`, `120-arch` and `180-arch`: describe what was built. This document replaces them for new work.
- Squadron `docs/EVENTS.md` and `docs/PIPELINES.md`: the pause, resume and event behavior read for this design.
