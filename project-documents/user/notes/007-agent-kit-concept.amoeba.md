---
docType: notes
layer: project
project: amoeba
audience: [human, ai]
description: Hand-off concept for a standalone kit for long-running agents, separate from Amoeba. Self-contained, so a session starting the new project needs no other Amoeba document. What it is, what the PM requires of it, the pattern it implements, what agent runtimes already supply (checked 20261120), what the kit builds, the first agents, what stays out, and what only the PM can still supply. Input for the new project's concept stage.
dependsOn: [notes/006-long-running-agents.amoeba.md]
dateCreated: 20261120
dateUpdated: 20261122
status: in-progress
---

# Agent kit: hand-off concept

"Agent kit" is a working name. The PM names the project.

## How to use this document

This is the input for a new project's concept stage, written to be handed to a session working in that project's own, empty repo. It stands alone: every fact the concept needs is here. The notes it was drawn from (`006` and `008` in the Amoeba repo) are background and are not required.

The PM's interest is the system, not the code: how AI is used to put this together so that it is easy to reuse, easy for other people to adopt, and easy for their AI agents to adopt. Treat that as the measure of the project, ahead of any single feature.

## What it is

A small package that turns a definition file into a long-running agent. The agent wakes when there is work, does a bounded piece of it with real tools, remembers what it learned, and sleeps. Writing a new agent means writing one file and running one command.

The kit knows nothing about Amoeba, Squadron or Context Forge.

## The pattern

The kit implements Anthropic's article "Building always-on agents" (https://claude.com/resources/articles/building-always-on-agents; read it before designing). The article has five parts: an event inbox, timers, memory, permissions, and an outbox. A long-running agent built this way needs:

1. **Triggers.** Something wakes it: a message, a timer, an outside event.
2. **A durable inbox.** Work survives the agent not running. Dedup ids and read cursors mean nothing is processed twice or lost.
3. **A bounded worker.** Each wake is one process with a time cap and a cost cap, and at most one runs per agent.
4. **Rules.** It reads how to behave from the repo's own rules files, not from a copy.
5. **Memory and curation.** It keeps what it learned across wakes. A scheduled pass replaces stale entries, so old memory does not steer new work wrong.
6. **Credentials.** It loads its own person's logins. Nothing leaks from whoever triggered it.
7. **Observability.** Logs per run, a status view, and a record of each run's outcome.
8. **An exit for every state.** Every run, limit and stored record ends on its own.

## Why now

The PM needs long-running agents in use at his job as well as on his own projects, and needs them now. Today there is no substrate to run one on, so the substrate is the project. Which agent runs on it first is decided when it exists.

The kit is built generically. Enterprise environment specifics, including how AI access works there, are a separate matter and are not designed into it. Two facts about where it runs are known:

- **It runs in a Docker container and is reachable over the network** (decided 20261122). That lets the PM run it on his LAN now and is the same shape that works later at his job, on a Linux VM.
- The PM uses it himself, with whichever provider he chooses.
- At work it will use Claude. Whether that is by API key or by login is not settled; during development the PM's enterprise Claude login can be used.

## Build order (decided 20261120, revised 20261122)

The kit is its own project. It does not wait for Amoeba to build an agent core and extract it.

1. **The substrate comes first.** The first build is done when a definition file becomes an agent that wakes, runs bounded, remembers and sleeps, unattended, on the PM's machine and in a Linux container. Nothing in it needs Amoeba.
2. **The PM names the first agent when the substrate runs.** At work it is probably review, otherwise issue triage. No design decision waits on this choice.
3. **Amoeba's persistent agent comes after that.** Amoeba's concept calls it the stand-in. On 20261122 the PM described it as the agent that lives in Amoeba's shared room and can see what is going on across projects; standing in for him is one of its functions. Putting it on the kit is what shows which parts are general. Expect rework in the kit when it lands.
4. **Amoeba does not build these parts itself.** Timers, memory curation, outgoing messages, runtime adapters and the cost cap are built in the kit and nowhere else.

The kit is not designed in the abstract: every part is proven by a real agent running on it, and a part that no agent listed below needs is not built.

## What the PM requires

1. **It acts as the right person.** Each agent runs under one named person's own logins: their model account, their GitHub, their mail. At work that includes SSO. No shared account and no shared quota.
2. **It never decides as its person.** An agent uses its person's logins; it does not speak for them. An action is either inside the authority its definition states, or it goes to the person through the approval path. It never composes an instruction or a decision in the person's name.
3. **It is not tied to one provider, and it knows which ones are usable.** The definition names the provider and the model. The desired state is what Squadron's provider layer does today (see "Squadron's provider layer" below): Anthropic by account login, Codex by OpenAI login, anything (Anthropic and OpenAI included) through OpenRouter, and a local model behind a compatible interface. At any moment the kit can say which of these are active. The first build may support one, Anthropic by account login, as long as the others are added without changing the kit's own code.
4. **It does things.** An agent labels and closes issues, pushes fixes, replies on review threads, filters and moves mail. It never hands a person instructions to paste.
5. **A new agent is quick.** One definition file, one command. No hand-written wrapper script per agent.
6. **It is easy to adopt, for people and for their AI agents.** A person installs it with one command. An AI agent given only the kit's published documentation can write a correct definition, install the agent and confirm it ran, with nobody explaining anything. This is tested: a fresh agent session with only the docs creates and runs a new agent.
7. **It runs in a container and is reachable over the network.** One image starts the whole kit. Its commands work against a kit on another machine, so the PM can list agents, read a run's log, cancel a run and answer an approval from anywhere on the network. Access is controlled; nothing is open by default.
8. **One install per machine.** Every command, hook and background process runs from the installed package. Nothing ever points at a source checkout or a virtualenv.
9. **Every run is bounded** by a time cap and a cost cap, and one run at a time per agent.
10. **Every state ends on its own:** completion, expiry or an explicit cancel.
11. **An agent can tell how well it is doing.** When an action can later be shown right or wrong (a finding it dismissed, a fix it pushed), the kit records the outcome when it arrives (a person overturned it, the checks failed, the pull request merged) and reports the rate per agent. The PM's words for reviews apply to every agent: it needs to know how good it is, and how to make itself better.
12. **Memory stays bounded.** Curation merges and replaces. Memory and instructions never grow by appending a rule after each incident; the definition sets a size limit and the curation pass keeps to it.

## What already exists (checked 20261120)

Nothing found is worth adopting. Check again before designing; these move quickly.

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

### Squadron's provider layer (checked 20261122, Squadron commit fc009694)

The PM's other tool, Squadron, already has the provider code this kit needs, and it gives full agents with tools, not bare models.

- **Three provider types behind one interface** (`AgentProvider` creates an `Agent`; an agent takes a message and yields messages). `sdk` is the Claude Agent SDK, signed in by account login, with its own file and shell tools. `openai-oauth` is Codex by OpenAI login, with its own sandbox. `openai` is any OpenAI-compatible chat endpoint, and for that one Squadron runs the tool loop itself with its own file and shell tools, confined to a directory.
- **Profiles** name an endpoint and how to sign in: `openai`, `openrouter`, `local` (a compatible server on the machine), `gemini`, `sdk`, `openai-oauth`. A user file adds more.
- **It knows what is usable.** Each profile has a sign-in strategy that reports whether its credentials are valid, where they came from, and what to do if they are missing. `sq auth status` lists every profile this way; `sq auth login` and `logout` exist for the account logins.
- **Every call reports usage and cost**, which is what a cost cap sums.
- **Size and coupling:** about 3,900 lines in `src/squadron/providers`, plus about 2,500 in `src/squadron/tools` for the compatible-endpoint tool loop. It imports a small part of the rest of Squadron: the message and agent-config models, usage records, logging and config lookup.

Other runtimes (opencode, Goose) fit the same adapter shape. Gemini's tool is not a base to build on: its docs say it was replaced for some account types in June 2026.

## What the kit builds

- **One store** (SQLite, in the state directory) with tables for events, timers, runs, outgoing messages and outcomes.
- **Intake.** Two ways in, both writing events with a dedup id: a small HTTP handler for webhooks, and polling sources run on a timer. Polling through the person's own tools needs no inbound network, which is what a work machine usually allows.
- **One process that stays up.** Each pass turns due timers into events and starts a run for any agent with pending events. One run per agent at a time; events that arrive mid-run wait for the next.
- **A runner over the provider layer.** Each run is one child process that hosts one provider agent in the agent's working directory, with the caps from the definition. The runner enforces time and cost itself (cost from the usage each call reports), records the outcome and the session id, and kills the whole process group at the limit. The first build supports Anthropic by account login.
- **A provider status view.** Which providers are signed in and usable right now, and what to do about one that is not.
- **A network door.** The staying-up process serves its commands and its webhook intake over HTTP, behind access control, so the command line is a client that can point at another machine.
- **A container image** that starts the staying-up process, with the state directory and each person's sign-in kept outside the image.
- **Timers.** Follow-ups an agent sets for itself and schedules from the definition. Each has an expiry.
- **Memory.** A folder per agent: instructions, an index, notes, progress per ongoing item, and what has already been reported. The index and instructions load every run. A scheduled curation pass merges repeats, replaces stale entries and keeps to the size limit.
- **Outcomes.** A record per judged action, closed when later evidence says whether it held, and a per-agent rate in the status view.
- **Outgoing messages.** What the agent tells its person, written to the store and delivered by a dispatcher, so a failed send is retried and nothing is sent twice. It starts quiet.
- **Waiting on a person.** An action the definition marks as needing approval ends the run with the session saved. The answer comes back as an event and the run resumes. A waiting item expires after an age set in the definition and is closed and recorded.
- **One definition file per agent:** whose it is, runtime, model, caps, triggers, tools and connections, what needs approval, memory location and size limit, instructions.
- **Commands:** create an agent from a definition, list agents and their last runs, show a run's log, cancel a run, remove an agent.
- **Documentation an agent can act on:** the definition's keys and commands described so that an AI agent can use the kit from the docs alone (requirement 6).

**When a cap is hit:** the run ends and is recorded with what it did. The item is retried once on the next wake. A second failure closes the item as failed and tells the person once.

**Identity.** The definition names the person. The kit runs that agent as that person's OS user, with that person's config directory, and loads no credential of its own. A machine that hosts agents for several people runs each under its own user. In a container, the person's credential is given to that container alone, by the method its definition names (a login token or an API key). The kit never copies a credential between people.

**No self-triggering.** What an agent writes during a run never becomes an event for that same agent. A run ends, and only a new outside event, a due timer or a person's answer starts the next.

## First agents

In no fixed order. The PM names the first (Build order, item 2).

1. **PR review responder (personal and work).** Wakes when a review lands on the person's pull request, from Copilot or a human's AI review. It reads every finding, sorts real problems from noise (a rare edge case rated high is the usual noise), fixes the real ones on the branch, replies on each thread with what it did or why the finding does not hold, pushes, and asks for re-review. Its person hears about a finding that is a real design question and about a pull request that is ready to merge. Its outcome records are the calls people overturned, so its sorting improves. It uses whatever review-combing tools the person has installed.
2. **Amoeba's persistent agent (personal).** See Build order, item 3.
3. **Reviewer (personal, then work).** Named by the PM on 20261122: one long-running agent handles reviewing, and a review must be measurable and trusted. It lives long enough to see what became of what it approved, which a one-shot reviewer cannot.
4. **Issue triage (work and personal).** Labels and categorizes new issues, marks the ones an agent can resolve, resolves those through a pull request, and leaves the rest sorted for people.
5. **Tracker sync.** Keeps issues and a project tool such as ClickUp in step in both directions.

## Out of scope

- **An agent loop of its own.** The provider layer has one for every provider type.
- **A safety classifier of its own.** The runtime has one.
- **A credential proxy.** Each agent runs as its person on a machine that person or their employer controls. A proxy is needed only for an agent running somewhere neither controls, which this kit does not do.
- **A hosted service.** The kit runs on machines the PM or his employer has.
- **Agents talking to each other.** That is Amoeba's messaging.

## Rules the new project inherits

These come from Amoeba's design rules and from what went wrong there.

- **Every state has an exit, and every limit says what happens when it is hit.** "Wait for a person who has no command to act with" is not an answer.
- **Config is config; state is state.** The definition file and user config live in the repo or `~/.config/<app>`. Stores, run records, memory, logs and caches live in `~/.local/state/<app>` (or `$XDG_STATE_HOME`).
- **No step waits on the PM** except the approval path, which expires on its own.
- **Values come from config,** never from a silent default in code.
- **The designer walks the design as its operator:** start, normal path, each failure, the end state, and how to clear or undo it.
- **Nothing is deferred.** In-scope behaviour is built in its slice or deleted from the design.

Three lessons from Amoeba's session hooks, observed 20261122:

- A model that wrote instructions in the PM's name issued orders he never gave. This is why requirement 2 exists.
- A hook that forced an extra turn after every message fed a second hook, and the pair looped. This is why a run never triggers itself.
- Hooks that ran from the source checkout changed behaviour in every session the moment a file was edited. This is why requirement 8 exists.

## What can be taken from Amoeba

Optional, to save time; the kit must be buildable without it. Amoeba (`amoeba-ai` on PyPI) has working versions of several parts, and they are copied at the start, not imported: the dedup inbox with read cursors, the wake wrapper with a time cap and process-group kill, the cleaned environment for a started command (`src/amoeba/operations/wake_environment.py`), run rows and logs, and pruning by age. In Amoeba's repo, `project-documents/user/notes/008-code-sort.amoeba.md` lists the groups and `docs/cli-contract.md` ("The wake command") describes the wrapper.

Amoeba keeps its own copies until its persistent agent moves onto the kit. At that point Amoeba depends on the kit, deletes its copies, and keeps what only it does: the hub, programs, messages between repos, and the record of the PM's decisions.

## For the architecture to settle

1. The definition file's exact keys, and how tools and connections are declared per runtime.
2. How the cost cap is computed for a runtime with no budget flag.
3. The polling sources in the first build (GitHub reviews and issues, mail) and the webhook handler's access control.
4. How the staying-up process starts and restarts, on macOS and in a Docker container on a Linux VM.
5. How approval requests reach a person and how the answer gets back as an event. The channel is an adapter, chosen in the definition.
6. Which surfaces make the kit adoptable by an AI agent (an `AGENTS.md`, an `llms.txt`, a skill, an MCP server with instructions), and the exact form of the adoption test in requirement 6.
7. For each first agent, which later evidence closes an outcome record, and how the kit learns of it.
8. **How the kit gets Squadron's provider layer.** Three ways: copy it into the kit, depend on Squadron as a library, or move it into its own package that both use. Recommended, not yet confirmed by the PM: a separate installable package inside the kit's repo, started as a copy of Squadron's provider and tool code, with the kit using it through one adapter module. Squadron switches to that package later and deletes its copy. This does not touch Squadron now, and it leaves one copy at the end.
9. How an account login (Anthropic, OpenAI) is made, kept and refreshed for an agent running in a container.
10. What controls access to the network door, and what it exposes.
11. On the machine that runs Amoeba's hub, whether the hub and the kit's staying-up process are one process or two. This is settled when Amoeba's agent moves onto the kit and blocks nothing before then.

## Only the PM can supply

1. **Where the project lives and what it is called.** Asked once, at the start.
2. **Which agent is first.** He says when the substrate runs.
