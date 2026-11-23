---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261122
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`, rewritten 20261120: Amoeba is an agent that stands in for the PM. Its defining purpose is taking questions off the PM's plate, measured by how many still reach him. The earlier versions of this plan are in git history. `notes/008-code-sort.amoeba.md` sorts today's code against the new concept.

Reordered 20261121 by the PM: every initiative is judged by whether it reduces the questions that reach the PM. That measure stands.

Reordered again 20261122 by the PM, replacing the order and the no-kit decision of 20261121:

- **The hub goes first.** What the PM needs from Amoeba is one coherent place: he, the session agents in every repo, and one persistent agent that can see what is going on. The hub is the plumbing of that place.
- **The agent parts come from `agent-kit`,** which the PM created as its own project on 20261122 (`repos/manta/agent-kit`; its own concept governs, and `notes/007-agent-kit-concept.amoeba.md` is only the hand-off). Amoeba builds no loop, timer, scheduler, runner, cost cap or memory curation.
- **The stand-in is built on the kit, after the hub,** once the kit has a general substrate. The kit's first build is one simplified review agent that uses Squadron as a library; the general substrate comes out of that afterwards, so this is more than one kit build away. Standing in for the PM is one function of Amoeba's persistent agent, not the whole of it.
- **Why:** the stand-in's first piece, the turn-end hook, ran for two days. Alone, it cut needless questions. It also issued orders the PM never gave (`#46`, fixed in 0.2.5), and a second hook added beside it (answer-first) made the pair loop and was removed. A model writing decisions in the PM's name is the weak part, and it is not built further until it runs on the kit, bounded and measured.

## Index Convention

**20-based** (100, 120, 140, ...), the guide default. Indices are tentative and may be reassigned. Retired indices stay listed so that existing documents keep their meaning. 280 is left unused: it was briefly the working number for what became slices 230 to 232.

## Decomposition rationale

Each step runs and is useful before the next one exists, and the order is set by the one measure:

1. The hub, so agents on every machine reach one Amoeba with one record of the PM's decisions (260).
2. The stand-in, built on `agent-kit` (320). Its first piece, the turn-end hook, was built 20261121 and stays in use as a stopgap; it gets no new behaviour.

Initiatives 100 to 240 are built. They are not redone. Each new initiative says what it keeps, changes and deletes from them, using the code sort.

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — Built: the SQLite store and related contracts. Dependencies: None. Status: complete
2. [x] **(120) Runner** — Built: launching and watching Squadron runs, resuming runs that stopped for a transient reason. Cut down by 220. Dependencies: [100]. Status: complete
3. [x] **(140) Question Answerer** — Built: the question record, source passages and the two-step answering pipeline with no tools. The record is kept and widened by 320. The pipeline is deleted by 320. Dependencies: [100, 120]. Status: complete
4. [ ] **(160) Translator & Notification** — Retired 20261106. Status: deprecated
5. [ ] **(180) Program Coordination** — Retired 20261106. Slices 180 and 181 are merged. What programs still needed moved to 220 and 240. Status: deprecated
6. [ ] **(200) Multi-Agent Chat** — Retired 20261106. Agent-to-agent messages came back as 240. Status: deprecated
7. [x] **(220) Program Tool** — Built, slices 220 to 230: one set of operations over MCP and a CLI, answering on runs Amoeba did not launch, the program record, the decision record, and standing answers. Closed 20261120. Slices 231 (work, then resume) and 232 (dreaming) are dropped; 320 covers both. Dependencies: [100, 120, 140]. Status: complete
8. [x] **(240) Agent Messaging** — Built: durable requests and notes between repos, push and presence, hold and release, waking, release notes. Kept. Dependencies: [220]. Status: complete
9. [ ] **(320) The Stand-In** — The agent that takes everything another agent would hand to the PM. It follows the hub and is built on `agent-kit` once the kit's substrate runs. Scope:
    - **Entry points:** the end of each turn in an interactive session (built 20261121: `amoeba stand-in`, a Claude Code `Stop` hook in the PM's user settings; since 0.2.5 it is shown the PM's last messages and settles only what blocks work he asked for), a paused pipeline run, a finished pipeline run, and a direct ask. An entry point that cannot reach Amoeba fails loudly.
    - **First-level chaos first.** Needless questions get answered so the agent keeps working. Leftovers get finished, or the agent is sent back to finish them.
    - **Real questions,** answered from the code, the plans, the history, the repo's rules, other repos in the program and the PM's earlier decisions. It matches by meaning and decides by default.
    - **The case record.** The question record widens to a case: any hand-off, what Amoeba looked at, what it decided and why, and the commits it made. The turn-end hook's day log is replaced by it.
    - **Learning.** Past cases are read before deciding. An overrule from the PM is stored against its case and the newest word wins. Leftovers are cases too.
    - **Dreaming,** carried over from dropped slice 232. With nobody asking, a scheduled pass goes over the PM's answers and Amoeba's cases in every repo. It finds a ruling that should hold beyond the repo it was given in and makes it a standing answer with the reach it fits: one repo, one program, or everything. It withdraws a standing answer that a later PM answer contradicts. It merges repeated cases into one general note. Each change takes effect at once and appears in the list of what was decided, where the PM can overrule it. The timer and the curation pass come from the kit.
    - **What reaches the PM,** as the concept lists it, and how each waiting item ends.
    - **Deleting the answering pipeline** (about 2,700 lines) and the rules that decided which pauses could be answered.

    Dependencies: [220, 240, 260], and `agent-kit` (an outside project). Status: in_progress
10. [ ] **(260) The Hub** — Amoeba on one machine on the PM's LAN that does not sleep, with every machine the PM works on as a client. First (20261122): sessions on every machine reach one Amoeba with one record of the PM's decisions, and the persistent agent later lives there. Its architecture and five slice designs (260 to 264) are written and reviewed, and 261's tasks are broken down. The stand-in's case record is carried to every machine by 320, when it is built. Scope:
    - **One process that stays up,** in a container, holding the store. It starts at boot and restarts on failure.
    - **A network door** over the existing operations, beside the CLI and MCP doors, with access control from the first slice.
    - **Client mode.** `amoeba` and `amoeba-mcp` on any machine talk to the hub and never open a store. A machine joins with one command run on that machine only.
    - **Members known by name across machines.** A client resolves its own repo locally; the hub resolves a recipient from the store.
    - **A directory:** which sessions are working where, across machines.
    - **An owner on every record,** which today is always the PM.
    - **Moving the PM's live store to the hub,** with a backup and a stated restore path, and deleting the finished one-time state move.

    Out of scope: finding the hub automatically on the LAN, and more than one person using a hub. Dependencies: [240]. Status: in_progress
11. [ ] **(300) Amoeba on the Kit** — Retired 20261121 by the PM, and it stays retired: no separate move is needed, because 320 is built on `agent-kit` from its start. The parts 300 would have held (the runner, timers, the scheduler) are the kit's. Amoeba's own copies of kit parts (the inbox and the bounded-run wrapper) are deleted when 320 lands. Status: deprecated
12. [ ] **(340) Git Agent** — Retired 20261121. Status: deprecated
13. [ ] **(360) Kit Extraction** — Retired 20261121. Status: deprecated

<!-- Status takes only: not_started | in_progress | complete | deferred | deprecated -->

## Cross-Initiative Dependencies

- **320 depends on 220 and 240,** both built, on 260, and on `agent-kit`. It carries its case record to every machine through the hub. It widens 140's question record into the case record, keeps 220's standing answers as the PM's instructions, keeps 220's pause entry, and deletes 140's answering pipeline.
- **260 depends on 240.** It carries 240's messages, presence and waking across machines. It reverses "no process kept running" and changes member lookup, which goes through the local Context Forge for every call today.

## External Dependencies

- **Claude Code**, checked 20261121 against 2.1.325 and its hooks documentation: a `Stop` hook receives the agent's final text as `last_assistant_message`, blocks the stop with `{"decision": "block", "reason": ...}`, re-fires with `stop_hook_active` true, is overridden after eight blocks in a row, and does not fire on a user interrupt. `SubagentStop` is a separate event. Hooks do not run under `claude -p --bare`.
- **Squadron.** A pipeline step on a Claude model runs through the Agent SDK and loads the repo's settings, not the PM's user settings, unless `pipeline.user_settings` is on. So a turn-end hook reaches pipeline runs only through the repo's settings or that key. A run on any other provider has no hooks; for those, the entry points are the pause and the finished run. `ecorkran/squadron#382` (reviews that read the whole document) was closed 20261121, so designs are reviewed through Squadron again.
- **agent-kit**, created 20261122 and not yet built: the PM's own project for long-running agents. 320 needs its general substrate (a definition file that becomes a bounded, remembering agent), which follows the kit's first build, a single review agent. 260 needs nothing from it.
- **Codex**, read 20261120: runs without a window and resumes a session. No turn, time or cost cap was found, so the runner enforces all three.

## Sequencing

`260 → 320`. 320 also waits for `agent-kit`'s substrate.

Within each initiative: architecture, then the slice plan, then slices. 320's first slice, the turn-end hook, was built ahead of its architecture on 20261121, and its architecture starts from what that hook did in use, including its misses.

## Notes

- The older architecture documents (`100-arch` to `240-arch`) describe what was built. Where they differ from the concept, the concept governs.
- **Hooks and non-Claude runs get a closer look in 320's architecture.** The current answer: Claude Code's turn-end hook where it exists, the pause and the finished run everywhere else. 320's architecture checks what each runtime the PM uses offers at the end of a turn, Codex and Squadron's other providers included.
- A needless question or a leftover that still reaches the PM is a defect in Amoeba and is fixed there.
- A design that handles one named case and sends the rest to the PM is rejected in review.
- Check off initiatives as their architecture documents and slice plans are complete.
