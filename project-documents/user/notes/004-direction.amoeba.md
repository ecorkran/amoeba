---
docType: notes
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
audience: [human, ai]
description: Direction set 20261027. Amoeba becomes a supervisor network over Squadron, not a second orchestrator. Squadron owns the pipeline; Amoeba launches, watches, resumes, answers agents' questions, and keeps one blocked list across projects. Replaces the rest of the 120 slice plan.
dateCreated: 20261027
dateUpdated: 20261027
status: in_progress
---

# Direction: a supervisor over Squadron

## The decision

Amoeba stops re-implementing what Squadron already does. Squadron runs the pipeline. Amoeba sits one level above every project's Squadron runs, keeps them moving, and answers what their agents ask.

## Why

The Runner built in 120–128 mirrors Squadron's own features:

| Runner piece | Squadron already has |
|---|---|
| Stepping design → tasks → implementation | `p456`, `p56`, `p45`, and any user pipeline (a `p4567` that also merges is a user-written pipeline) |
| Routing on PASS / CONCERNS / FAIL against a threshold | the run's pass and accept thresholds |
| Rerun up to N times | `--max-revisions` |
| Plan-wide batch dispatch (slice 130) | `slices-plan`, `tasks-plan`, `implement-plan` |
| A Judge to weigh review findings (140) | `judge-cycle`, the findings-addressed judge |

Two copies of the same policy means two places to configure it and two places it can disagree. The shipped routing table had shrunk to "advance on pass, otherwise ask the PM", which made Amoeba worse than running `sq` by hand.

## What each side owns

**Squadron:** the pipeline. Which phases run, in what order, review thresholds, revision counts, judges, and the merge. All of it is pipeline definition and run parameters, set where `sq run` takes them.

**Amoeba:**
1. **Launch.** Start the pipeline a project is configured to run (any built-in or user pipeline) on the next unit of work.
2. **Watch and resume.** Track every run across every project. A run that completes is done. A run that crashes or stops for a transient reason is resumed (`sq run --resume`). The resident process, the store and crash recovery already do this.
3. **Answer agents' questions.** See below. This is the main job.
4. **One blocked list.** Everything Amoeba could not answer or resume, across all projects, with why, in one place.
5. **Notify and take answers back.** Tell the PM when something lands on the list; feed the answer into the same resume. (Initiative 160's notification bridge.)
6. **Later: the program level.** 180 (program record) and 200 (multi-agent chat) stand as planned, after the above works.

## Answering agents' questions

Today a phase agent that needs a decision ("which branch?", "redesign or leave?") ends its run, and the question goes to the PM. This was 120's Future Work 15. It is now the core of Amoeba.

1. **Catch.** A run ends because its agent asked instead of finishing.
2. **Answer.** Amoeba answers from what it holds: the project's rules and plan, the program concept (for `trading-*`), and earlier answers to the same question.
3. **Resume.** `sq run --resume <id> --instructions "<answer>"`. The answer is prepended to the dispatches that run.
4. **Otherwise list it.** A question Amoeba cannot answer goes on the blocked list. The PM's answer goes back through the same resume.

Bounds: the answerer only ever resumes with instructions. It does not edit code, merge, or change thresholds. Every question and answer is recorded, so a repeat is answered the same way and the PM can see what was decided for them.

Initiative 140 (Judge) becomes this answerer, not a second reviewer.

## What happens to the code

Measured 20261027: `src/amoeba/runner/` is about 12k lines; the rest of `src/amoeba/` is about 19k.

- **Keep:** `store/`, `process/` (launching, observing, resuming and pruning `sq` runs), `inbox/`, `serve/` (network API), `feed/`, `inspection/`, `cli/`, `upstream/`, and the Runner's tick, launch, observe, ingest, faults and crash recovery.
- **Shrink:** `runner/routing/` to "completed → done, otherwise answer or list"; `runner/resolutions/` to resume-with-instructions; `runner/project_config.py` to which pipeline a project runs and its parameters.
- **Delete candidates,** confirmed one by one against what pipelines do: the verdict routing in `runner/routing/`; the P4/P5/P6 step map and chaining in `runner/lifecycle/`; CF gate reads, ungate hatches and merge observation in `runner/gates/`; CF pointer moves in `runner/dispatch/` (pipelines move CF themselves).

## Plan changes

- **130 (Batch Dispatch):** superseded. Squadron's `*-plan` pipelines batch.
- **131 (Tier Inference):** superseded. Review routing is Squadron's.
- **140:** re-scoped to the question answerer above.
- **160, 180, 200:** unchanged in purpose.
- **Rule for all new work:** no design, task or step needs the PM to act, choose, or relay. Every decision has an automated answer; the blocked list is the only path to the PM.

## What Squadron already gives us

Read from Squadron's source 20261027 (installed `sq` 0.24.6).

- **Questions are caught for design and tasks.** After a dispatch that should write an artifact and didn't, a reply with a line ending in `?` pauses the run with checkpoint kind `agent_question`. `sq runs wait --json` reports the question in `checkpoint.question` (the reply's last 400 characters). Without a `?` line the run fails as `artifact_missing`. Then the text is only a suffix of `failure.message`. Squadron added the question pause on 20261021 (after 0.23.7) and the trailing-options fix on 20261024. Amoeba's `artifact_missing` sightings predate both or lacked a `?`.
- **The full reply is in the run-state file:** `completed_steps[].action_results[]`, the `dispatch` entry, `outputs.response`.
- **Resume works on paused and failed runs.** `sq run --resume <id> --instructions "<answer>"` reruns the stopped step as a fresh dispatch, with the answer prepended to every prompt. The rerun may not see the earlier conversation, so an answer restates the question it answers. `--decision accept` applies only at loop steps.
- **Pipelines move CF's pointers themselves.** Every design, tasks and implement phase step runs `cf set slice`, `cf set phase` and `cf build` before dispatching. Amoeba's own pointer moves in `runner/dispatch/` are redundant.

## Squadron gaps

- **Implement-step questions are missed.** Implement has no expected artifact, so an implementation agent that stops on a question counts as a successful step, and the pipeline goes on to review and merge. Fix on Squadron's side: run the question check on implement dispatches too.
- **`artifact_missing` carries no question field.** Small fix on Squadron's side: put the final text on the failure (`dispatch_artifact.py` `_failure_metadata`, `run_outcome.py` `_failure`). Until then Amoeba reads `outputs.response` from the run-state file.

## Next

1. One slice: Amoeba runs a project's configured pipeline, marks completed runs done, resumes crashed ones, lists the rest, and deletes the routing, chaining and CF pointer moves it no longer needs.
2. One slice: the question answerer. It reads `checkpoint.question` and answers with `--resume --instructions`; otherwise the question goes on the list.
3. Squadron: the two gaps above.
