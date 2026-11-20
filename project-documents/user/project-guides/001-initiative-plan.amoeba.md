---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261120
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`, rewritten 20261120: Amoeba is an agent that stands in for the PM. The earlier versions of this plan are in git history. `notes/008-code-sort.amoeba.md` sorts today's code against the new concept.

## Index Convention

**20-based** (100, 120, 140, ...), the guide default. Indices are tentative and may be reassigned. Retired indices stay listed so that existing documents keep their meaning. 280 is left unused: it was briefly the working number for what became slices 230 to 232.

## Decomposition rationale

The concept's build order is the decomposition. Each step is something that runs and is useful before the next one exists, and each later step builds on the one before:

1. Amoeba on a machine that never sleeps, reachable from every machine the PM works on (260).
2. The parts any long-running agent needs (300).
3. The stand-in agent, which is the product (320).
4. A second, unrelated agent on the same parts (340).
5. The kit, taken out of what the two agents share (360).

Initiatives 100 to 240 are built. They are not redone. Each new initiative says what it keeps, changes and deletes from them, using the code sort.

The kit is last on purpose. It is extracted from two working agents, not designed first. The work prototype and its enterprise layer (single sign-on and per-person access for a team) are built on the kit in another project and are not in this plan.

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — Built: the SQLite store and related contracts. Its store base is kept as agent core. Dependencies: None. Status: complete
2. [x] **(120) Runner** — Built: launching and watching Squadron runs, resuming runs that stopped for a transient reason. Cut down by 220. Dependencies: [100]. Status: complete
3. [x] **(140) Question Answerer** — Built: the question record, source passages and the two-step answering pipeline with no tools. The record is kept and widened by 320. The pipeline is deleted by 320. Dependencies: [100, 120]. Status: complete
4. [ ] **(160) Translator & Notification** — Retired 20261106. Status: deprecated
5. [ ] **(180) Program Coordination** — Retired 20261106. Slices 180 and 181 are merged. What programs still needed moved to 220 and 240. Status: deprecated
6. [ ] **(200) Multi-Agent Chat** — Retired 20261106. Agent-to-agent messages came back as 240. Status: deprecated
7. [x] **(220) Program Tool** — Built, slices 220 to 230: one set of operations over MCP and a CLI, answering on runs Amoeba did not launch, the program record, the decision record, and standing answers. Closed 20261120. Slices 231 (work, then resume) and 232 (dreaming) are dropped: 320 does the first with an agent that decides, and 300 does the second as memory curation. Dependencies: [100, 120, 140]. Status: complete
8. [x] **(240) Agent Messaging** — Built: durable requests and notes between repos, push and presence, hold and release, waking, release notes. Kept. Its inbox and wake wrapper are the start of 300. Dependencies: [220]. Status: complete
9. [ ] **(260) The Hub** — Amoeba on one machine on the PM's LAN that does not sleep, with every machine the PM works on as a client. Rewritten 20261120 and moved to the front: Amoeba loses most of its purpose on one machine. Scope:
   - **One process that stays up,** in a container, holding the store. It starts at boot and restarts on failure.
   - **A network door** over the existing operations, beside the CLI and MCP doors, with access control from the first slice.
   - **Client mode.** `amoeba` and `amoeba-mcp` on any machine talk to the hub and never open a store. The hub's address is one config value.
   - **Members known by name across machines.** A client resolves its own repo locally; the hub resolves a recipient from the store. Registration is cut down to fit (it is about 3,000 lines today).
   - **A directory:** which sessions are working where, across machines.
   - **An owner on every record,** which today is always the PM.
   - **Moving the PM's live store to the hub,** with a backup and a stated restore path, and deleting the finished one-time state move.

   Out of scope: finding the hub automatically on the LAN, and more than one person using a hub. Dependencies: [240]. Status: not_started
10. [ ] **(300) Agent Core** — The parts a long-running agent needs, built inside Amoeba. The model is Anthropic's "Building always-on agents" and `notes/006-long-running-agents.amoeba.md`. Scope:
    - **Events.** The inbox widens from messages between repos to any event, with a dedup id and a status. One run per agent at a time; events that arrive during a run wait for the next.
    - **Timers.** Follow-ups an agent sets for itself and schedules from its definition, each with an expiry. A scheduler pass in the hub's process turns a due timer into an event.
    - **The runner.** It starts the command an agent's definition names (Claude Code or Codex without a window, or a Squadron pipeline), enforces a time cap and a cost cap itself, records the outcome and the session, and kills the whole process group at the limit. A run happens where its files are: on the hub from a clone, or on the client machine that has the working tree.
    - **The definition file:** one per agent, naming its owner, command, model, caps, triggers, tools, what needs a person's approval, and its instructions.
    - **Memory.** Instructions, an index, notes, progress per ongoing item, and what has already been reported. A scheduled curation pass merges repeats and replaces stale entries.
    - **Outgoing messages,** stored and sent by a dispatcher, so a failed send is retried and nothing is sent twice.
    - **Waiting on a person.** A run that needs approval ends with its session saved, and resumes when the answer arrives as an event. A waiting item expires.
    - **A view of it all:** agents, their last runs, a run's log, and a cancel.

    Out of scope: an agent loop, a model layer, a safety classifier and a credential proxy, for the reasons in the concept. Dependencies: [260]. Status: not_started
11. [ ] **(320) The Stand-In** — The agent that takes everything another agent would hand to the PM. It is the product. Scope:
    - **Entry points:** the end of each turn in an interactive session, a paused pipeline run, a finished pipeline run, and a direct ask. An entry point that cannot reach Amoeba fails loudly.
    - **First-level chaos first.** Needless questions get answered so the agent keeps working. Leftovers get finished, or the agent is sent back to finish them.
    - **Real questions,** answered from the code, the plans, the history, the repo's rules, other repos in the program and the PM's earlier decisions. It matches by meaning and decides by default.
    - **The case record.** The question record widens to a case: any hand-off, what Amoeba looked at, what it decided and why, and the commits it made.
    - **Learning.** Past cases are read before deciding. An overrule from the PM is stored against its case and the newest word wins. Leftovers are cases too.
    - **Dreaming,** carried over from dropped slice 232. With nobody asking, a scheduled pass on 300's curation goes over the PM's answers and Amoeba's cases in every repo. It finds a ruling that should hold beyond the repo it was given in and makes it a standing answer with the reach it fits: one repo, one program, or everything. It withdraws a standing answer that a later PM answer contradicts. It merges repeated cases into one general note. Each change takes effect at once and appears in the list of what was decided, where the PM can overrule it. The PM can also tell any agent that a given answer holds everywhere.
    - **What reaches the PM,** as the concept lists it, and how each waiting item ends.
    - **Deleting the answering pipeline** (about 2,700 lines) and the rules that decided which pauses could be answered.

    Dependencies: [300]. Status: not_started
12. [ ] **(340) Git Agent** — A second agent on the same core, for the PM's own repos, running on the hub. Scope:
    - **Review responder.** It wakes when a review lands on one of the PM's pull requests, sorts real findings from noise, fixes the real ones, replies on each thread with what it did or why the finding does not hold, pushes, and asks for re-review.
    - **Issue triage.** It labels and categorizes new issues, marks the ones an agent can resolve, and resolves those through a pull request.
    - **Events from GitHub,** by polling through the PM's own login and by a webhook where the hub can be reached.
    - **Its own memory:** which calls the PM overturned.

    Its purpose beyond its own use is to show which parts of 300 are general. Whatever it cannot use as built gets fixed in 300. Dependencies: [300]. Status: not_started
13. [ ] **(360) Kit Extraction** — Take what 320 and 340 both use out of Amoeba into its own package, with no dependence on Amoeba, Squadron or Context Forge. Amoeba and the git agent then depend on it. `notes/007-agent-kit-concept.amoeba.md` is the draft of where it is heading; it is rewritten from the working code when this starts. Out of scope: single sign-on, per-person access for a team, and the work prototype, which are built on the kit elsewhere. Dependencies: [320, 340]. Status: not_started

<!-- Status takes only: not_started | in_progress | complete | deferred | deprecated -->

## Cross-Initiative Dependencies

- **260 depends on 240.** It carries 240's messages, presence and waking across machines. It reverses "no process kept running" and changes member lookup, which goes through the local Context Forge for every call today.
- **300 depends on 260.** Timers need a process that stays up, and events from other machines need the hub's door. It grows out of 240's inbox and wake wrapper.
- **320 depends on 300.** The stand-in is an agent defined and run by 300. It widens 140's question record, keeps 220's standing answers as the PM's instructions, keeps 220's pause entry, and deletes 140's answering pipeline.
- **340 depends on 300.** It does not depend on 320, and the two can be built in either order. 320 goes first because it is the PM's larger cost.
- **360 depends on 320 and 340.** Two working agents decide what is general.

## External Dependencies

- **Claude Code**, read 20261120: without a window it takes a turn cap and a cost cap; a hook at the end of a turn can block the stop and give the agent text to continue with; a hook can defer a tool call so the run ends saved and resumes later. None of the runtimes checked has a wall-clock limit. Architecture re-checks each of these before depending on it.
- **Squadron.** A pipeline step on a Claude model runs through the Agent SDK and loads the repo's settings, not the PM's user settings, unless `pipeline.user_settings` is on. So a turn-end hook reaches pipeline runs only through the repo's settings or that key. A run on any other provider has no hooks; for those, the entry points are the pause and the finished run.
- **`ecorkran/squadron#302`** (a command started when a run pauses) and **`#303`** (working directory in the run file, JSON from `sq runs list`): closed, checked 20261120. **`#304`** (a pipeline step that runs a command): open, and nothing here needs it.
- **Codex**, read 20261120: runs without a window and resumes a session. No turn, time or cost cap was found, so the runner enforces all three.

## Sequencing

`260 → 300 → 320 → 340 → 360`.

Within each initiative: architecture and its review, then the slice plan, then slices. 260's architecture starts from this plan's scope, not from the earlier 260 entry.

## Notes

- The older architecture documents (`100-arch` to `240-arch`) describe what was built. Where they differ from the concept, the concept governs.
- **Hooks and non-Claude runs get a closer look in 320's architecture** (PM, 20261120). The current answer is good enough to start: Claude Code's turn-end hook where it exists, the pause and the finished run everywhere else. 320's architecture checks what each runtime the PM uses offers at the end of a turn, Codex and Squadron's other providers included, and whether a run on those can be caught as early as a Claude one.
- A needless question or a leftover that still reaches the PM is a defect in Amoeba and is fixed there.
- A design that handles one named case and sends the rest to the PM is rejected in review.
- Check off initiatives as their architecture documents and slice plans are complete.
