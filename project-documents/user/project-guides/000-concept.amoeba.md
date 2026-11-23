---
docType: concept
layer: project
phase: 0
phaseName: concept
project: amoeba
audience: [human, ai]
description: Concept for Amoeba, rewritten 20261120. An agent that stands in for the PM. Everything another agent would hand to the PM goes to it first. It answers needless questions, catches leftover work, answers real questions from the repo and the PM's earlier decisions, and learns from every case. Built as a long-running agent.
dependsOn: [000-pre-concept.amoeba.md, notes/006-long-running-agents.amoeba.md]
dateCreated: 20260618
dateUpdated: 20261122
status: in_progress
---

# Amoeba

**THE DEFINING PURPOSE OF AMOEBA IS TAKING QUESTIONS OFF THE PM'S PLATE. EVERY INITIATIVE, SLICE AND DESIGN IS JUDGED BY ONE MEASURE: HOW MANY QUESTIONS STILL REACH THE PM. ZERO IS THE GOAL. ONE EVERY TWO DAYS IS ACCEPTABLE. FIVE IN A SESSION IS FAILURE. WORK THAT DOES NOT REDUCE THAT NUMBER IS NOT AMOEBA'S PURPOSE, HOWEVER WELL IT IS BUILT.**

## Overview

Amoeba is the room the PM and his agents share, and the persistent agent that lives in it. Everything another agent would hand to the PM goes there first: questions, leftover work, paused runs. The agent settles what the PM's record and the repo already settle, in its own voice, and makes the rest cheap for him to answer. It learns from every case and every time the PM overrules it.

The User-Provided Concept below is the original idea, kept as written. Amoeba has moved a long way from it. The Refined Concept is the current one.

## User-Provided Concept

> **Note on status:** This is a *pre-concept* — input for the P0/concept stage, not the finished concept. It front-loads the architectural decisions that should be locked before the runner starts, and deliberately leaves open the decisions the concept stage exists to make.
>
> **Note on the name:** Amoeba. In Amoeba's world, amoebas are immense, apex entities — formless, adaptive, and powerful. The name encodes the architecture: a single adaptive process that flows around each project's shape and extends ephemeral *pseudopods* (on-demand Judge nodes) to grab what it needs, then reabsorbs them. Subsystem vocabulary follows the metaphor (e.g. "the Amoeba extends a pseudopod to evaluate finding F002").
>
> **Repo description:** *Deterministic control flow, bounded nondeterminism, named after an apex amoeba.*
>
> **Note on "deterministic":** The control flow is deterministic; the system as a whole is not, because the Judge (and Squadron's reviewers) are LLMs. The precise and stronger claim is **bounded nondeterminism** — nondeterminism is confined to named, bounded subroutines whose blast radius is fixed by the deterministic structure around them, not by the subroutine itself. The Runner is a deterministic machine that calls nondeterministic oracles and applies fixed rules (thresholds, routing) to their answers; the structure determines how far any single bad answer can propagate. Avoid the bare phrase "deterministic orchestration" anywhere load-bearing — it overclaims in the one way a careful reader will catch.

#### High-Level Project Concept

Amoeba is an orchestration runner with **deterministic control flow and bounded nondeterminism** that drives a project through its full Context Forge / Squadron lifecycle — P0 concept through P6 code — with human involvement reduced to the points where judgment is the actual work. It is the "next level of automation" above Squadron: where Context Forge removed nondeterminism from scaffolding and Squadron placed nondeterminism deliberately inside pipeline steps, Amoeba removes the human from the *orchestration* of those pipelines wherever the orchestration is deterministic, and escalates to a human (or first to an ephemeral Judge) only where it isn't. The control flow is deterministic; the judgment subroutines (Judge, reviewers) are not — but the deterministic structure bounds how far any one of their outputs can propagate.

The governing principle is the same one the whole toolchain is built on: **every intelligence added to a system — human or AI — reduces its determinism, so you place intelligence only where judgment pays for the variance it introduces, and remove it everywhere else.** Amoeba applies this to its own design by splitting into parts with deliberately opposite natures:

* **The Runner** — a deterministic state machine. It executes a known command sequence (`cf set slice 104`, `cf build`, `sq run p4 104 -v`), reads structured findings, applies a routing policy, and either advances or writes a blocked-state. It has zero discretion. It is not an agent. It is Context Forge's shape pointed at the orchestration layer. The Runner is the central body; everything nondeterministic is a bounded subroutine it invokes and a deterministic rule it applies to the result.
* **The Translator** — a conversational AI at the human edge. It converts natural-language intent ("add Kalshi as a source in trading-data, follow the existing pattern") into the deterministic command sequence the Runner executes, and converts the Runner's structured findings back into natural language for the human. It does *not* run the project. It interprets intent and reports state.
* **The Judge** — an ephemeral, on-demand node (a *pseudopod*) the Runner spawns when it hits a finding that is *not* deterministically resolvable. The Judge runs a scored evaluation and returns `(resolution, confidence)`. The Runner then applies a deterministic threshold: confidence above threshold → apply resolution and continue (human never pinged); below → write blocked-state and escalate. The Judge is a nondeterministic intelligence, but **the Runner's use of it is deterministic** — the Runner does not judge, it calls a judger and applies a fixed rule to the number. The discretion lives entirely inside the ephemeral node; the orchestration around it stays a state machine. The pseudopod is spawned, used, and reabsorbed.

The parts never call each other directly. **They communicate through Context Forge / Squadron state.** The Translator writes intent into state; the Runner reads state and executes; the Runner writes findings and checkpoint-blocks into state; the Translator reads state to report and to surface escalations; the Judge reads the finding and its locked constraints from state and writes its resolution back. State is the interface — the same principle CF already runs on, extended one level up. This decoupling is what makes the whole thing async by construction: the Runner grinds while the human chats with the Translator whenever convenient, and nothing blocks waiting on anything.

Amoeba exists because building software with AI tools works until the project becomes at all complicated, then falls apart — and the part that still requires a human (running the pipeline, resolving each checkpoint, advancing each phase) is mostly deterministic and mostly not worth a human's time. Amoeba automates the deterministic orchestration layer, lets a Judge absorb the evaluable-but-not-mechanical findings, and preserves the human exactly where direction is set.

* This is a **standalone runner + thin conversational front-end + on-demand Judge**, built on top of existing Context Forge and Squadron installations. It does not replace either; it drives them.
* The Runner is deterministic Python (or equivalent), authored by hand — it is the interesting artifact and the embodiment of the project's own thesis.
* The Translator is an AI conversational layer (Claude Code VS Code extension, a chat interface, or both — the surface is interchangeable because it only reads/writes state).
* The Judge is a Squadron-invoked evaluation (Squadron already supports SDK sessions, tool calls, and multi-provider models — the Judge is a pipeline that scores a finding and returns a structured verdict).
* First proof: drive `trading-data` to add Kalshi as a data source, near-autonomously, with one front-loaded human checkpoint at concept.
* The single load-bearing design decision: **a checkpoint is a persisted blocked-state, not a blocking call.** The Runner writes "slice 104 P2 blocked-on-human, finding F002, awaiting resolution," stops touching that branch, and moves on to other runnable work or idles. When the resolution lands in state, the branch becomes runnable again. This is what makes async real, makes restart-survival free, and makes the eventual multi-project version a quantity change rather than a rewrite.

##### Target Users

Initially: Erik, driving his own projects (trading-data first, then the backlog of specialized utilities). The human role is **direction-setter and escalation-resolver**, not operator. The human locks concept, glances at the borderline P1 plan, and thereafter answers only the escalations the routing policy (and the Judge) raise.

This broadens as the routing policy and the Judge's calibration mature. Early on, more findings escalate (the policy is conservative and the Judge's threshold is set to always-escalate); as deterministic gates absorb the mechanically-checkable findings and the Judge earns trust, the escalation rate drops and the same person supervises more concurrent work. The eventual multi-project mode (running several lifecycle-trees at once) has the same single supervisor watching a forest of runnable / blocked / done nodes rather than a single linear run.

##### Proposed Technical Stack

* **Runner:** Hand-written deterministic state machine. Python is the natural choice (matches Squadron, matches the CLI surface). Core logic: `while runnable work exists: run command -> parse structured findings -> apply routing table -> advance, spawn Judge, or write blocked-state`.
* **Control surface into the toolchain:** the existing CF/SQ CLIs (`cf ...`, `sq run ...`), which are already deterministic. The Runner shells out and parses; it does not reimplement CF/SQ logic.
* **State:** the existing Context Forge / Squadron state plus a small amount of Amoeba-owned run-state (per-node status: runnable / blocked-on-human / blocked-on-judge / done; open findings; pending resolutions). Reuse CF/SQ state mechanisms where they fit rather than inventing a parallel store. *(See open question on the resident substrate / message queue.)*
* **Findings contract:** Squadron already emits structured findings (YAML front-matter, `severity` in {pass, concern, fail, note}, `category`, `summary`, `location`). The Runner parses these directly. *(See open question on the checkability tier — this likely needs an added field.)*
* **Translator:** an AI conversational layer with access to read/write CF/SQ state and to invoke CF/SQ commands. Could be the Claude Code VS Code extension, a chat surface, or an SDK-connected model. Interchangeable by design.
* **Judge:** a Squadron evaluation pipeline, spawned on demand, returning `(resolution, confidence)`. Confidence is *not* the model's self-reported number (poorly calibrated); the real metric is **agreement across N judge runs or across models** — which Squadron's multi-provider substrate is built for. Consensus = confidence; divergence = escalate.
* **Notification channel:** outbound Discord webhook on escalation (cheap, async, already acceptable). Inbound: a way to read the human's reply back into the blocked node's resolution. Deliberately *not* an autonomous-agent runtime (e.g. ZeroClaw) as the orchestration substrate — adopting an autonomous-agent framework as dumb plumbing contradicts the project's own thesis, and the notification half is a day of code.

##### Proposed Development Methodology

In general, favor simplicity and avoid over-engineering. Remember the cliche about premature optimization. Use industry standard solutions where practical and available. Avoid reinventing wheels.

* **DFS, not BFS, through the lifecycle tree.** Implement the first slice fully before planning the next, because early implementation reveals information that changes later design. BFS commits to downstream plans before upstream code has taught you why they're wrong.
* **Cherry-pick the easiest slice category first.** Validate the Runner, the routing table, and the Judge on low-risk work before pointing them at hard slices. The easiest category is where the routing table is most likely already correct.
* **Build by inducing failure** (the house method). Point the Runner at real work, watch where it stops that it shouldn't have, and refine the routing table or the Judge threshold at exactly that point. Each wrong escalation is the next deterministic gate or routing rule. Each missed escalation that should have fired is a finding-severity or Judge-calibration correction. Each confident Judge resolution that disagrees with what the human would have decided is calibration data that lowers (or holds) the threshold for that finding category.
* **Front-load judgment to manufacture downstream checkability AND judgeability.** Early human checkpoints (concept, borderline P1) are dense; they resolve the genuine unknowns into constraints. Done well, the front-loading is *why* later phases reach high autonomy: downstream tasks inherit constraints to verify against (checkability, for deterministic gates) and locked references to score against (judgeability, for the Judge), rather than decisions to make. Early human judgment earns the right to later autonomy.

**Checkpoint and review-gate policy (initial):**

| Phase | Gate | Human role |
|---|---|---|
| P0 concept | no formal review; **mandatory human checkpoint** | direction-setter; iterate until good before Runner starts |
| P1 initiative plan | no formal review; **usual human glance** | borderline; usually a yes/iterate |
| P2 architecture | review gate | Judge first; escalate on low consensus |
| P4 slice plan | review gate | Judge first; escalate on low consensus |
| P5 tasks | review gate | Judge first; escalate on low consensus |
| P6 code | review gate | Judge first; escalate on low consensus |

**Routing policy keyed on checkability tier, not category:**

* **Tier 1 — mechanically checkable predicate** (path exists, grep match, schema diff, typecheck; e.g. "slice number 193 vs 169", "no load-test task in `tests/load/`"). Run as deterministic gates *before* the AI reviewer where possible. Routing: auto-fail / auto-fix-and-recheck, never escalate, never Judge. Any Tier-1 finding the AI emits is deterministically verifiable, so the AI's mechanical claims are free to audit — and a deterministic check that *disagrees* with an AI Tier-1 claim is itself a high-value signal (the reviewer confabulated).
* **Tier 2 — semantic-coverage judgment** (e.g. "prompt-only capability probe omitted", "relative gate insufficient to confirm the NFR"). Judgment is the work. Routing: **Judge first** — score against the finding's own predicate and the project's locked constraints (reference-free / rubric-based, no golden output needed because the locked architecture *is* the reference). High consensus → resolve and continue. Low consensus → escalate to human. Current threshold = always-escalate (Judge runs and logs, human still decides) until the Judge earns trust.
* **Tier 3 — borderline / mixed** (a checkable core wrapped in a judgment, e.g. "timeout path untested"). Decompose: carve off the deterministic predicate to Tier 1, leave the residual judgment at Tier 2. Often a single finding is doing two jobs — detecting a mechanical gap and judging its significance — and only the second needs the Judge.

##### Summary

Amoeba runs Context Forge and Squadron through a full project lifecycle with **deterministic control flow and bounded nondeterminism**. A deterministic Runner (a state machine, not an agent) is the central body; a conversational Translator handles judgment at the human edge; an ephemeral Judge (a pseudopod) absorbs the evaluable-but-not-mechanical findings and returns a scored verdict the Runner trusts via a deterministic threshold. The parts communicate only through toolchain state. Humans are involved at the front-loaded concept checkpoint and at Tier-2 findings the Judge can't resolve with consensus. It is the toolchain's own thesis applied one level up: deterministic control flow around bounded nondeterministic subroutines, spending an intelligence only where judgment is the actual work.

##### Output Location

On adoption into a CF project, save the finished concept as `001-concept.amoeba.md` in the `user/project-guides/` directory.

---

## Refined Concept

> Rewritten 20261120 at the PM's direction. It replaces the 20261106 Refined Concept and its scenarios A to F, which are in git history. Where the User-Provided Concept above differs, this section governs.

### Problem

The PM runs many agents: interactive sessions and unattended pipeline runs, across several repos. They waste his time in three ways.

1. **Needless questions.** Agents ask things that are already decided, or that they could settle by looking at the repo.
2. **Leftovers.** Agents stop with work undone: an unticked plan, a "remaining" list, a step skipped and handed over as an open item.
3. **Real questions that have an answer.** Some questions need thought, and the answer can still be worked out from the code, the plans, the history and how the PM has decided before. They wait for the PM anyway.

Written rules do not fix this. Agents read a rule and then act from habit. On 20261120 a session had "do this after every merge, never ask" in front of it and listed the item for the PM anyway. Whatever fixes this has to sit outside the agent and act on what the agent actually produces.

Earlier versions of Amoeba failed by narrowing:

- **It acted in one situation only:** a Squadron pipeline run paused on a question. Interactive sessions and runs that finished with leftovers never reached it.
- **Its answerer was built to refuse.** It had no tools, saw only text pasted into its prompt, and could answer only when that text already settled the question. Everything else waited for the PM.
- **Each new case needed the PM to write a ruling first.** The PM still did the thinking, one case at a time.

What that produced was a record-keeper and a few hooks.

### What Amoeba is

Amoeba is a room and the agent that lives in it (The room, below). The agent judges and interprets. Standing in for the PM is one of its functions, not the whole of it.

Everything an agent would hand to the PM goes to Amoeba first: a question, a "remaining" list, a pause, a run that finished with work left over. Amoeba looks at the repo with full tools, works out what the repo and the PM's record settle, and either does the work, tells the agent what to do, or puts the question to the PM in one line. It does three jobs and learns from each.

1. **It answers needless questions,** so the agent keeps working and the PM never sees them.
2. **It catches leftovers.** An agent's work is not finished until Amoeba has checked what it left. Amoeba finishes small leftovers itself or sends the agent back to finish them.
3. **It answers real questions** from whatever settles them: the code, the plans, the git history, the repo's rules, other repos in the program, and the PM's earlier decisions.

### The room

> Added 20261122 at the PM's direction, after two days of the turn-end hook in use.

Standing in for the PM is a role. The room is a place, and the place is what the PM needs: something coherent, where today everything is fragmented across sessions.

- **One shared thread.** The PM, the session agents in every repo, and Amoeba's persistent agent are in it. A hand-off from any session goes there, not to a private judgment inside that session.
- **The agent speaks as itself.** It never writes an instruction or a decision in the PM's name. When the record settles something (a decision he made, a standing answer, the plan, the repo's rules), it says so and cites it. The turn-end hook wrote its orders as the PM. On 20261122, after its fix, it gave three in a day and two were wrong.
- **It still decides by default** (Judgment, below), by looking, with tools. Two things it does not do, both learned from the hook: start work the PM did not ask for, and guess a fact only he has. Those go to him.
- **Asking the PM is cheap there.** A question used to cost the PM a switch into one session and a read of its detail, which is why earlier versions had to guess. In the room the agent has done the reading, and the question is one line with its recommendation. He answers without opening that session, and the answer goes back to the agent that asked.
- **The PM sees outcomes.** Agents talk to each other in the room while he is away. He is shown what needs him and what was decided. The talk between agents is there to open, and folded by default.
- **What the persistent agent does there.** It settles what the record settles (the stand-in's job), carries messages between agents and repos, tells sessions the standing facts they would otherwise rediscover, reads detail so the PM does not have to, and notices what crosses projects. Later it directs work the PM asked for in the room. Directing work is one function of it. The room is not a hierarchy of a boss and workers.
- **The PM's seat is a session like any other,** in his editor, opened on the room. The chat is a component he places beside whatever else he is doing. Amoeba builds no dashboard.
- **Smaller rooms are later work.** The PM will want to talk to some agents and not all, most often every agent in one program. The first version is one room in which a message can be addressed to a member or to a program.
- **What agents share.** Two repos' agents share information through the room without noise, clutter or bloat. The bar for sending: something the other repo relies on has changed. Anything else is not sent. What a receiving agent keeps, if anything, has no rule yet, and it needs one: the aim is a thing that learns and gets better, and nothing in Amoeba says today what learning is.
- **The test:** the PM stops having to visit a session to unblock it.

### Judgment

- **The default is to decide.** Amoeba does not need an earlier ruling that covers the case. It works out the answer the way the PM would: by looking.
- **It matches by meaning.** It never requires a question to match a stored situation exactly. Anything a script or a query could do is not what Amoeba is for.
- **The record is exact.** Every decision is stored with the question, what Amoeba looked at, what it decided and why. Judgment is free; the record of it is not.
- **Its work can be undone.** What Amoeba does in a repo lands as commits, and each decision names them.
- **Little reaches the PM.** Four kinds of thing do:
  - an action that cannot be undone and reaches outside the repo, such as publishing a release or destroying data;
  - spending past the budget set in config;
  - product direction: what to build and why;
  - a question Amoeba worked and could not settle. It arrives with what Amoeba found and the answer it recommends.
- **An item waiting for the PM always ends:** by his answer, by a dismiss, or by expiry after an age set in config. An expired item is closed and recorded, and the agent that asked is told to drop that line of work.

### Learning

Amoeba gets better from use. This is the part earlier versions lacked.

- **Every answer is a case.** Before deciding, Amoeba reads the past cases that bear on the question and what the PM said about them.
- **An overrule is a correction.** When the PM overrules a decision or says "don't ask me that" or "you should have told me", Amoeba stores it against the case. The newest word from the PM wins.
- **Every leftover is a case too.** Amoeba records what was left, by which kind of work, and what finishing it took. Its check at the end of later work looks for the same thing.
- **A curation pass keeps memory true.** On a schedule, Amoeba reviews recent cases, merges repeats into one general note, replaces entries that are stale or contradicted, and extends a decision made in one repo to the others it fits.
- **The PM can still rule ahead of time.** A standing answer (slice 230) is his explicit instruction. Amoeba treats it as the strongest memory it has. It is one input to judgment, and no longer the only way Amoeba learns.

### Getting in the path

Amoeba only works if agents cannot go around it.

- **Interactive sessions.** A hook at the end of each agent turn sends the agent's closing message to Amoeba. If it hands something to the PM that Amoeba can settle, the turn does not end: the agent gets the answer and keeps working.
- **Pipeline runs that pause.** As today, a paused run goes to Amoeba. Amoeba now decides with tools and judgment.
- **Pipeline runs that finish.** Amoeba checks a finished run for leftovers before the result reaches the PM.
- **Direct asks.** Any agent can ask Amoeba a question over MCP or the CLI.
- **A failure is loud.** If Amoeba cannot be reached, the hook reports an error. It never passes the question to the PM as if Amoeba had seen it.

### A long-running agent

Amoeba is built as a long-running agent: it wakes when there is work, does a bounded piece, remembers what it learned and sleeps. The model is Anthropic's article "Building always-on agents", read 20261120, and `notes/006-long-running-agents.amoeba.md`. These parts come from `agent-kit`, the PM's own project for long-running agents, created 20261122 (`notes/007-agent-kit-concept.amoeba.md`). Amoeba builds none of them, and its agent is built on the kit once the kit's substrate runs. This replaces the 20261121 decision that Amoeba would build them itself. This table covers every part the article names.

| Article part | In Amoeba | Status |
|---|---|---|
| Event inbox | The store's inbox, with dedup ids, read cursors and one worker per inbox. Hand-offs from sessions and runs arrive as events. | Built for messages between repos. Hand-offs are new. |
| Timers: follow-ups | Amoeba sets its own deadline, such as checking that an agent it sent back did finish. | From agent-kit |
| Timers: schedules | Recurring work, such as the curation pass. Timers live in the store; a scheduler pass turns a due timer into an inbox event. | From agent-kit |
| Memory: user instructions | The PM's standing answers | Built (slice 230) |
| Memory: user notes | What Amoeba has learned about how the PM decides. An index loads on every wake; entries are read when needed. | From agent-kit |
| Memory: past messages | What the PM has already been told, so nothing is told twice | Partly built (the decisions list and its read marker) |
| Memory: task progress | Progress on each item Amoeba is still handling, so the next wake picks it up | From agent-kit |
| Dreaming (memory curation) | The curation pass under Learning | From agent-kit |
| Permissions: deferred tool calls | An item that needs the PM ends the run and is saved. His answer comes back as an inbox event and the work resumes. | Built for paused runs (hold and release). Extended to sessions. |
| Permissions: auto mode | The safeguards of the runtime Amoeba's agent runs in. The architecture checks what each runtime offers. | Used, not built |
| Permissions: credential proxy | None | Not built; reason below |
| Outbox | The decisions list and the items that need the PM. It starts quiet. | Partly built |
| Outbox: evals for how much to send | None | Not built; reason below |

**Not built, and why:**

- **Credential proxy.** The article puts credentials in a proxy outside the agent so an agent running somewhere the user does not control never holds them. Amoeba's agents run as the PM, on the PM's machines, with the same access as every session he already runs, and a wake command gets a cleaned environment and loads its own secrets. A proxy would guard against a case that does not exist here. It becomes necessary the day an agent runs on a machine that is not the PM's.
- **A safety classifier of Amoeba's own.** The runtime already has one, and a second would be a worse copy.
- **Evals for message volume.** The article tunes how much an agent says with an eval suite. Amoeba has one user, and his reaction is the measure: "don't tell me this" and "you should have told me" are corrections it learns from.

**From the 006 note, beyond the article:**

- **Bounded runs.** Every wake has a time cap and a cost cap, and one wake runs per inbox. When a cap is hit, the run ends and is recorded with what it found. The item is retried once on the next wake, then goes to the PM's list with the findings.
- **Observability.** A row and a log per run, and a status view.
- **One definition, one runner.** An agent is one definition file plus a generic runner, so a second long-running agent is a copied file, not a hand-written script.
- **Runtime and model come from config.** There is no default in code.

### What Amoeba also does

These are built and stay. They are the stand-in's wiring and reach.

- **Knows the program:** the member repos, what each depends on and what each has released. A program is a set of repos where members depend on each other, usually on a release.
- **Carries messages between repos:** requests and notes between agents in different repos, with waking when nobody is working in the recipient.
- **Keeps the record:** who asked what, what Amoeba looked at, what it decided, and what the PM overrode.

### What Amoeba is not

- **A pipeline engine.** Squadron runs planned work inside a repo: phases, reviews, merges.
- **A rules engine.** It does not look up a matching rule and apply it. A design that could be replaced by a script or a query is the wrong design.
- **An extension to Squadron.** Squadron is one source of hand-offs among several. A gap in what Amoeba handles is fixed in Amoeba.
- **A chat product or a dashboard.** The PM's seat in the room is an ordinary session. He still talks to whatever agent he likes, and that agent's hand-offs go through Amoeba.

### Users and how they reach it

- **Agents** reach Amoeba through the hooks above and through one set of operations, over MCP for sessions and a CLI for pipelines and scripts.
- **The PM** sits in the room through a session like any other, and types no `amoeba` command in normal use. He sees what needs him and a short list of what was decided, and he answers there. He can also overrule by saying so to any agent.
- **Set-up** is one command per repo.

### How it runs

- **One process stays running, on a machine on the PM's LAN that does not sleep.** It holds the store, inbox, timers, memory and the PM's decisions, and runs the scheduler. This reverses the earlier "nothing stays running": timers and a turn-end answer both need it. The PM's laptop sleeps and he works on several machines, so the process does not live on any of them.
- **Every machine the PM works on is a client of it.** Sessions and runs send their hand-offs to that process, so the PM's decisions are one store everywhere (the hub, initiative 260).
- **A run happens where its files are.** Work from a clone runs on the LAN machine. Work that needs a live working tree, uncommitted changes included, runs on the machine that has it, started by the session's own hook. That machine is awake whenever a session on it is asking.
- **A wake is a run on `agent-kit`.** The kit starts the provider that the agent's definition names and enforces the time and cost caps. Amoeba builds no model layer and no runner of its own.
- **Entry points do not depend on one vendor.** For any runtime, Amoeba reads what a run produced when it ends, and a paused pipeline run reports itself. Where a runtime offers more (Claude Code's turn-end hook, its pause-and-resume for approval, its cost cap), Amoeba uses it as the faster path.
- **Every record names its owner.** Each agent, event, run and memory entry records whose it is. Today that is always the PM, through one stored login. It is the one seam kept for a later multi-person version.
- **Config and state are separate.** What a person edits lives in the config directory. The store, memory, run records and logs live in the state directory.

### What this replaces

| Earlier piece | Now |
|---|---|
| Scenarios A to F as the unit of design | Dropped. The three jobs are the purpose, and they are not a closed list of cases. |
| Answering pipeline: closed evidence, no tools, cite or decline | Replaced by the stand-in agent, which has tools and decides. |
| "An automatic answer can only resume the run that asked" | Removed. Amoeba does work in the repo. |
| "Amoeba does not start work" and "decides no work" | Removed for leftovers and for work a decision needs. Planned work is still Squadron's. |
| Standing answers as the way Amoeba learns | Kept as the PM's explicit instructions. Learning comes from every case. |
| "Nothing stays running" | Reversed. |
| "If it could be a Squadron pipeline, it should be" | Removed. |
| Store, decisions record, messaging, waking, hold and release, program record | Kept. |

The initiative plan and the 220 slice plan (slices 231 and 232) were written against the old concept and are redone from this one.

### Decisions

- **A waiting item is a saved state, not a blocking call.** Kept from the original concept.
- **Amoeba owns its own state** (cases, memory, timers, messages, program record), in SQLite.
- **Amoeba depends on upstream shapes, not version numbers.** Kept.
- **Amoeba adds judgment on purpose.** The record is what must be exact.

### Grounding that still holds

Squadron facts below were read from its source at the dates in the notes; re-check the shape before depending on one.

- Squadron pauses a run on an agent's question (`checkpoint.kind = agent_question`, read through `sq runs wait --json`), and `sq run --resume <id> --instructions "<answer>"` reruns the stopped step. See `notes/004-direction.amoeba.md`.
- Squadron's daemon is frozen and is not used by its pipeline engine, and Squadron will not build a server or message layer.
- Context Forge persists workflow pointers and does not store findings or checkpoints.

### Open for architecture

The architecture answers these itself.

1. **The turn-end hook** in each runtime the PM uses: what it can see, how it holds a turn open, and how the answer gets back to the agent.
2. **How Amoeba notices a finished run** and reads what it left.
3. **How cases are stored and found by meaning,** and what the curation pass rewrites.
4. **How the stand-in runs:** which runtime, how the time and cost caps are enforced, and how fast a turn-end answer has to be.
5. **How the kept-running process starts and restarts,** and how it becomes the hub for other machines.
6. **What the audit keeps.** Today's code is sorted against this concept into keep, change or delete.
7. **The PM's seat.** Whether the session the PM sits in is the persistent agent itself, attended, with the same memory and record as its unattended runs, and how a hand-off that arrives while he is typing is shown.
8. **How an answer given in the room reaches a session that has stopped,** in each runtime, without the PM opening that session.
9. **What a receiving agent keeps.** A rule for what received information changes on the receiving side, and a measure that shows learning. Two proposals to test, neither decided: keep only by correcting something that already exists (a document, a rule, a memory entry), never by adding to a pile; and count a correction the PM has to give twice as the sign that learning failed.

### Development approach

- **Build order** (reordered 20261122 by the PM: the hub first, then the agent on `agent-kit`).
  1. The always-up process on the LAN machine, with the store, and the laptop and other machines as its clients, so every machine reaches one Amoeba with one record of the PM's decisions.
  2. The first-level chaos: needless questions and leftovers, from sessions and from pipeline runs, with the case record, built on `agent-kit`. Its first piece, the turn-end hook, was built 20261121 and stays in use as a stopgap.
  3. Real questions answered from the repo and the PM's earlier decisions, with memory curation.
- **The agent parts come from `agent-kit`** (decided 20261122, replacing the no-kit decision of 20261121). Amoeba builds no loop, timer, scheduler, runner, cost cap or memory curation.
- **Test with fixtures and live fixture runs.** No step waits on real use. Ship it, leave it on, and rework from what use shows.
- **Each needless question or leftover that still reaches the PM is a defect in Amoeba,** and is fixed there.
- **Resist narrowing.** A design that handles one named case and sends the rest to the PM is rejected in review.
