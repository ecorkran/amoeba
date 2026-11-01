---
docType: architecture
layer: project
project: amoeba
archIndex: 140
component: question-answerer
initiative: question-answerer
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [100-arch.substrate-run-state-store, 120-arch.runner-routing-engine]
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for Amoeba's question answerer. A Squadron run whose agent stopped to ask a question is answered from what Amoeba holds about the project and resumed with the answer; a question that cannot be grounded in supplied sources and confirmed by an independent check goes on the blocked list. Replaces the original Judge (component 4) per the 20261028 direction. Revised 20261031 and 20261101 after its architecture reviews.
dateCreated: 20261031
dateUpdated: 20261101
status: not_started
---

# Architecture: Question Answerer

## Overview

The question answerer is the judgment Amoeba spends. When a Squadron agent ends a step on a question ("which branch?", "redesign or leave it?"), its run pauses and, since slice 132, the slice lands on the blocked list. Most of those questions already have an answer somewhere Amoeba can read: the project's rules, its plan and designs, or an answer the PM gave before. The answerer finds that answer, resumes the run with it, and records what it decided. Only a question it cannot ground and confirm reaches the PM.

**The problem it addresses.** After 132 the supervisor launches, watches and resumes runs, but every agent question stops the slice until the PM reads it, answers, and submits a resume. Questions are the most common reason a run stops (`notes/004-direction.amoeba.md`), so until they are answered automatically "point it at slices and walk away" holds only between questions.

**Scope.** This component owns: (1) the **question record**, every question an agent asked, its lifecycle, the answer it got, the passages the answer rested on, and who gave it (the answerer or the PM); (2) the **answering stage** inside the Runner tenant that takes a question-blocked slice and either resolves it or hands it to the PM; (3) **answer generation**, assembling the project's sources and running a bounded answering run; (4) the **checks** that decide whether an answer is used; (5) the **bounds** on what the answerer may do and how often it may answer one run. It does not own the outcome map or the launch of pipeline runs (120), notifying the PM or taking replies from chat (160), the program concept as a source (180, which adds it), or anything Squadron's pipelines decide (reviews, thresholds, revisions, merge).

**Motivation.** This is milestone 4 in `notes/003-milestones.amoeba.md` and the reason the direction change kept Amoeba as more than a run babysitter. The concept's thesis carries over unchanged: deterministic control flow around one bounded nondeterministic subroutine, now pointed at questions instead of review findings.

## Design Goals

- **Questions with an answer on file never reach the PM.** If the rules, the plan, or the PM's earlier answer settles a question, the run resumes without a person, from the first slice that ships an answering run. There is no shadow mode in which the answerer runs but the PM still decides. The two checks below carry that trust.

- **Every answer is traceable.** For any resumed run, the record shows the question, the answer sent, the passages it cited, the independent check's verdict, and who answered. The PM can read what was decided for them without opening a transcript.

- **A question the PM already answered stays answered.** A PM's answer becomes precedent the moment it is given. When any slice later asks a question that means the same thing, in any wording, the answerer uses the PM's answer. "Means the same thing" is a judgment, so a model makes it, and an independent check confirms it.

- **Declining is cheap and safe.** A question the answerer cannot ground and confirm goes on the existing blocked list with the question and the reason. A wrong decline costs the PM one answer; a wrong answer costs a run. Every uncertain path ends in a decline.

- **The outcome map does not change.** 132's classification of runs stays as it is, and 132 still blocks a question as `HUMAN` with its payload. The Runner's control surface gains one command kind for the answering run, the code that reads a slice's latest journal entry learns to skip it (see "The answering entry and the slice's journal"), and the ingest of a `QUESTION` outcome (`runner/ingest/outcome.py`, `runner/ingest/record.py`) writes the question's block and record together, so a retry after a crash writes neither twice. The Runner's tick also gains the answering stage after ingest, and 127's `acknowledge_resolution` records the PM's answer on the question (slice 141, D1, D2 and D5). Those are the changes to code 120 owns; nothing else in the supervisor changes shape.

## Architectural Principles

- **The answerer is a stage of the Runner, not a second tenant.** It runs inside the Runner's tick, in its own modules, and launches its runs through the Runner's journaled control surface. The Runner stays the only part of Amoeba that issues `sq` commands. One tick order serializes the answerer, the supervisor, and the PM's resolutions on the same slice, so they never race each other.

- **The answer goes back through the PM's door.** A confirmed answer becomes a `resume` resolution with instructions, submitted through 100's inbox with the answerer as the submitter, and applied on a later tick like the PM's. One path, one validator, and a submission record of who answered. The instructions restate the question, because the rerun may not see the earlier conversation.

- **Answers are grounded in supplied passages and confirmed independently.** Amoeba supplies the sources as numbered passages; an answer must cite passage ids from that set, which is checked mechanically. A separate check, which sees the question, the answer and the whole passage set but not the answer step's reasoning, must say the cited passages settle the question and that no other passage of equal or higher precedence contradicts the answer. Precedence is by date: every passage carries one (a rules or plan passage, the date of its file's last commit on the target; a PM answer, the date it was given), and the later passage wins. A PM answer given after a rule was last changed therefore stands against that rule, so a deliberate exception becomes precedent; a rule changed after the PM answer overrides it, and the question goes back to the PM. Anything other than an unqualified yes is a decline. Self-reported confidence counts for nothing.

- **The answering run is read-only by construction.** It gets pre-assembled text, no file tools, and a scratch working directory under Amoeba's store directory. It never touches a project checkout, so it cannot edit code, commit, or merge, and it does not hold or wait on a checkout.

- **One gate for every resolution.** Every answer the answerer would submit, including one that rests on a PM answer, passes the same gate: the per-run answer limit and the PM-reserved screen. A question whose answer would authorize something the project's rules reserve for the PM (a push, a merge to `main`, a release, a destructive database statement, a policy change) is declined however well it is grounded. A question asked after its run reached the answer limit is declined with that reason; the block already on the node is the PM's, and the run's questions and answers are read from the question record through the blocked listing and `amoeba inspect`.

- **The record is the memory.** Precedent, crash recovery of answering, and the PM's view of what was decided all read one question record in 100's store. Nothing is remembered in prompts, files, or process memory. Every record transition that has an effect (submit the resolution and mark `answered`; mark `declined`; mark `answered` by the PM when the Runner acknowledges the PM's resolution) commits in one store transaction with that effect, and the gate reads the run's answer count from the record inside the same transaction. The inbox opens its own transaction, so this is one new operation in 100's store, not a wrapper around the inbox call: it applies the resolution and updates the record under one `BEGIN IMMEDIATE`, and branches on the outcome. A resolution applied marks the record `answered` with `answered_by` set to the answerer. A resolution rejected because the block is already resolved discards the run's answer and leaves the record to the acknowledgment of the PM's resolution, which marks it answered by the PM: that is the record's note that the PM answered first.

- **Who answered is a field, not a label.** The answerer's own operation sets `answered_by=answerer` on the record. A question counts as answered by the PM only when its block was resolved by a resume that did not come through that operation, which the record can decide by itself. The submission's `submitted_by` string is provenance only and is never read to decide this. A crash therefore leaves either both or neither: no answer is submitted twice or counted twice, and no record says `answered` with nothing in the inbox.

- **Precedent is the PM's answers, matched by meaning.** Each PM answer reaches the answering run as a dated passage that carries the question it answered and the slice it was given for. The answer step decides whether a new question means the same thing, taking the slice into account ("which branch?" for another slice is a different question). The answerer's own answers are never passages, so one wrong answer cannot become the ground for another. Because the check step sees the whole passage set, a rule newer than a PM answer that contradicts it makes the check say no, and the question goes to the PM. There is no exact-match shortcut and no separate matching code: a repeat is just a question whose best passage is a PM answer.

- **Failures decline; nothing retries.** An answering run that fails for any reason (failed, orphaned, provider error, stall, cost cap, missing or malformed answer artifact) declines the question with that reason. The PM sees the question; the spend stops.

## Current State

Slice 132 left a clean seam:

- `runner/supervise.py` classifies a pause with checkpoint kind `agent_question` as `QUESTION`.
- `runner/ingest/outcome.py` writes that slice a `HUMAN` block whose payload holds the run id, reason `agent_question`, the step, and the question text (the reply's last 400 characters, which may be absent).
- The `resume` resolution with instructions is the way back: the Runner reruns the stopped step with `sq run --resume <id> --instructions "<text>"`, journaled as a resolution resume.
- Journal entries are tied to a node, and adding a command kind is a fixed three-part change (the kind, its required parameters, a recovery observer).
- Inbox submissions record who submitted them.

What is missing, and what this component adds:

- **Nothing answers.** Every question waits on the PM, so the blocked list fills with questions that already have answers on file.
- **Questions are not records.** A question exists only as a block payload. When the block is resolved, the question and its answer survive only as journal parameters, with no link between them. 140 does not backfill these: the question record starts empty, and 132's "earlier answers" contract is satisfied by the record from here on.
- **The store keeps payloads and escalation messages only for `HUMAN` blocks.** That is why 132 blocks questions as `HUMAN`, and 140 keeps it that way: the PM's blocked list, 160's notifications, and the PM's way to answer all already work on that block. The unused `JUDGE` kind is left alone.
- **Every launch is a checkout launch.** The Runner's launch path resolves a checkout per node, checks it is clean and on an allowed branch, and holds it until the run ends. An answering run needs none of that.

## Envisioned State

When this component is complete, a question-paused run moves through Amoeba like this. Each step runs inside the Runner's tick, in a stage after observe and ingest.

1. **Catch.** The supervisor classifies the outcome as `QUESTION` and writes its `HUMAN` block, exactly as 132 does. In the same ingest the question is written to the question record (state `pending`), linked to the project, slice, run and step and to that block, with a flag if the question looks cut off. The PM can see and answer the question from this moment, on the same blocked list and through the same resolution. If the node was already blocked for another reason, no new block is written (the store writes none), the record is still written, and it is declined at once with the reason "node already blocked". The question record is never skipped.

2. **Queue.** On its next pass the answering stage takes each `pending` question, in order, up to the project's configured cap on concurrent answering runs; the rest wait for a later tick. Before it starts step 3 it checks three things, each settled without a run. If the project has no answerer configuration, the question is declined with "answerer not configured", so it still reaches the declined state that listings and 160 act on. If the question's block is no longer open because the PM already resolved it, no run starts; the Runner's acknowledgment of that resolution marks the record answered by the PM (slice 141, D2). A question with no text is declined.

3. **Answer.** The answering stage assembles the sources from the target branch's committed state: the project's rules (the paths and globs in its answerer configuration, so no prose is parsed to find them) and its CF plan (concept, initiative plan, architecture, slice plan, the slice's design and tasks), each as numbered passages that keep their path, plus every PM answer the project has recorded, each as a dated passage with the question it answered and the slice it was for. The answerer's own earlier answers are not sources. It launches the answering run as a journaled `sq_answer` entry on the slice node, and the record moves to `answering` with the entry's id. The run has two steps: an answer step that returns an answer citing passage ids, or a decline, and a check step that sees the question, the answer and the whole passage set, not the answer step's reasoning.

4. **Check.** When the run ends, a pure function decides from recorded inputs alone: cited ids exist in the supplied set, the check step said yes (the cited passages settle the question and nothing else in the set contradicts the answer), and the run succeeded. Otherwise it is a decline, with the reason.

5. **Gate.** The per-run answer limit and the PM-reserved screen apply to every answer, including one resting on a PM answer.

6. **Resolve or decline.** An answer that passes becomes a `resume` resolution in the inbox, submitted by the answerer against the question's `HUMAN` block, in the same transaction that marks the record `answered`. The Runner carries it out on a later tick as it does the PM's. A decline only marks the record `declined`, with the question, any declined answer and the reason. The block already says the PM is needed; the record says why the answerer did not answer, and the blocked listing and `amoeba inspect` show that from the record.

7. **The PM answers.** The PM's `resume` on the question block is the same resolution it is today, and when it carries instructions it is recorded on the question as precedent; a resume without instructions is not precedent. If the PM resolves the block while an answering run is in flight, the PM wins. The tick applies the PM's resolution first (see "The answering entry and the slice's journal" for why it is not rejected). The acknowledgment marks the record answered with `answered_by` set to the PM, which is the note that the PM answered first. When the answering run ends, its result is discarded and the record is not changed.

A restart finds in-flight answering runs through journal recovery for `sq_answer`, adopts them by run id, and never launches a duplicate.

**Order inside one tick.** The PM's resolutions are applied first, as today. Observe then watches `sq_run` entries and `sq_answer` entries in two separate passes. A finished `sq_run` goes through `record_finished` and 132's outcome map, which also writes the question record on a `QUESTION`. A finished `sq_answer` never goes to `record_finished`: it goes only to the answering stage's check, gate and resolve steps. The answering stage runs after ingest and before the act stage, under the same tick budget and fault isolation. It launches answering runs for pending questions and settles finished ones. Its resolutions are applied by the next tick's first stage, so an answer takes effect one tick after it is decided. `amoeba inspect` gains a view of questions and answers per project, and 160 can later notify on what was answered as well as what was blocked.

## Technical Considerations

- **Squadron capability and version.** The answering run needs a user pipeline whose steps run with no tools, from a working directory Amoeba chooses, where the check step sees only what Amoeba passes it and the answer step's output, not the answer step's conversation. This is confirmed against the installed `sq` before the answering run is designed, and the minimum `sq` version that supports it is pinned beside 132's 0.24.9 for `agent_question`. A missing capability is a Squadron change, not an Amoeba workaround.

- **Launch without a checkout.** `sq_answer` skips the checkout lookup, the clean-tree and branch checks, and the per-checkout hold. The answering stage issues it through the Runner's journaled control surface, a second launch site beside the act stage, and it counts against the tick's budget and fault isolation.

- **The answering entry and the slice's journal.** The `sq_answer` entry is journaled on the slice node, so every code path that reads the slice's latest entry must skip it. Today several do not: `resolutions/classify.py` treats an unresolved latest entry of any kind as "a command is in flight" and rejects the PM's resolution, and `supervise.run_to_resume` returns nothing unless the latest entry is a resolved `sq_run`, so after the answering run resolves, a resume would be rejected as `instructions_not_applicable`. The fix is one shared reader that returns the slice's entries without `sq_answer`, used by `classify`, `run_to_resume`, the checkout hold and dispatch state, and the resume counter in ingest. It is a small change to code 132 owns, made in the first slice that journals an answering entry, with a test that a PM resolution and the answerer's resolution are both accepted while and after an answering run exists. The unresolved `sq_answer` itself is not a reason to reject a resolution: the PM wins the race by design.

- **Assembling sources.** Rules and plan documents are many and long. Which go in, how they are cut into passages, and how it all fits one dispatch is the main design work of the answering slice. Reading from the target branch (`git show` against the target) keeps the paused run's working tree out of it; planning artifacts are committed on the target, so the plan is there. Code is not a source.

- **What "the same question" means.** Questions arrive as the last 400 characters of an agent reply, with varying preamble and options lists. Whether a new question means the same as one the PM answered is decided by the answer step, with each PM passage carrying its question and slice, and confirmed by the check step. Amoeba does no text matching.

- **Stale precedent and growth.** Rules and plans change after an answer is given. PM answers carry their dates and sit in the same passage set as the current rules, and the check step sees the whole set, so a newer rule that contradicts an older PM answer makes the check say no and the PM decides again. There is no invalidation scheme. Only PM answers are passages, and they grow without bound, so some must be left out of one dispatch. Trimming is part of the risk model: a PM answer left out is one the check step cannot see, and an answer that contradicts it could pass. Two rules limit that. Rules and plan passages are never trimmed; if they alone do not fit one dispatch, the question is declined with "sources too large". PM answers are kept in this order until the configured size is reached: those for the same slice, then the most recent.

- **Truncated and absent questions.** `checkpoint.question` may be null, or cut mid-sentence. A null question declines at once. The record's cut-off flag measures how often truncation happens. The fix, if it is needed, is asking Squadron for the full reply in `sq runs wait --json`, keeping 120's rule that Amoeba never reads the run-state file.

- **`artifact_missing` replies.** A failed step whose agent replied without a `?` line carries its reply in `failure.agent_text`. Some of those are questions in all but punctuation. They stay `BLOCKED` until real sightings show the answerer should take them.

- **Recognising PM-reserved questions.** The screen's terms come from per-project configuration beside the pipeline: a list of reserved terms (for example `push`, `merge to main`, `release`, `DROP`), with no defaults. The screen matches them, case-insensitively, against the question and the answer, and a hit declines. An empty list is allowed only when written explicitly. The screen is a net for the obvious cases and the check step is told to refuse reserved actions too; neither is a proof. The hard bounds are the per-run answer limit, the screen, and the fact that a wrong answer costs one rerun of one step, not a merge: the answerer can only resume a paused step with instructions, and it cannot push, merge or release. A project whose config has no answerer section has the answerer off and behaves as 132 does.

- **Store changes.** 100's store gains the question record table (by migration) and one operation that applies a resolution and updates the record in a single transaction (see "The record is the memory"), plus a record-only update for declines. The answering slice adds two more (slice 144, D4 and D5): one operation that journals the `sq_answer` entry and moves the record to `answering` in a single transaction, using the journal's insert, and a done-guard that ignores unresolved `sq_answer` entries, so a slice whose resumed run finishes during an answering run can still be marked done. The inbox itself is unchanged.

- **The blocked listing.** The question's block is the `HUMAN` block 132 already writes. The listing and `amoeba inspect` join it to the question record to show whether the answerer is working on it or has declined it, and why. 160 can notify on the declined state instead of on every question.

- **Cost and configuration.** Each answering run is spend. The answering pipeline is the file Amoeba ships and probes at start, not a configuration key (slice 144, D1). Its models, the per-run answer limit, the cap on concurrent answering runs, the rules paths and globs, the passage size limit, and the reserved terms belong in per-project configuration beside the pipeline 132 already configures, with no hard-coded defaults. Squadron's `max_cost_usd` bounds each answering run.

## Anticipated Slices

- **Squadron capability spike.** Confirm the no-tools, scratch-directory, two-step answering pipeline against the installed `sq`, and pin the minimum version. Any gap becomes a Squadron issue that the answering slice depends on.

- **Question record.** The question record and its lifecycle, writing it on every `QUESTION` outcome beside 132's `HUMAN` block, recording the PM's answers on their questions, the decline state shown on the blocked listing, and an inspection view of questions and answers. Deterministic; no LLM; submits nothing.

- **Gate.** The per-run answer limit and the PM-reserved screen, with their per-project configuration. They ship before the answering run, which is the first slice that submits a resolution.

- **Answering run.** Source assembly from the target branch plus the PM's recorded answers, the `sq_answer` command kind with its recovery observer, the shared latest-entry reader that skips it, launching and observing the answering run, parsing its artifact, the check function, and turning the result into a resolution or a decline.

- **Live walkthrough.** A scratch project in a throwaway registry, as in slice 132's walkthrough, where a real agent question is answered and the run completes, and a PM-reserved question is declined.

## Related Work

- `user/notes/004-direction.amoeba.md`: the direction that made 140 the question answerer, and what Squadron provides (`checkpoint.question`, `--resume --instructions`, implement-step questions since 0.24.9).
- `user/project-guides/001-initiative-plan.amoeba.md`: initiative 140's entry and its dependencies on 100 and 120.
- `user/architecture/100-arch.substrate-run-state-store.md`: the store, the inbox and its submissions, the blocked kinds, and the resident process.
- `user/architecture/120-arch.runner-routing-engine.md`: the supervisor, its tick order, its control surface and journal recovery, concurrency per checkout, and the "Direction Change" section.
- `user/slices/132-slice.pipeline-supervisor.md`: the `agent_question` block payload (D4), the `resume` resolution with instructions (D6), and its "Provides to Other Slices" contract for 140.
- `user/reviews/140-review.arch.question-answerer.md`: the architecture review this revision answers.
- `user/notes/003-milestones.amoeba.md`: milestone 4, "Answers agents' questions".
- Initiative 180 (Program Record): adds the program concept as a source and a program scope for precedent.
- Initiative 160 (Translator & Notification): notifies on what reaches the blocked list, including declined questions, and carries the PM's answer back into the same resume.
