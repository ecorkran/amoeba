---
docType: notes
layer: project
project: amoeba
source: user/project-guides/001-initiative-plan.amoeba.md
audience: [human]
description: Milestones for Amoeba from the user's seat — when each capability becomes usable, what you could do with it, and why you would. Derived from the initiative plan and the 120 slice plan; no dates, because nothing in the plans carries any.
dateCreated: 20261022
dateUpdated: 20261103
status: in_progress
---

# Amoeba Milestones

## Why use this

Building with AI tooling works until a project gets complicated. Then you become a full-time operator: start the pipeline, notice it stopped, read why, answer the agent's question, resume it, start the next one, across several projects at once. Squadron already runs each pipeline end to end. Amoeba runs the layer above it: it starts each project's pipeline on the work you point it at, keeps the runs moving, answers what the agents ask, and keeps one list of what really needs you.

**What it costs you:** it works today, from the command line only. You register and link projects by inbox message, write a per-project config (pipeline, and the `answerer` section with no defaults), steer with `amoeba submit` and read the blocked list with `amoeba inspect blocked`. It coordinates nothing across repos yet (Milestone 5) and has no chat or pings (Milestone 6).

## Milestones

| # | Milestone | Slices / initiative | You can… | Status |
|---|---|---|---|---|
| 0 | **Substrate** | 100 (slices 101–110) | Run the resident process (`amoeba start`/`stop`/`status`). Submit intents and resolutions from anywhere (`amoeba submit`). Feed in Squadron reviews (`amoeba ingest review`) and see them as verdicts with provenance. Watch project state change live (the feed, `amoeba serve` over HTTP, `amoeba inspect`). Prune finished paused Squadron runs (`amoeba prune sq-runs`). | Done |
| 1 | **The Runner exists** | 120–122 | Recovery finds a run by its id (120), the store holds what the Runner needs (121), and a command goes out, is watched without blocking, and survives a crash (122). | Done |
| 2 | **It mirrors and takes direction** | 123–128 | See your Context Forge plan as a tree that stays in step as the plan changes (123). Tell it what to work on, and stop it, without touching the store (124). Runs launch, are watched and land as evidence (125), and a decision you give on a stuck run is carried out (127). Routing (126) and gates (128) were built too; 132 removes most of them. | Done |
| 3 | **Supervisor** | 132 | Point it at slices and walk away. It runs each project's configured Squadron pipeline, marks finished work done, resumes crashed runs, and lists the rest with the reason. **First time "why use this" is true.** | Done |
| 4 | **Answers agents' questions** | 140–145 | Runs that stop because an agent asked a question get answered from your project's rules, plan and earlier answers (cited, and checked by a second model), and resume on their own. Merge and other PM-reserved questions are screened out. Only what it cannot answer reaches you. Proven live against real models (`docs/answerer-walkthrough.md`). | Done |
| 5 | **Several repos, one product** | 180 | Declare a program (`trading` = data, engine, UI; or Squadron, Context Forge, the guide, Amoeba). When one repo needs a change in another, the request becomes work in the other repo, the dependent slice is held until it is satisfied (merged, or a probe passes for tool repos), then released and resumed. See what is blocked on you across the program in one list. | Next |
| 6 | **Talk to it, get pinged** | 160 | Steer in natural language from your editor or chat. Get a ping when something lands on the blocked list, cross-project holds included, and reply to unblock it. | Not started |
| 7 | **One conversation across projects** | 200 (tentative) | Work across a program's projects in one chat, with each project's agent as a participant. | Tentative |

## Reading the table

- **Order is dependency order, not a schedule.** The plans carry no dates and no calendar estimates, so this note gives none.
- **What it stops on decides what comes next.** The questions agents actually ask and the stops that still reach the blocked list shape 180 and 160. The order 180 before 160 was set 2026-11-03: coordination across repos is the pain now, and chat and pings follow it.

## Not in v1

Multi-project scheduling (fairness, a global limit on in-flight runs) and relinking a renumbered slice. Both are recorded under the 120 slice plan's Future Work and wait for real use to show they are needed.
