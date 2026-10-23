---
docType: notes
layer: project
project: amoeba
source: user/project-guides/001-initiative-plan.amoeba.md
audience: [human]
description: Milestones for Amoeba from the user's seat — when each capability becomes usable, what you could do with it, and why you would. Derived from the initiative plan and the 120 slice plan; no dates, because nothing in the plans carries any.
dateCreated: 20261022
dateUpdated: 20261022
status: in_progress
---

# Amoeba Milestones

## Why use this

Building with AI tooling works until a project gets complicated. Then you become a full-time operator of a pipeline that is mostly deterministic: run a command, read the findings, decide advance-or-block, repeat. Amoeba takes over that operating. You state intent ("take slice X to implementation"), it drives Context Forge and Squadron, and it comes back to you only for genuine decisions, with the context to make them. It will not make those decisions for you.

**What it costs you:** until Milestone 4 it does not drive anything on its own. Milestones 0–3 build the machinery, and the first point where you hand it work and walk away is the First Proof.

## Milestones

| # | Milestone | Slices / initiative | You can… | Status |
|---|---|---|---|---|
| 0 | **Substrate** | 100 (slices 101–110) | Run the resident process (`amoeba start`/`stop`/`status`). Submit intents and resolutions from anywhere (`amoeba submit`). Feed in Squadron reviews (`amoeba ingest review`) and see them as verdicts with provenance. Watch project state change live (the feed, `amoeba serve` over HTTP, `amoeba inspect`). Prune finished paused Squadron runs (`amoeba prune sq-runs`). | Done |
| 1 | **The Runner exists** | 120–122 | Nothing new yet at the surface. Under it, recovery finds a run by its id (120 is done), the store holds what the Runner needs (121), and a command goes out, is watched without blocking, and survives a crash (122). | 120 done |
| 2 | **It mirrors and takes direction** | 123–125 | See your Context Forge plan as a tree that stays in step as the plan changes (123). Tell it what to work on, and stop it, without touching the store (124). One lifecycle step runs end to end under Amoeba and its result lands as evidence (125). **First time it does a step for you.** | Planned |
| 3 | **Safe on a real repo** | 126–128 | Every outcome gets an explained route, and the routing table is a file you edit (126). A decision you give on a stuck node is carried out without you running Squadron by hand (127). Gates, git and human steps are respected, so it can be pointed at a real repository without surprises (128). | Planned |
| 4 | **First Proof** | 129 | Pick one unstarted unit of work in one project and have the Runner drive it design → tasks → implementation to your merge, under your intents. Every stop it makes is recorded as evidence for the routing table. **First time "why use this" is true.** | Planned |
| 5 | **Fewer, better stops** | 130–131 | Batch a plan-wide run as one dispatch (130). Route on an inferred tier, so trivial findings stop interrupting you (131). Scope comes from what the First Proof's stops show, so 131 is deliberately not designed yet. | After the proof |
| 6 | **Judge** | 140 | Findings the table flags as judgment calls go to an ephemeral Judge first, run several times, and reach you only on low agreement. Starts as always-escalate until trust is earned per category. | Not started |
| 7 | **Talk to it, get pinged** | 160 | Steer in natural language from your editor or chat. Get a Discord ping when something needs you, and reply to unblock the node. | Not started |
| 8 | **Several repos, one product** | 180, then 200 (both tentative) | See what is blocked on you across a program's repos (180), and work across projects in one conversation (200). | Tentative |

## Reading the table

- **Order is dependency order, not a schedule.** The plans carry no dates and no calendar estimates, so this note gives none.
- **Milestones 6 and 7 are independent.** They both attach to the spine from Milestone 4. Which comes first is your call once 120 is done, and 180/200 slot in the same way.
- **The proof decides what comes after it.** The plan is depth-first and built by inducing failure: where the First Proof stops that it should not have is what shapes 130, 131 and the routing table.

## Not in v1

Multi-project scheduling (fairness, a global limit on in-flight runs), automatic retry for transient faults, per-project routing tables, and relinking a renumbered slice. All are recorded under the 120 slice plan's Future Work and wait for real use to show they are needed.
