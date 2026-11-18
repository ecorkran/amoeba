---
docType: notes
layer: project
project: amoeba
audience: [human, ai]
description: Hand-off brief for a separate session. How to make long-running (always-on) agents easy to define, package and run, starting from what Amoeba 0.2.0 already provides. Problem statement, existing parts, gaps, a proposed shape and open questions; no design decided.
dateCreated: 20261117
dateUpdated: 20261117
status: in-progress
---

# Long-running agents: packaging brief

## What this is

A brief to hand to another session or project. The PM wants long-running agents to be
easy to create and package: you write a small definition, and the agent then wakes
when there is work, does a bounded piece of it, remembers what it learned, and goes
back to sleep. Nobody babysits it, and it can never run without a limit.

Background reading: Anthropic's article "Building always-on agents"
(https://claude.com/resources/articles/building-always-on-agents). Amoeba
(this repo, `amoeba-ai` on PyPI, 0.2.0) already has most of the runtime parts
described there. What's missing is the packaging: today, turning a repo into an
always-on agent means hand-writing a script and wiring it up yourself.

## What a long-running agent needs

1. **Triggers.** Something wakes it: a message, a timer, an outside event.
2. **A durable inbox.** Work survives the agent not running. Dedup ids and read cursors
   mean nothing is processed twice or lost.
3. **A bounded worker.** Each wake is one process with a time cap and a cost cap, and
   at most one runs per inbox.
4. **Rules.** It reads how to behave from the repo's own rules (CLAUDE.md, AGENTS.md),
   not from a copy.
5. **Memory and curation.** It keeps what it learned across wakes. A periodic pass
   ("dreaming" in the article) replaces stale entries, so old memory doesn't
   quietly steer new work wrong.
6. **Credentials.** It loads its own secrets. Nothing leaks from whoever triggered it.
7. **Observability.** Logs per run, a status view, and a record of each run's outcome.
8. **An exit for every state.** Every run, limit and stored record ends on its own:
   completion, expiry or an explicit cancel. No state waits on a person who has no
   command to act with.

## What Amoeba 0.2.0 already provides

| Need | Amoeba part | Where |
|---|---|---|
| Durable inbox | requests and notes in one SQLite store, with dedup ids and `as_of_seq` / `read_through` cursors | slices 240, 243; `docs/cli-contract.md` |
| Push when awake | MCP channel event that says "mail arrived" (counts only, never text); live-session rows | slice 241; `docs/mcp-server.md` |
| Trigger when asleep | `wake_command` per member, started on `send` when there's no live session | slice 244; `docs/cli-contract.md`, "The wake command" |
| Bounded worker | `wake_timeout_seconds` (Amoeba kills the process group), `max_wakes_per_day`, one running wake per member | slice 244 |
| Clean environment | the command gets only `WAKE_ENV_NAMES` (`PATH`, `HOME`, `AMOEBA_HOME`, `CONTEXT_FORGE_DATA_DIR`, ...) and loads its own secrets | `src/amoeba/operations/wake_environment.py` |
| Observability | a `wakes` row per run (`exited`, `timed_out`, `start_failed`, `wrapper_failed`), logs in `<state>/logs/wake/`, a **Waking** section in `list` and `status` | slice 244 |
| Deferred approval | a run blocked on another repo is held and resumed when the request ends | slice 242 (hold and release) |
| Rules | answering reads the repo's CLAUDE.md and imports, never a copy | slice 140 series |
| Cleanup | rows, notes and logs pruned by `prune_after_days` | slices 243, 244 |

## The gaps

- **No packaging.** A wake command is any program. The only example in the docs is
  `python3 /home/pm/bin/wake_agent.py --max-seconds 600`, and nobody has written a
  standard one. Each agent needs its own script that launches a model runtime with the
  right caps, tells it to check `inbox`, handle requests and check `inbox` again, then
  exits. The command also has to carry its own cost or time cap, because it is the only
  bound if Amoeba's wrapper gets killed.
- **Triggers only on `send`.** There are no timers ("check back at 3pm if nobody
  replied"), no schedules (a nightly run), no re-wake after a timeout, and no outside
  events.
- **No agent memory beyond the inbox.** Stored PM answers are the closest thing, and
  the only way to clean them up is a manual `retract`. A curation pass is being looked
  at separately inside Amoeba (stored-answer "dreaming").
- **No single definition.** An agent's setup is scattered across Context Forge
  registration, `amoeba add` flags, a script somewhere on disk, the repo's rules and
  config keys. You can't copy one file to make a second agent.
- **Runtime choice is open.** Claude Code headless (`claude -p`), the Claude Agent SDK,
  Codex, or a hosted option such as Claude Managed Agents. Each one caps cost and turns
  differently. Check the current flags and APIs before designing around any of them.

## A proposed shape (a starting point, not a decision)

One definition file per agent, checked into the repo it works in, plus one generic
runner that serves as the wake command for every agent.

```yaml
# .amoeba/agent.yaml  (illustrative; every key name is open)
name: billing-agent
runtime: claude-code          # or agent-sdk, codex, ...
model: <model id>             # from config, never a silent default
caps:
  seconds: 900                # the runner enforces this even if Amoeba's wrapper dies
  usd: 2.00
  turns: 40
triggers:
  on_request: true            # today's 244 behaviour
  schedule: "0 6 * * *"       # new
  follow_up: true             # agent may set its own re-wake timer (new)
memory:
  file: .amoeba/memory.md     # or a store table; see curation work
  curate: weekly
instructions: |               # appended to the repo's own rules, never replacing them
  Check inbox first and last. Accept before working. Decline with a reason when the
  rules do not settle it.
```

- **`amoeba agent init`** writes the file, registers the member and sets its wake
  command to the generic runner. One command takes a repo from nothing to a working
  agent.
- **The generic runner** reads the file, starts the chosen runtime in the checkout with
  the caps enforced inside the runner itself, records the outcome, and exits. It
  replaces every hand-written `wake_agent.py`.
- **Timers and schedules** become store rows with a due time, picked up by the same
  sweep that already prunes state. Each timer has a cap and an expiry.

## Rules to carry over (from Amoeba's design rules)

- Every state has an exit. Every cap says what happens when it's hit.
- Config is config, state is state. The definition file and user config live in the
  repo or `~/.config/<app>`. Run records, memory stores, logs and caches live in
  `~/.local/state/<app>`.
- No step waits on the PM. A default that needs a person to pick it is a bug.
- Values come from config, never from silent fallbacks in code.
- Whoever writes the design does the operator walkthrough: start, normal path, each
  failure, end state, undo.

## Open questions for the next session

1. Does this belong in Amoeba (it already owns the inbox, wakes and store), in a
   separate small package that depends on Amoeba, or in Squadron? Current lean:
   Amoeba, because triggers and run records are already there and a second store would
   duplicate them.
2. Which runtimes come first, and how does each enforce a hard cost cap rather than
   just a turn cap?
3. Does agent memory go in a file in the repo (diffable, reviewable) or in the store
   (queryable, curatable, shared with the stored-answer curation)?
4. What does "package" mean here: a definition file plus the generic runner, a
   template repo, or something installable (`uvx`, a container)?
5. Should an agent be able to run on another machine or in the cloud, or is "runs as
   the PM, on the PM's machine" a fixed boundary? Today it's fixed, and that is why
   the article's credential proxy and safety classifiers don't apply.
