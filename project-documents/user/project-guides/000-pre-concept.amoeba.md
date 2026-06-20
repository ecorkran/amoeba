---
layer: process
phase: 1
phaseName: concept
guideRole: primary
audience: [human, ai]
description: Pre-concept for Amoeba, an orchestration runner with deterministic control flow and bounded nondeterminism that drives Context Forge and Squadron through a project's full lifecycle with minimal human involvement, escalating only where judgment is the actual work.
dependsOn: [guide.ai-project.000-process.md]
project: amoeba
status: pre-concept
dateCreated: 20260618
---

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

### Open questions for the concept stage (resolve before the Runner starts)

1. **Auto-fix path.** Does Squadron today have any path to *act* on a finding (regenerate a task breakdown to add a missing load-test task), even human-triggered? If yes, "auto-fix-and-recheck" is a real routing branch and the easy tier gets dramatically more autonomous. If no, v1 routing is continue / Judge / escalate, and auto-fix is a later upgrade. **This determines how autonomous the first Kalshi run can actually be.**
2. **Checkability tier as an emitted field.** Should the Squadron reviewer self-classify each finding's tier at emission time ("mechanically verifiable" vs "requires judgment")? It produces the routing signal directly and cheaply, and yields free eval data on which categories the reviewer is reliable vs confabulating.
3. **`concern` overload.** Today `concern` spans Tier-1 rule violations and Tier-2 judgment. The routing policy can't act on `severity` alone. Resolving #2 resolves this.
4. **Judge confidence metric.** Confirm the metric is agreement-across-runs / agreement-across-models, not self-reported confidence. Decide N, decide whether consensus is per-model or per-run, decide the initial threshold (always-escalate) and the per-category trust-earning mechanism that lowers it.
5. **Translator's command authority.** What is the exact set of CF/SQ commands the Translator may issue, and does any have side effects that should themselves require human confirmation (vs. pure state-advancement)? Keep the Translator's authority narrow and deterministic in shape even though the Translator itself is an intelligence.
6. **Resident substrate / message queue.** The Runner is resident; the Translator, Judge, and (separately) Cowork all want to leave each other durable messages. Squadron has a daemon Erik never runs — but Squadron's *identity* is request-shaped (invocable pipeline engine), not resident-shaped. Decision: Squadron is the engine; the resident runtime + durable message-queue + structured-storage + embedding substrate belongs to Amoeba (or is a separate primitive Squadron, Amoeba, and Cowork all sit on as peers). The existing Squadron daemon is good infrastructure and should be reused as the base for that resident substrate rather than reinvented — but relocated out of Squadron's identity. **Confirm nothing in Squadron's pipeline/Langfuse/session paths depends on the daemon being resident before relocating it.**
7. **Kalshi discovery as a front-loaded concept input.** The one genuine unknown in the first proof is the Kalshi API's granularity / history / structure. Resolve it at concept (single research step), write it into the concept, and the storage-format decision (predicted: structured -> existing TimescaleDB) becomes a constraint to verify rather than a decision to make. Conditional checkpoint only: escalate if the data turns out non-relational / document-oriented.
