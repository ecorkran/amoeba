---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261121
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`, rewritten 20261120: Amoeba is an agent that stands in for the PM. The earlier versions of this plan are in git history. `notes/008-code-sort.amoeba.md` sorts today's code against the new concept. Updated 20261121 for the kit-first build order (`notes/007-agent-kit-concept.amoeba.md`, decided 20261120).

## Index Convention

**20-based** (100, 120, 140, ...), the guide default. Indices are tentative and may be reassigned. Retired indices stay listed so that existing documents keep their meaning. 280 is left unused: it was briefly the working number for what became slices 230 to 232.

## Decomposition rationale

The concept's build order is the decomposition. Each step is something that runs and is useful before the next one exists, and each later step builds on the one before:

1. Amoeba on a machine that never sleeps, reachable from every machine the PM works on (260).
2. Amoeba on the agent kit, which is built in its own project (300).
3. The stand-in agent, which is the product, as the kit's second agent (320).

Initiatives 100 to 240 are built. They are not redone. Each new initiative says what it keeps, changes and deletes from them, using the code sort.

The kit is built first, in its own project, for one real agent: the PR review responder. Amoeba does not build the parts any long-running agent needs (timers, memory curation, outgoing messages, runtime adapters, the cost cap); it takes them from the kit. The stand-in is the kit's second agent, and putting it on the kit is what shows which parts are general. The review responder, the work prototype and its enterprise layer (single sign-on and per-person access for a team) are built on the kit in other projects and are not in this plan.

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — Built: the SQLite store and related contracts. Its store base is kept as agent core. Dependencies: None. Status: complete
2. [x] **(120) Runner** — Built: launching and watching Squadron runs, resuming runs that stopped for a transient reason. Cut down by 220. Dependencies: [100]. Status: complete
3. [x] **(140) Question Answerer** — Built: the question record, source passages and the two-step answering pipeline with no tools. The record is kept and widened by 320. The pipeline is deleted by 320. Dependencies: [100, 120]. Status: complete
4. [ ] **(160) Translator & Notification** — Retired 20261106. Status: deprecated
5. [ ] **(180) Program Coordination** — Retired 20261106. Slices 180 and 181 are merged. What programs still needed moved to 220 and 240. Status: deprecated
6. [ ] **(200) Multi-Agent Chat** — Retired 20261106. Agent-to-agent messages came back as 240. Status: deprecated
7. [x] **(220) Program Tool** — Built, slices 220 to 230: one set of operations over MCP and a CLI, answering on runs Amoeba did not launch, the program record, the decision record, and standing answers. Closed 20261120. Slices 231 (work, then resume) and 232 (dreaming) are dropped: 320 does the first with an agent that decides, and 300 does the second as memory curation. Dependencies: [100, 120, 140]. Status: complete
8. [x] **(240) Agent Messaging** — Built: durable requests and notes between repos, push and presence, hold and release, waking, release notes. Kept. Its inbox and wake wrapper are copied into the kit at its start; Amoeba deletes its own copies in 300. Dependencies: [220]. Status: complete
9. [ ] **(260) The Hub** — Amoeba on one machine on the PM's LAN that does not sleep, with every machine the PM works on as a client. Rewritten 20261120 and moved to the front: Amoeba loses most of its purpose on one machine. Scope:
   - **One process that stays up,** in a container, holding the store. It starts at boot and restarts on failure.
   - **A network door** over the existing operations, beside the CLI and MCP doors, with access control from the first slice.
   - **Client mode.** `amoeba` and `amoeba-mcp` on any machine talk to the hub and never open a store. The hub's address is one config value.
   - **Members known by name across machines.** A client resolves its own repo locally; the hub resolves a recipient from the store. Registration is cut down to fit (it is about 3,000 lines today).
   - **A directory:** which sessions are working where, across machines.
   - **An owner on every record,** which today is always the PM.
   - **Moving the PM's live store to the hub,** with a backup and a stated restore path, and deleting the finished one-time state move.

   Out of scope: finding the hub automatically on the LAN, and more than one person using a hub. Dependencies: [240]. Status: in_progress
10. [ ] **(300) Amoeba on the Kit** — Amoeba takes the agent kit as a dependency in place of building an agent core. The kit is built in its own project (`notes/007-agent-kit-concept.amoeba.md`); this initiative starts when its first build runs the PR review responder unattended. Rewritten 20261121; it was "Agent Core", the same parts built inside Amoeba. Scope:
    - **The kit's process on the hub.** The kit's stay-up process runs beside the hub on the LAN machine, or the hub is that process. Which of the two is the architecture's call (007 lists it as open).
    - **Amoeba's events into the kit's inbox:** messages between repos, paused runs and, from 320, hand-offs from sessions. Amoeba's hub, programs, messages between repos and the record of the PM's decisions stay in Amoeba.
    - **Deleting Amoeba's copies** of what the kit now holds: the dedup inbox with read cursors, the wake wrapper with its time cap and process-group kill, the cleaned environment for a started command, run rows and logs, and pruning by age (`notes/008-code-sort.amoeba.md` lists where they are).
    - **A kit gap Amoeba hits is fixed in the kit,** not worked around in Amoeba.

    Out of scope: building timers, memory curation, outgoing messages, runtime adapters or a cost cap in Amoeba. Dependencies: [260]. Status: not_started
11. [ ] **(320) The Stand-In** — The agent that takes everything another agent would hand to the PM. It is the product. Scope:
    - **Entry points:** the end of each turn in an interactive session, a paused pipeline run, a finished pipeline run, and a direct ask. An entry point that cannot reach Amoeba fails loudly.
    - **First-level chaos first.** Needless questions get answered so the agent keeps working. Leftovers get finished, or the agent is sent back to finish them.
    - **Real questions,** answered from the code, the plans, the history, the repo's rules, other repos in the program and the PM's earlier decisions. It matches by meaning and decides by default.
    - **The case record.** The question record widens to a case: any hand-off, what Amoeba looked at, what it decided and why, and the commits it made.
    - **Learning.** Past cases are read before deciding. An overrule from the PM is stored against its case and the newest word wins. Leftovers are cases too.
    - **Dreaming,** carried over from dropped slice 232. With nobody asking, a scheduled pass on the kit's memory curation goes over the PM's answers and Amoeba's cases in every repo. It finds a ruling that should hold beyond the repo it was given in and makes it a standing answer with the reach it fits: one repo, one program, or everything. It withdraws a standing answer that a later PM answer contradicts. It merges repeated cases into one general note. Each change takes effect at once and appears in the list of what was decided, where the PM can overrule it. The PM can also tell any agent that a given answer holds everywhere.
    - **What reaches the PM,** as the concept lists it, and how each waiting item ends.
    - **Deleting the answering pipeline** (about 2,700 lines) and the rules that decided which pauses could be answered.

    The stand-in is an agent defined and run by the kit. Dependencies: [300]. Status: not_started
12. [ ] **(340) Git Agent** — Retired 20261121. The review responder is the kit's first agent and is built in the kit project, with issue triage after it. It proves the kit's parts are general there, not here. Status: deprecated
13. [ ] **(360) Kit Extraction** — Retired 20261121. The kit is built first in its own project, so nothing is extracted from Amoeba. Amoeba's move onto it is 300. Status: deprecated

<!-- Status takes only: not_started | in_progress | complete | deferred | deprecated -->

## Cross-Initiative Dependencies

- **260 depends on 240.** It carries 240's messages, presence and waking across machines. It reverses "no process kept running" and changes member lookup, which goes through the local Context Forge for every call today.
- **300 depends on 260 and on the kit's first build.** The kit's stay-up process needs the hub's machine, and events from other machines need the hub's door. It replaces 240's inbox and wake wrapper with the kit's.
- **320 depends on 300.** The stand-in is an agent defined and run by the kit. It widens 140's question record, keeps 220's standing answers as the PM's instructions, keeps 220's pause entry, and deletes 140's answering pipeline.

## External Dependencies

- **The agent kit**, built in its own project from 20261120 (`notes/007-agent-kit-concept.amoeba.md`). 300 starts when its first build runs the PR review responder unattended on the PM's own repos. Check what it holds then; do not copy a status from this plan.
- **Claude Code**, read 20261120: without a window it takes a turn cap and a cost cap; a hook at the end of a turn can block the stop and give the agent text to continue with; a hook can defer a tool call so the run ends saved and resumes later. None of the runtimes checked has a wall-clock limit. Architecture re-checks each of these before depending on it.
- **Squadron.** A pipeline step on a Claude model runs through the Agent SDK and loads the repo's settings, not the PM's user settings, unless `pipeline.user_settings` is on. So a turn-end hook reaches pipeline runs only through the repo's settings or that key. A run on any other provider has no hooks; for those, the entry points are the pause and the finished run.
- **`ecorkran/squadron#302`** (a command started when a run pauses) and **`#303`** (working directory in the run file, JSON from `sq runs list`): closed, checked 20261120. **`#304`** (a pipeline step that runs a command): open, and nothing here needs it.
- **Codex**, read 20261120: runs without a window and resumes a session. No turn, time or cost cap was found, so the runner enforces all three.

## Sequencing

`260 → 300 → 320`, with 300 also waiting on the kit's first build.

Within each initiative: architecture and its review, then the slice plan, then slices. 260's architecture starts from this plan's scope, not from the earlier 260 entry.

## Notes

- The older architecture documents (`100-arch` to `240-arch`) describe what was built. Where they differ from the concept, the concept governs.
- **Hooks and non-Claude runs get a closer look in 320's architecture** (PM, 20261120). The current answer is good enough to start: Claude Code's turn-end hook where it exists, the pause and the finished run everywhere else. 320's architecture checks what each runtime the PM uses offers at the end of a turn, Codex and Squadron's other providers included, and whether a run on those can be caught as early as a Claude one.
- A needless question or a leftover that still reaches the PM is a defect in Amoeba and is fixed there.
- A design that handles one named case and sends the rest to the PM is rejected in review.
- Check off initiatives as their architecture documents and slice plans are complete.
