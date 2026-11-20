---
docType: notes
layer: project
project: amoeba
audience: [human, ai]
description: Amoeba's source sorted against the 20261120 concept into agent core (candidates for the kit), stand-in (stays in Amoeba), and dead. Line counts per group, a verdict for each, and what is missing entirely.
dependsOn: [project-guides/000-concept.amoeba.md, notes/007-agent-kit-concept.amoeba.md]
dateCreated: 20261120
dateUpdated: 20261120
status: in-progress
---

# Code sort against the 20261120 concept

Measured 20261120 on `main`: 27,006 lines in `src/amoeba`, 61,582 in `tests`.

**Method.** Files were grouped by module name and by what the design documents say each module does. They were not read line by line, so a group's verdict is for the group. A file can turn out to belong elsewhere when it is opened.

## The sort

| Group | Lines | Verdict |
|---|---|---|
| **Agent core** | | |
| Store base, config, pruning, call log | 2,299 | Keep. Kit candidate. |
| Inbox, messages and notes | 3,851 | Split. The dedup inbox with read cursors is core. The request states (accept, decline, done, chains, rejections) are Amoeba's messaging between repos and stay in Amoeba. |
| Wake and the bounded run wrapper | 1,010 | Keep. Kit candidate. This is the time cap, process-group kill, cleaned environment, run rows and logs. |
| Sessions and presence | 646 | Keep. It becomes the hub's directory of who is working where. |
| One-time move of state out of `~/.config` | 679 | Dead once the PM's install is confirmed moved. A state directory exists at `~/.local/state/amoeba`. |
| **Stand-in (stays in Amoeba)** | | |
| Question and decision record | 2,866 | Keep and widen. Today a record is a question from a paused run. It becomes a case: any hand-off, what Amoeba looked at, what it decided, and the PM's correction. |
| Standing answers | 634 | Keep. They are the PM's explicit instructions in memory. |
| Pause entry and reads of Squadron run state | 2,935 | Keep the entry: notice the pause, claim it, resume the run. The parts that decide which pauses may be answered shrink, because the agent now decides. |
| Programs and releases | 2,090 | Keep as is. Not part of the agent, and nothing in the new concept changes it. |
| Registration (`add`, `rm`, set-up) and reads of Context Forge | 2,997 | Change. It is large for what it does and resolves every member through the local Context Forge. The hub needs members known by name across machines. |
| **Dead** | | |
| Answering pipeline: passages, source reads, rule imports, the cite-or-decline gate | 2,717 | Delete. An agent with tools reads the repo itself. |
| **Shell** | | |
| CLI, MCP server, status and list views, wiring | 4,282 | Keep. It follows whatever the operations become. |

Totals: about 7,800 lines of agent core, 11,500 of stand-in, 4,300 of shell, and 3,400 dead or soon dead.

## What does not exist yet

None of these has any code today.

- The always-up process and its HTTP door, so other machines are clients.
- Timers: follow-ups and schedules, and the scheduler pass.
- Memory beyond standing answers, and the curation pass.
- The runner: start a command from a definition, enforce time and cost caps, record the outcome.
- The definition file.
- The stand-in agent itself.
- The session turn-end entry point and the finished-run check.
- Outgoing messages with a dispatcher.
- An owner on every record.

## What this says about Amoeba

- **About a third of the code is the plumbing a long-running agent needs,** and it works: a durable inbox, bounded runs, logs, cleanup.
- **About a tenth is the part that was built to refuse,** and it goes.
- **The rest is record-keeping and registration** that the stand-in still uses, some of it oversized.
- **The agent itself was never built.** Everything under "What does not exist yet" is the product described in the concept.
