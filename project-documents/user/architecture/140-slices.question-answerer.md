---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/140-arch.question-answerer.md
archIndex: 140
component: question-answerer
audience: [human, ai]
description: Slice plan for Amoeba initiative 140 — the answering pipeline against Squadron, the question record, the gate and answer submission, source passages, the answering run, and a live walkthrough.
dateCreated: 20261031
dateUpdated: 20261101
status: not_started
---

# Slice Plan: Question Answerer

## Parent Document

`140-arch.question-answerer.md`

## Planning Context

Architecture-level, built on complete initiatives 100 and 120. The answerer is a stage inside the Runner tenant, so every slice extends the Runner and 100's store rather than adding a process. A question stays a `HUMAN` block, as 132 writes it; the answerer works on that same block and the PM can answer it at any time.

Three things shape the decomposition:

- **Squadron capability first.** The answering run needs a no-tools, scratch-directory, two-step pipeline from `sq`. That is the one external unknown, so it is confirmed before anything is designed against it.
- **Deterministic before nondeterministic.** The question record, the gate, the answer-submission operation and the source passages need no LLM. They ship first, each testable alone. The answering run then plugs into a stage whose bounds already exist.
- **Bounds before the first resolution.** The gate and the operation that submits an answer ship before the answering run, which is the first slice that submits a resolution.

Slice numbers are execution order. Following the slice-planning guide, the first slice takes the plan's index (140).

## Foundation Work

1. [ ] **(140) Answering Pipeline** — The Squadron pipeline the answering run uses, proven against the installed `sq`. Two steps: an answer step that gets the question and numbered, dated passages and writes an answer artifact (an answer citing passage ids, or a decline with a reason), and a check step that sees the question, the answer and the whole passage set, not the answer step's reasoning, and writes yes or no. The check step is told the precedence rule: the later-dated passage wins, and its yes means the cited passages settle the question and no passage of equal or higher precedence contradicts the answer. Both steps run with no tools, from a working directory Amoeba chooses. The pipeline ships with Amoeba. The minimum `sq` version that runs it is pinned beside 0.24.9, and the start-up `sq` probe checks the shape the answering run depends on.
   **Value:** Architectural enablement. Removes the one external unknown before the answering run is designed.
   **Success Criteria:**
   - A run of the pipeline with a fixed question and passages, from a scratch directory, writes both artifacts in the documented shape.
   - A test shows neither step can read or write files: a passage asking the agent to create a file leaves the scratch directory unchanged.
   - The check step's input holds the question, the answer and the whole passage set, and not the answer step's conversation, shown from the run's recorded prompts.
   - With a fixed passage set where a later PM answer contradicts an older rule, the check says yes; where a later rule contradicts an older PM answer, it says no. Run against the real pipeline, not a stub.
   - The minimum `sq` version is recorded in the process contract, and the start-up probe fails on an `sq` that cannot run the pipeline.
   - Any capability `sq` lacks is filed as a Squadron issue and named in this plan as a dependency of 144.
   **Dependencies:** None inside Amoeba (100 and 120 complete). External: a Squadron release with the capabilities in the slice design's D8 (Squadron issue: ecorkran/squadron#284). The real-run criteria wait on it.
   **Interfaces:** Provides the pipeline file, its artifact shapes and the readers that parse them to 144, so 144 does not parse artifacts itself. Extends the `sq` shape probes (120's slice 122) with an answering-pipeline probe that 142 wires into start-up.
   **Risk Level:** Medium. It depends on Squadron features not yet used by Amoeba, and on a model following the precedence rule.
   **Relative Effort:** 2

## Feature Slices

2. [x] **(141) Question Record** — Every question becomes a record. When a `QUESTION` outcome is ingested, 132's `HUMAN` block is written as today and, in the same ingest, a question record is written (state `pending`), linked to project, slice, run, step and that block, with the question text and a flag when it looks cut off. The record states are `pending`, `answering`, `answered` and `declined`, with `answered_by` (answerer or PM) and a reason on a decline. A new answering stage in the Runner's tick, after observe and ingest, declines every pending question, with "answerer not configured" when the project has no answerer configuration and "no answer on file" otherwise; a node that was already blocked, and a null question are declined without a run. A question whose block the PM has already resolved is skipped, and the Runner's acknowledgment of that resolution marks it answered by the PM. A PM `resume` with instructions on a question block is recorded on its question as the answer, with the PM as `answered_by`; a resume without instructions is not precedent. The blocked listing and `amoeba inspect` join each question's block to its record, and `amoeba inspect questions` lists the records.
   **Value:** Architectural enablement, and a visible change for the PM: questions are listed as records with their history, and the blocked list shows whether a question was declined and why.
   **Success Criteria:**
   - A question-paused run produces one `HUMAN` block, exactly as 132 wrote it, and one linked question record; the blocked list shows the same text 132 showed.
   - A question on an already-blocked node produces a record declined with "node already blocked" and no second block.
   - A null question is recorded and declined with its own reason. A question whose block the PM resolved before the stage ran is marked answered by the PM and no run starts.
   - A project with no answerer configuration has every question declined as "answerer not configured", so every question still reaches the declined state.
   - A PM resume with instructions records the answer with the PM as `answered_by`; one without instructions records nothing as precedent. A resume that an answerer submission made is never recorded as the PM's. The rule is decided from the record, not from the submission's `submitted_by` string, and a test covers it.
   - The question record's states and transitions are fixed in the store contract, and an illegal transition raises.
   - A crash between writing the block and the record loses nothing: the question is written in the same transaction as the block, or the next tick finds the missing record from the block.
   - `amoeba inspect blocked` shows each question's state; `amoeba inspect questions` lists records with state, question, answerer and outcome.
   **Dependencies:** None beyond 120. Independent of 140.
   **Interfaces:** Adds the question record table by migration and a record-only update for declines to `docs/store-contract.md`. Changes 132-owned ingest of a `QUESTION` outcome (`runner/ingest/outcome.py`) to also write the record. Consumed by 142, 143 and 144.
   **Risk Level:** Medium. It touches 132's outcome ingest, which 160 will notify on.
   **Relative Effort:** 3

3. [x] **(142) The Gate and Answer Submission** — Every answer the answerer would submit goes through one gate, and one store operation submits it. The gate is a pure function: the per-run answer limit (read from the record), and the PM-reserved screen, which matches the project's configured reserved terms case-insensitively against the question and the answer. A failing answer is declined with the reason. The submission operation lives in 100's store: under one `BEGIN IMMEDIATE` it reads the run's answer count, applies a `resume` resolution with instructions (restating the question) with the answerer as submitter, and marks the record `answered` with `answered_by=answerer`. If the block is already resolved, the resolution is rejected and the record is marked "PM answered first". Nothing calls the operation yet outside tests.
   **Value:** Architectural enablement. The bounds and the atomic submission exist, and are proven, before any model answers.
   **Success Criteria:**
   - An answer over the per-run answer limit is declined with that reason; the block already on the node is the PM's and no second block is written; the run's questions and answers are read from the question record.
   - An answer whose question or text contains a configured reserved term is declined with the matched term in the reason.
   - A passing answer is submitted and the record is `answered` in one transaction. A crash between the two leaves neither or both: a test kills the operation mid-way.
   - A PM resolution and an answerer submission for the same block: whichever applies first wins; the answerer's is rejected, the record notes "PM answered first", and the PM's answer is the one recorded as precedent.
   - Two answers submitted in the same tick count against the limit once each, and not twice.
   - The answer limit and the reserved terms come from per-project configuration with no hard-coded defaults. An empty list of reserved terms is accepted only when written explicitly; a project with an answerer section missing either value fails at load.
   **Dependencies:** 141.
   **Interfaces:** Adds the submission operation to `docs/store-contract.md`. Extends `projects.yaml` (answerer section: answer limit, reserved terms). Runs 140's answering-pipeline probe at start when any project has an answerer section. Provides the gate and the operation to 144.
   **Risk Level:** Medium. The reserved screen is a net, not a proof, and the transaction has to fit the inbox's own.
   **Relative Effort:** 3

4. [x] **(143) Source Passages** — The sources an answering run sees, assembled from the target branch's committed state. Reads the project's rules from the paths and globs in its answerer configuration, and its CF plan (concept, initiative plan, architecture, slice plan, the slice's design and tasks), with `git show` against the target, cuts them into numbered passages that keep their path and carry the date of their file's last commit, and adds every PM answer the project has recorded as a dated passage with the question it answered and the slice it was for. The answerer's own answers are never included. Rules and plan passages are never trimmed: if they alone exceed the configured size limit, assembly fails with "sources too large". PM answers are kept in this order until the limit is reached: those for the same slice, then the most recent. A citation check confirms that every cited id is in the set supplied.
   **Value:** Architectural enablement. Pure and testable without Squadron or an LLM; makes the grounding check mechanical.
   **Success Criteria:**
   - Assembly reads committed content only: an uncommitted edit in the checkout does not appear in the passages.
   - Every passage carries its id, path or source, and date; every PM passage also carries its question and slice.
   - An answer the answerer itself gave never appears as a passage.
   - Over the size limit, PM answers are dropped in the documented order and the dropped ones are recorded; rules and plan passages are never cut, and a set that cannot fit declines with "sources too large".
   - The citation check rejects an id not in the supplied set and an answer citing nothing.
   - Rules paths and globs and the size limit come from per-project configuration with no defaults.
   - Tests use this project's own rules and plan files as fixtures, not invented ones.
   **Dependencies:** 141 (PM answers come from the question record). Independent of 140 and 142.
   **Interfaces:** Provides the passage set, rendered in the `passages.md` format fixed in 140's design (no shared code), and the citation check to 144. Extends `projects.yaml` (rules paths, size limit). Reads git with `show` and `log` only, like the Runner's existing git reads.
   **Risk Level:** Low
   **Relative Effort:** 2

5. [ ] **(144) Answering Run** — The answerer answers. For each pending question, up to the project's configured cap on concurrent answering runs, the stage first checks that the question's block is still open, then assembles passages (143) and launches the answering pipeline (140) as a journaled `sq_answer` entry on the slice node, from a scratch directory under the store directory, without the checkout lookup, clean-tree check or checkout hold. The record moves to `answering` with the entry id. When the run ends, a pure function decides from recorded inputs: the run succeeded, the answer's citations pass the check, and the check step said yes. A confirmed answer goes through 142's gate and submission; anything else, including any failure of the answering run, is declined with the reason. A shared reader returns a slice's journal entries without `sq_answer`, and the supervisor's latest-entry readers use it. A repeat of a question the PM already answered is handled the same way as any other: the PM's answer is a passage, and a question that means the same thing in other words is answered from it.
   **Value:** User value. Milestone 4: questions with an answer in the rules, the plan or the PM's earlier answers resume without the PM.
   **Success Criteria:**
   - A question whose answer is in a supplied passage resumes the run, and the record holds the answer, the cited passages, the check's verdict and the run id.
   - A question that repeats an earlier PM answer in different wording, on the same or another slice where the meaning is the same, resumes from that answer. A question for another slice where the slice makes the answer different is declined. Tests use question tails from real Squadron runs.
   - A no from the check step, an uncited answer, a malformed or missing artifact, and a failed, orphaned, stalled or cost-capped answering run each decline the question with a distinct reason. None is retried.
   - A PM resolution is accepted while an `sq_answer` is in flight, and the answerer's resolution is accepted after one resolves, with the `sq_run` still found as the run to resume. A test proves both against `classify`, `run_to_resume`, the checkout hold, dispatch state and the resume counter.
   - A restart with an answering run in flight adopts it by run id through journal recovery and never launches a second one.
   - No answering run starts for a question whose block the PM has already resolved.
   - A burst of questions never starts more answering runs than the configured cap.
   - The answering pipeline is the file Amoeba ships (144's design, D1). Its models, the concurrency cap and the cost cap come from per-project configuration with no defaults; Squadron's `max_cost_usd` is set on every answering run.
   - A PM answer that lands while the run is in flight wins, and the run's later result changes nothing but the record.
   **Dependencies:** 140, 142, 143. Any Squadron issue 140 files (ecorkran/squadron#284).
   **Interfaces:** Adds `sq_answer` to the journal's command kinds with its required parameters and recovery observer (`docs/process-contract.md`, `docs/store-contract.md`). Changes 132-owned readers of a slice's latest journal entry to use the shared reader (`resolutions/classify.py`, `supervise.run_to_resume`, `dispatch/hold.py`, `dispatch/state.py`, `ingest/record.py`). Extends `projects.yaml` (models, concurrency cap, cost cap).
   **Risk Level:** High. First LLM decision that resumes real runs without the PM, and the second change to 132's code.
   **Relative Effort:** 4

## Integration Work

6. [ ] **(145) Live Walkthrough** — A real run end to end, as in slice 132's walkthrough: a scratch CF project in a throwaway registry, a scratch checkout with rules and a plan, and a throwaway store. A real pipeline run on a slice whose agent asks a question answered by the plan resumes with the answer and completes. A question asking to merge to `main` is declined by the reserved screen and handed to the PM. A PM answer is used when a question that means the same thing is asked again in different words. A PM answer given after a rule changed stands against that rule. The real registry is untouched.
   **Value:** Verification that the stage works against real Squadron and real agent questions, not only fixtures.
   **Success Criteria:**
   - The four cases above happen as described, with records and journal entries that show each step.
   - The walkthrough steps are recorded in the docs so it can be repeated.
   - Any question shape the walkthrough meets that the fixtures lacked becomes a fixture.
   **Dependencies:** 144.
   **Interfaces:** None new.
   **Risk Level:** Low
   **Relative Effort:** 2

## Implementation Order

`140 → 141 → 142 → 143 → 144 → 145`.

- **Dependencies.** 144 needs the pipeline (140), the gate and submission (142) and the passages (143). 142 and 143 both read the question record (141).
- **Risk.** 140 comes first because it is the only slice that can be blocked by something outside Amoeba; a Squadron gap found there has the length of 141–143 to be fixed.
- **Testability.** 141 through 143 need no LLM and are tested with hand-made answers; 144 is the first slice that resumes a run on the answerer's word.
- **Parallel work.** 140 is independent of 141–143, and 143 is independent of 142, if separate worktrees are used.

## Notes

- **Migration order.** 141 adds the question record table; 142 adds the submission operation over it. Slice design assigns migration numbers in build order.
- **Behavior between slices.** After 141 every question still reaches the PM exactly as before, with a record beside it. 142 and 143 change nothing a PM sees. After 144 the answering run answers what it can ground and confirm.
- **Changes to 132-owned code.** Three, as the arch lists: the ingest of a `QUESTION` outcome writes the record (141), the readers of a slice's latest journal entry skip `sq_answer` (144), and the control surface gains the `sq_answer` kind (144).
- **Configuration lands where it is first read.** 142 adds the answer limit and reserved terms, 143 the rules paths and size limit, 144 the models, concurrency cap and cost cap, all in one `projects.yaml` answerer section. A project with no section has the answerer off.
- **No backfill.** The question record starts empty; questions and answers already in the journal are left behind (arch, Current State).
- **160 notifies on the declined state.** 141 is where a question gets its record and a declined state, so it is the point 160's notification bridge attaches to.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Full reply from Squadron** — If 141's cut-off flag shows truncation is common, ask Squadron to put the agent's full final reply in `sq runs wait --json`, keeping the rule that Amoeba never reads the run-state file. Dependencies: [141]. Effort: 1/5
2. [ ] **Answer `artifact_missing` replies** — A failed step whose agent replied without a `?` line carries its reply in `failure.agent_text`. Route those to the answerer if real sightings show they are questions. Dependencies: [144]. Effort: 2/5
3. [ ] **Agreement across answering runs** — If induced failure shows confirmed answers that are wrong, add N answering runs or models and require agreement before submitting. Dependencies: [144]. Effort: 3/5
4. [ ] **Program scope for precedent and sources** — When 180 lands, add the program concept as a source and let PM answers from member projects reach the passages. Dependencies: [144, 180]. Effort: 2/5
