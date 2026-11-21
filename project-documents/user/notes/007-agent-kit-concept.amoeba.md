---
docType: notes
layer: project
project: amoeba
audience: [human, ai]
description: Draft concept for a standalone kit for long-running agents, separate from Amoeba. What it is, what the PM requires of it, what agent runtimes already supply (checked 20261120), what the kit builds, the first agents, and what stays out. Built now as its own project with the PR review responder as the first agent, ahead of Amoeba's own agent work. Input for a new project's concept stage.
dependsOn: [notes/006-long-running-agents.amoeba.md]
dateCreated: 20261120
dateUpdated: 20261120
status: in-progress
---

# Agent kit: draft concept

"Agent kit" is a working name. The PM names the project.

## What it is

A small package that turns a definition file into a long-running agent. The agent wakes when there is work, does a bounded piece of it with real tools, remembers what it learned, and sleeps. Writing a new agent means writing one file and running one command.

The kit knows nothing about Amoeba, Squadron or Context Forge. The PR review responder is the first agent built on it. Amoeba's stand-in is the second.

The pattern is Anthropic's article "Building always-on agents" (five parts: event inbox, timers, memory, permissions, outbox) plus the additions in `006-long-running-agents.amoeba.md` (bounded runs, observability, one definition file, an exit for every state).

## Build order (decided 20261120)

The kit starts now, as its own project. It does not wait for Amoeba to build an agent core and extract it.

1. **The kit is built for one real agent: the PR review responder.** The first build is done when that agent runs unattended on the PM's own repos. Nothing in it needs Amoeba's hub, programs or messaging.
2. **Amoeba's stand-in is the second agent.** Putting it on the kit is what shows which parts are general. Expect rework in the kit when it lands.
3. **Amoeba does not build these parts itself.** Timers, memory curation, outgoing messages, runtime adapters and the cost cap are built in the kit and nowhere else.

The kit is still not designed in the abstract: every part is built because the review responder needs it.

## What the PM requires

1. **It acts as the right person.** Each agent runs under one named person's own logins: their model account, their GitHub, their mail. At work that includes SSO. No shared account and no shared quota.
2. **It is not tied to one vendor.** The definition names the runtime and the model. The kit starts that runtime; it does not replace it.
3. **It does things.** An agent labels and closes issues, pushes fixes, replies on review threads, filters and moves mail. It never hands a person instructions to paste.
4. **A new agent is quick.** One definition file, one command. No hand-written wrapper script per agent.
5. **Every run is bounded** by a time cap and a cost cap, and one run at a time per agent.
6. **Every state ends on its own:** completion, expiry or an explicit cancel.

## What already exists (checked 20261120)

Nothing found is worth adopting.

- **OpenClaw** has hooks, a scheduler, and memory with a curation pass, but it is its own agent runtime. It does not start vendor tools under each person's login.
- **agentcron** has the right shape (one file per job, runs `claude` or `codex`, timeout, run ledger) but was three weeks old with no users, and has no event inbox, no curation and no outbox.
- **Workflow engines** (Temporal, DBOS) supply only plumbing and need a server or Postgres.
- **Claude Code scheduled cloud agents** run as the creator's claude.ai account, in the cloud, on Claude only, and stop at a permission prompt that waits for a person.
- **Claude Managed Agents** supply sessions, budgets, memory stores and a curation call, but credentials are scoped to a workspace, not a person, and it is Claude only.

What the runtimes supply, so the kit does not build it:

| Need | Claude Code headless | Codex headless | Kit's part |
|---|---|---|---|
| Agent loop and tools | yes | yes | none |
| Turn cap | flag | none found | pass it, or count turns from the output |
| Cost cap | budget flag (an estimate) | none | sum usage from the run's output and stop the run |
| Wall-clock cap | none | none | always the kit's: kill the process group |
| Resume a saved session | yes | yes | record the session id per item |
| Pause for a person and resume | a hook can defer a tool call; the run ends saved | not confirmed | store the pending item; resume when the answer arrives |
| Safety review of risky actions | auto mode | sandbox and approval modes | pick the mode in the definition |
| Run as a person, unattended | a token minted once by that person's login, or an API key; one config directory per person | login, API key, or a per-member access token on Enterprise | start the runtime in that person's environment |
| Memory curation | none locally | none | the kit's |

Other runtimes (opencode, Goose) fit the same adapter shape. Gemini's tool is not a base to build on: its docs say it was replaced for some account types in June 2026.

## What the kit builds

- **One store** (SQLite, in the state directory) with four tables: events, timers, runs, outgoing messages.
- **Intake.** Two ways in, both writing events with a dedup id: a small HTTP handler for webhooks, and polling sources run on a timer. Polling through the person's own tools needs no inbound network, which is what a work machine usually allows.
- **One process that stays up.** Each pass turns due timers into events and starts a run for any agent with pending events. One run per agent at a time; events that arrive mid-run wait for the next.
- **A runner with one adapter per runtime.** It starts the runtime in the agent's working directory with the caps from the definition, enforces time and cost itself, records the outcome and the session id, and kills the whole process group at the limit. Claude Code and Codex adapters are in the first build.
- **Timers.** Follow-ups an agent sets for itself and schedules from the definition. Each has an expiry.
- **Memory.** A folder per agent: instructions, an index, notes, progress per ongoing item, and what has already been reported. The index and instructions load every run. A scheduled curation pass merges repeats and replaces stale entries.
- **Outgoing messages.** What the agent tells its person, written to the store and delivered by a dispatcher, so a failed send is retried and nothing is sent twice. It starts quiet.
- **Waiting on a person.** An action the definition marks as needing approval ends the run with the session saved. The answer comes back as an event and the run resumes. A waiting item expires after an age set in the definition and is closed and recorded.
- **One definition file per agent:** whose it is, runtime, model, caps, triggers, tools and connections, what needs approval, memory location, instructions.
- **Commands:** create an agent from a definition, list agents and their last runs, show a run's log, cancel a run, remove an agent.

**When a cap is hit:** the run ends and is recorded with what it did. The item is retried once on the next wake. A second failure closes the item as failed and tells the person once.

**Identity.** The definition names the person. The kit runs that agent as that person's OS user, with that person's config directory, and loads no credential of its own. A machine that hosts agents for several people runs each under its own user. The kit never copies a credential between people.

## First agents

1. **PR review responder (the build target; the PM's own repos first, then work).** Wakes when a review lands on the person's pull request, from Copilot or a human's AI review. It reads every finding, sorts real problems from noise (a rare edge case rated high is the usual noise), fixes the real ones on the branch, replies on each thread with what it did or why the finding does not hold, pushes, and asks for re-review. Its person hears about a finding that is a real design question and about a pull request that is ready to merge. Memory holds which calls people overturned, so its sorting improves. It uses whatever review-combing tools the person has installed.
2. **Issue triage (work and personal).** Labels and categorizes new issues, marks the ones an agent can resolve, resolves those through a pull request, and leaves the rest sorted for people.
3. **Tracker sync.** Keeps issues and a project tool such as ClickUp in step in both directions.
4. **Amoeba's stand-in (personal).** The agent described in `000-concept.amoeba.md`.

## Out of scope

- **An agent loop of its own.** The runtime has one.
- **A safety classifier of its own.** The runtime has one.
- **A credential proxy.** Each agent runs as its person on a machine that person or their employer controls. A proxy is needed only for an agent running somewhere neither controls, which this kit does not do.
- **A hosted service.** The kit runs on machines the PM or his employer has.
- **Agents talking to each other.** That is Amoeba's messaging.

## What moves from Amoeba

Amoeba has proven several of these parts and they are copied into the kit at the start, not reinvented: the dedup inbox with read cursors, the wake wrapper with a time cap and process-group kill, the cleaned environment for a started command, run rows and logs, and pruning by age. `008-code-sort.amoeba.md` lists where they are.

Amoeba keeps its own copies until the stand-in moves onto the kit. At that point Amoeba depends on the kit, deletes its copies, and keeps what only it does: the hub, programs, messages between repos, and the record of the PM's decisions.

## For the architecture to settle

1. Where the project lives and what it is called (the PM's choice).
2. The definition file's exact keys, and how tools and connections are declared per runtime.
3. How the cost cap is computed for a runtime with no budget flag.
4. The polling sources in the first build (GitHub reviews and issues, mail) and the webhook handler's access control.
5. How the staying-up process starts at login and restarts, on macOS and on a work Linux or Windows machine.
6. How approval requests reach a person at work (the PM's chat tool there) and how the answer gets back as an event.
7. On the machine that runs Amoeba's hub, whether the hub and the kit's staying-up process are one process or two. This is settled when the stand-in moves onto the kit and blocks nothing before then.
