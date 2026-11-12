---
docType: concept
layer: project
phase: 0
phaseName: concept
project: amoeba
audience: [human, ai]
description: Concept for Amoeba, rewritten 20261106. A tool that agents and pipelines call. It knows how a program's repos depend on each other, handles first-level questions by running a Squadron answering pipeline, and keeps the record of what was decided. Squadron does the work, and in normal use a human never types an Amoeba command.
dependsOn: [000-pre-concept.amoeba.md, notes/005-usage-scenarios.amoeba.md]
dateCreated: 20260618
dateUpdated: 20261106
status: in_progress
---

# Amoeba

## Overview

Amoeba is a tool that agents and pipelines call. It knows how a program's repos depend on each other, handles first-level questions by running a Squadron answering pipeline, and keeps the record of what was decided. Squadron does the work inside each repo, and humans reach Amoeba through an agent.

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

> Rewritten 20261106 from `notes/005-usage-scenarios.amoeba.md`. It replaces the earlier Refined Concept, which is in git history. Where the User-Provided Concept above differs, this section governs.

### Problem

Squadron works inside one repo and one run at a time. Two things fall outside that:

1. **Programs.** Some repos only make sense together: `trading-data`, `trading-engine` and `trading-ui` are one product, and Squadron, Context Forge and ai-project-guide are one toolchain. Each usually waits on a release of another. Today only the PM holds that picture.
2. **Questions.** A pipeline's agent stops to ask something. Most of these questions could be answered from the project's rules, the program's concept and the PM's earlier answers, but the run waits for the PM anyway.

Amoeba had not been run by anyone as of 20261106. It was built from the bottom up (store, process, contracts, features), and no one could say who would start it or when. This concept starts from the people and agents who use it, and everything else has to justify itself against that use.

### What Amoeba is

A tool that agents and pipelines call. It does three things:

- **Knows the program:** the members, what each is doing, what each depends on and what is blocked.
- **Handles first-level questions:** it routes a question to the answering pipeline with the right context, then returns the answer or passes the question up.
- **Keeps the record:** who asked what, which model answered, from what, and what the PM overrode.

### What Amoeba is not

- **A pipeline engine.** Squadron runs the work, including phases, reviews, thresholds and merges.
- **A pile of gates.** Squadron has those. A check on an answer belongs in the answering pipeline, as a Squadron step.
- **A chat system.** Agent-to-agent conversation and the PM's chat live elsewhere.
- **A graph runner.** The program graph is a dependency graph. Nobody walks it. Amoeba never launches member pipelines in order, because that would make it a workflow engine on top of a workflow engine.

### On determinism

Amoeba adds nondeterminism on purpose: it asks a model to answer in the PM's place. Wrapping that in more deterministic machinery doesn't change what it is. The part that must be exact is **the record**, and the part that must be bounded is **what the answer can do**. An answer can only resume the run that asked. It never edits code, merges or changes a threshold.

### Where it sits

| Piece | Job | Graph |
|---|---|---|
| Squadron | Runs work inside one repo | Workflow graph: do A, then B, loop on review. Executed. |
| Amoeba | Knows the program, handles first-level questions, keeps the record | Dependency graph between repos. Consulted, never executed. |
| The chat agent (separate app) | The human front door: the coordinated agent the PM talks to | None |
| Agent-to-agent talk (later) | Agents talking to each other | Not Amoeba. Closer to chat or a two-way agent dashboard. |

### Users and how they reach it

**In normal use, a human never types an `amoeba` command.** If someone has to stop and think "is that amoeba or squadron?", the design has failed.

- **Agents and pipelines** use one set of operations, exposed over MCP for agent sessions and as a CLI for pipelines and scripts. Same operations, same names.
- **The PM** reaches Amoeba through an agent: the chat agent, or a Claude or Codex session already open. "Where's trading at?" is a question to an agent, which calls Amoeba.
- **Notifications go to agents.** Agents can already reach the PM by mobile push, macOS and so on, so Amoeba builds no notification mechanics.
- **Set-up** is the one exception: register a program and its members once, ideally through an agent.

### How it runs

**Nothing stays running unless a scenario can't work without it.** By default Amoeba is a store, an MCP server started by whatever session uses it, and a CLI. A resident process is justified only by something that must happen when no run is active and nobody asked.

Amoeba works on runs it did not launch. It does not start work. The only run it resumes is the one that asked.

### What it has to do

Full walkthroughs are in `notes/005-usage-scenarios.amoeba.md`.

- **A: a question while the PM is away.** A `sq run` pauses on an agent's question. Amoeba gathers context and runs the answering pipeline. The run resumes with the answer, or an agent tells the PM. In the morning, the PM sees the finished run and a short list of what was decided on their behalf.
- **B: a change in one member affects another.** A member's pipeline tells Amoeba what it released and what that touched. Another member's pipeline asks at the start of a slice whether anything it depends on has changed, then either picks the change up as context or stops with a reason.
- **C: the PM asks where things stand.** An agent calls Amoeba and gets a short status per member: what's running, what's blocked and why, and what was answered since the PM last looked.

### Programs

There is one kind of program: a set of repos where members depend on each other, usually on a **release** of another member. A toolchain and a product are the same concept.

### Answering

The answering run is a Squadron pipeline with two steps, each isolated:

- **A closed set of evidence.** The answer step sees only the passages Amoeba supplies, and cites them.
- **An independent check.** The check step sees the question, the passages and the reply, and shares no session with the answer step.
- **No tools.** A passage that steers the model can at worst produce a wrong reply.

These are properties of the step's configuration, not of a model vendor. Claude models work here (`ecorkran/squadron#299`, closed).

### Decisions

- **A checkpoint is a persisted blocked-state, not a blocking call.** A paused run holds no process open, so the PM can answer whenever. Kept from the original concept.
- **Amoeba owns the program and question state.** Context Forge persists only workflow pointers, and Squadron persists only per-run state. Kept, in SQLite.
- **Amoeba depends on upstream shapes, not version numbers.** Kept.
- **"State is the interface; parts never call each other" no longer holds.** Agents and pipelines call Amoeba directly.

### What happened to the original pieces

| Piece | Now |
|---|---|
| Runner | No longer the centre. Whatever survives is decided by the audit below. |
| Routing engine | Gone. Squadron owns routing. |
| Judge | Became the answering pipeline. |
| Translator | The separate chat agent app. |
| Notification bridge (Discord) | Dropped. Amoeba notifies agents. |
| Run-state store | Stays, reduced to what the scenarios need. |
| Resident substrate | Justified only by a scenario. |
| Multi-agent chat | Not Amoeba. |

### Grounding that still holds

Squadron facts below were read from its source at the dates in the notes; re-check the shape before depending on one.

- Squadron pauses a run on an agent's question (`checkpoint.kind = agent_question`, read through `sq runs wait --json`), and `sq run --resume <id> --instructions "<answer>"` reruns the stopped step. See `notes/004-direction.amoeba.md`.
- Squadron's daemon is frozen and is not used by its pipeline engine, and Squadron will not build a server or message layer.
- Squadron persists per-pipeline run state with resumable run ids, and its pipelines own phases, thresholds, revisions and judges.
- Context Forge persists workflow pointers and does not store findings or checkpoints.

### Open for architecture

1. **Who notices a paused run?** A Squadron hook that calls Amoeba needs a Squadron change and no watcher. A watcher needs no Squadron change but puts something back in the background. This decides whether a resident process exists at all.
2. **What the operations are** that MCP and the CLI share.
3. **How a member declares what it depends on, and what counts as a release** for a repo that doesn't publish versions. The current program record may be too much or too little.
4. **How a Squadron pipeline in one repo reaches a program's state**, so that scenario B needs no human.
5. **Which agent gets told** when a question has to go to the PM, including when no session is open. The chat agent is the natural recipient, but it's a separate app and not finished.
6. **Whether requests between members stay.** Initiative 180 planned for an agent to ask another member for a change, plus hold, release and ordering. None of that is in the scenarios, and some of it walks the graph.

### Development approach

- **Scenarios first.** Nothing gets built unless a scenario needs it, and a new need starts as a new scenario.
- **Audit before building.** Today's code (about 34k lines in `src`, 69k in `tests`, measured 20261106) gets sorted against scenarios A to C into keep, move to Squadron, or delete. The slice plan is rebuilt from that result, and slices 182 to 186 are re-judged there.
- **First proof.** Scenario A, end to end, on a real run the PM started. The PM picks the unit of work from whatever is unstarted at the time.
- **Build by inducing failure.** Point it at real work, and each wrong answer or needless escalation shows what to change next.
- **Favor simplicity.** If it could be a Squadron pipeline, it should be.
