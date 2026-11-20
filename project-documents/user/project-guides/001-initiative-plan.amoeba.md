---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261119
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`, rewritten 20261106 from `notes/005-usage-scenarios.amoeba.md`. The earlier version of this plan is in git history.

## Index Convention

**20-based** (100, 120, 140, ...), the guide default. Indices are tentative and may be reassigned. Retired indices stay listed so that existing documents keep their meaning.

## Decomposition rationale

Initiatives 100 to 140 were built from the bottom up, and 160 to 200 were planned the same way. The new concept starts from three scenarios and one job description, and that job is a single coherent system: a tool that knows the program, handles first-level questions and keeps the record. So all remaining work goes in **one initiative**, with one architecture document and one slice plan.

Splitting it again (say, questions in one initiative and programs in another) would give two architecture documents that have to agree on the same operations, the same store and the same answer to "does anything stay running?". Split later only if the work itself shows a reason to.

240 is that later split. Messaging between agents is a new layer on top of 220's operations and store, with its own scenario (D), and it does not change what 220 built.

260 is its own initiative for the same reason. It adds a kept-running hub and a network door, which 240's architecture rules out, and it has its own scenario (E).

280 is separate from 260 because it needs no hub and no network. It changes what 220 said an answer can do (resume only), so it gets its own architecture document, and it has its own scenario (F).

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — Built: the SQLite store, resident process, inbox of submission files, network API and related contracts. The concept keeps the store, reduced to what the scenarios need; the rest has to be justified by a scenario. 220's audit decides what stays. Dependencies: None. Status: complete
2. [x] **(120) Runner** — Built: launches and watches Squadron runs, resumes runs that stopped for a transient reason, hands paused runs to 140 and keeps the blocked list. The concept says Amoeba starts no work, so launching at least is in question. 220's audit decides what stays. Dependencies: [100]. Status: complete
3. [x] **(140) Question Answerer** — Built: the question record, source passages and the two-step answering pipeline, plus a gate around the answer. The record and the pipeline are the core of the new concept. Checks on an answer belong in the pipeline as Squadron steps, so the gate is in question. 220's audit decides what stays. Dependencies: [100, 120]. Status: complete
4. [ ] **(160) Translator & Notification** — Retired 20261106. The Translator is now the PM's separate chat agent app. The Discord bridge is dropped, because Amoeba notifies agents and agents already reach the PM. Status: deprecated
5. [ ] **(180) Program Coordination** — Retired 20261106. Slices 180 (slice-writing pipeline) and 181 (program record) are merged. Slice 182 (program concept as a source) is parked on its branch, unmerged, and slices 183 to 186 are paused. Edges with hold and release, requests between members, and ordering are not in any scenario, and some of them walk the dependency graph, which the concept rules out. What programs still need moves to 220. Requests and hold-and-release come back in 240, rebuilt without a resident process. Status: deprecated
6. [ ] **(200) Multi-Agent Chat** — Retired 20261106. Not Amoeba: the PM's chat and agent-to-agent talk live elsewhere. Brought back 20261114 as part of 240: agent-to-agent messages are Amoeba's, and a message to a program reaches every member. Status: deprecated
7. [x] **(220) Program Tool** — Everything the concept asks for, built by cutting down what exists before adding to it. Scope:
   - **Scenarios A, B and C** from the concept: a question while the PM is away, a change in one member reaching another, and the PM asking where things stand. Scenario A, end to end on a real run the PM started, is the first proof.
   - **One set of operations**, over MCP for agent sessions and a CLI for pipelines and scripts. No MCP server exists today.
   - **Answering on runs Amoeba did not launch**, resuming only the run that asked.
   - **The program model** at the size scenario B needs: members, what each depends on, and what each has released.
   - **The record** of who asked what, which model answered, from what, and what the PM overrode.
   - **An audit of today's code** against the scenarios, sorting about 34k lines in `src` and 69k in `tests` into keep, move to Squadron, or delete, and doing the deleting. Slices 182 to 186 are re-judged here.
   - **The architecture document answers the concept's six open questions**, starting with who notices a paused run, since that decides whether a resident process exists at all.

   - **Scenario A switched on 2026-11-12** (hook live at user level, `trading` program registered, sanity pass clean). The counted trial and verdict were dropped as needing PM-driven work; evidence comes from normal use of `amoeba decisions` and `amoeba status`.

   Out of scope: launching member pipelines, notification mechanics, chat, and any check on an answer that could be a Squadron step. Dependencies: [100, 120, 140]. Status: not_started
8. [x] **(240) Agent Messaging** — Messages between agents in different repos, for any agent and any UI, not only Claude Code sessions. Scenario D: one repo needs another to build something (squadron needs context-forge, which needs ai-project-guide). Architecture: `240-arch.agent-messaging.md`. Scope:
   - **Durable messages** in the Amoeba store, addressed to a member repo or a program. Requests have states with an exit for each (open, accepted, done, declined, cancelled, expired), and notes are information only.
   - **Chains** as parent links between requests, shown but never walked, with a depth limit.
   - **Delivery by polling** at moments named in each repo's rules file, the floor for every agent. **Push** from `amoeba-mcp` on top: Claude Code channel events, plus a standard MCP resource update for clients that act on it. Also session presence.
   - **Hold and release:** a run paused on a request resumes when the request is done.
   - **Waking:** a configured per-member command started when mail lands and nobody is working in that repo. This is the last slice.
   - **Release reports** also drop a note in each consumer's inbox.

   Out of scope: ordering across a chain, and Amoeba deciding what work to do. Slice plan: `240-slices.agent-messaging.md` (240 requests, 241 push and presence, 242 hold and release, 243 notes, 244 waking). Dependencies: [220]. Status: complete
9. [ ] **(260) Cross-Machine Hub** — 240's messaging between repos on different machines, LAN first. Scenario E: trading-ui is worked on one machine and trading-data on another, in one program, and each needs to send the other requests, notes and release reports. Scope:
   - **A hub:** one machine holds the store and runs `amoeba serve`, an HTTP door over the existing operations beside the CLI and MCP doors. This is a process kept running, on the hub machine only and only when remote use is wanted.
   - **Client mode:** `amoeba` and `amoeba-mcp` on another machine point at the hub instead of a local store. A remote client only ever talks HTTP to the hub and never opens the store, so the hub can later move into its own service without clients changing.
   - **Member identity without the hub's Context Forge:** project ids are minted per machine. The client resolves its own member with its local `cf`; the hub resolves a recipient by name from the store, which gains a member name. `add` for a remote repo is checked by the client's `cf`.
   - **One repo, one machine, one member.** Two checkouts of a repo on two machines are two members.
   - **A directory:** session rows record the host, so `list` shows who is working where across machines. Agents announce by heartbeat; the hub never pings agents.
   - **Finding the hub:** the hub advertises itself on the LAN and a new machine's `amoeba` finds it without configuration.
   - **Waking across machines:** mail for a repo on another machine starts that repo's wake command on its own machine.
   - **Access:** a shared token from the first slice, since anyone who can post to the hub can put text in front of agents and start wake commands.

   Out of scope: one member spanning machines, a request sent to more than one member, a claim queue ("whoever can do X"), the hub as a separately deployed service, and answering a paused run from another machine (answering reads the repo on disk, so each machine handles its own pauses against the shared store). Dependencies: [240]. Status: not_started
10. [ ] **(280) Standing Answers** — A ruling the PM gives once, applied to every later pause it covers. Scenario F: a p6 run pauses at its merge step on unchecked task boxes, and the PM's ruling is always the same (verify, finish what is small, tick, commit, merge). Scope:
   - **The standing answer record,** in the store: the PM's words, the situation it covers, and its reach (every repo, one program, one member). Given through an agent, listed, and withdrawn; a withdrawn one stops applying at once.
   - **Matching a pause to a standing answer.** Squadron already labels this pause in the run file (`unfinished_tasks` on the merge step), so a labelled pause matches on the label. A plain question matches through the answering pipeline, with standing answers supplied as passages.
   - **Pauses that need work.** Amoeba starts an agent in the paused run's repo, on its branch, with the standing answer as the instruction, then resumes the run. One attempt per pause; a pause that survives it waits for the PM with what the agent did on the record.
   - **The PM's authorization.** A standing answer is not stopped by the list of things an automatic answer may not authorize.
   - **Curation.** Promote one of the PM's stored answers to a standing answer, or retract it.
   - **Reach beyond a member** for ordinary questions: a standing answer counts in every repo it reaches, where a stored answer counts only in its own.

   Out of scope: Amoeba choosing work nobody ruled on, and a standing answer written by anyone but the PM. Needs no network: it works on one machine, and 260's shared store carries it to the others. Dependencies: [220, 240]. Status: not_started

## Cross-Initiative Dependencies

- **120 depends on 100, and 140 depends on 100 and 120.** These hold for the code as built. 220's audit may remove the dependencies along with the code.
- **220 depends on 100, 120 and 140.** It inherits their code and is what cuts it down, so it can change or delete any of it. It also inherits slices 180 and 181 from retired 180.
- **240 depends on 220.** It builds on 220's store, operations, MCP server, resume procedure and question record. It revises 220's "pull, never push" principle and decisions 5 and 6, as listed in `240-arch`.
- **280 depends on 220 and 240.** It builds on 220's question record, answering pipeline and resume procedure, and on 240's way of starting an agent in a repo. It revises 220's rule that an answer can only resume the run that asked.
- **260 depends on 240.** It carries 240's messages, presence and waking across machines and changes none of their rules. It revises 240's "no new process kept running" for the hub machine, and 240's member lookup, which goes through the local `cf` for every call.

## External Dependencies

- **`ecorkran/squadron#299`:** closed. Answering steps' `allowed_tools: []` runs tool-less on Claude models.
- **The PM's chat agent app:** not a dependency. Getting waiting questions to the PM belongs to chat and agent communication. From 240, Amoeba's MCP server pushes new mail to its own session, and pushes nothing else.
- **Two more Squadron changes,** listed in `220-arch.program-tool`: a command started when a run pauses (`#302`), and the working directory in the run file with JSON from `sq runs list` (`#303`). A pipeline command step (`#304`) is on hold. All are general, off unless configured, and never make Squadron depend on Amoeba.
- **Claude Code channels** (240's push): a research preview, observed 20261114. A custom server needs a launch flag, and the server has to negotiate a pre-2026-07-28 MCP revision. Polling still delivers without it.

## Sequencing

Work 220 in this order:

1. **Architecture:** one new document, `220-arch`, answering the six open questions.
2. **Audit:** sort the code against the scenarios and the architecture.
3. **Slice plan:** rebuilt from the audit result.
4. **Scenario A,** then whatever it shows is next. The slice plan sets the order of B and C.

Nothing new gets built before the audit, and slices 183 to 186 stay paused until the slice plan re-judges them.

Work 240 in this order: architecture and its review with the PM, scenario D added to the concept, then the slice plan.

Work 260 in this order: scenario E added to the concept, architecture and its review, then the slice plan.

Work 280 in this order: architecture and its review, then the slice plan. Scenario F is in the concept. 280 does not wait for 260.

## Notes

- Until 220's architecture exists, the older architecture documents (`100-arch`, `120-arch`, `140-arch`, `180-arch`) describe what was built. Where they differ from the concept, the concept governs.
- A new need starts as a new scenario in the concept, not as a new initiative here.
- Check off initiatives as their architecture documents and slice plans are complete.
