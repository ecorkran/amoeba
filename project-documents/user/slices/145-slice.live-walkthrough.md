---
docType: slice-design
slice: live-walkthrough
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies:
- 140
- 144
interfaces: []
dateCreated: 20261101
dateUpdated: 20261103
status: in_progress
turns: 21
promptTokens: 1747072
cachedTokens: 1635205
cacheWriteTokens: 111827
completionTokens: 31278
durationSeconds: 341.0
costUsd: 1.847708
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.8477084000000001
    completionTokens: 31278
---

# Slice Design: live-walkthrough

## Overview

Slice 145 runs the question answerer end to end against real Squadron runs and real agent questions. It covers the plan's four cases: a question answered from the plan, a question that asks to merge to `main`, a PM answer reused when the question comes back in other words, and a PM answer that stands against an older rule. The setup follows slice 132's walkthrough. There is a scratch Context Forge project in a throwaway registry, a scratch git checkout holding rules and a plan, and a throwaway Amoeba store. The real registry is never written.

The slice ships three things. The first is the scratch project's source tree, kept in the repository. The second is a setup script that builds the scratch environment from that tree. The third is `docs/answerer-walkthrough.md`, so anyone can repeat the walkthrough. Every question tail the walkthrough captures is added to 144's real-tail fixture.

## Value

This verifies milestone 4. Slices 141–144 are tested against the stub `sq` and against 144's live tier, which uses a stub-paused run. 145 is the first run where the paused run is a real slice pipeline and each question is one a real design agent wrote. It shows the PM what the answerer does on a real project: the records, the journal entries and the resumed runs. It also adds the question shapes found there to the fixtures that later tests use.

## Technical Scope

Included:

- The scratch project tree at `scripts/answerer_walkthrough/project/`: a concept, an initiative plan, an architecture, a six-slice plan and a rules file, following CF's naming convention so 143 finds them (D1, D2).
- `scripts/answerer_walkthrough.py setup`, which builds the throwaway registry, checkout, store directory and project config from that tree (D6).
- `docs/answerer-walkthrough.md`: the steps, the PM's answers, and what to check after each case (D6).
- A deterministic test that 143's assembly over the scratch tree finds every plan file and the passages each case depends on (D6).
- Running the four cases live and writing what was observed under the task file (D7).
- Adding every captured question tail to `tests/live/answering/fixtures/question_tails.json` (D8).
- A link to the walkthrough doc from the answerer section of `docs/process-contract.md`.

Excluded:

- Any change to the answerer's code. A defect found in 140–144 is filed as an issue (D7).
- Restart and crash cases. 144's crash tests cover them.
- An implement-step question. All four cases ask at the design step (D1).
- The program scope and the notification bridge (180, 160).

## Dependencies

### Prerequisites

- **144 (answering run)**, and with it 140–143, implemented and merged.
- **A Squadron release with 140's D8 capabilities.** On 20261101 the installed `sq` was 0.24.12. Whether a given release has the capabilities is decided by 140's start-up probe, not by its version number. Until such a release exists, the live tasks carry `BLOCKED:` lines naming the Squadron issue 140 filed. The fixture tree, the setup script, the docs and the deterministic test can be built before that.
- Provider keys for the design agents, in a `.env` file the user supplies (132's walkthrough found Squadron reads the checkout's `.env`).
- Model aliases and a cost cap for the answering run, from 140's live-tier variables `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD`.

### Interfaces Required

- 144's eight-key `answerer` section in `projects.yaml`, and its listings: `amoeba inspect questions` (with `--json`), `inspect blocked` and `inspect journal`.
- 143's `assemble_sources` and its naming-convention lookup of plan files (143, D3), used by the deterministic fixture test.
- 132's `submit intent drive`, `submit resolution --decision resume --instructions`, and per-slice dispatch.
- `amoeba submit create-project` and `submit link-cf-project`. Amoeba's `--cf-data-dir`, and `CONTEXT_FORGE_DATA_DIR` in the environment so the spawned `sq` and `cf` see the throwaway registry.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Scratch project tree | `scripts/answerer_walkthrough/project/` | The files committed as the scratch checkout's first commit |
| Setup script | `scripts/answerer_walkthrough.py` | `setup --dir D --env-file F`: builds the environment and prints the exports and node ids |
| Fixture test | `tests/runner/answering/test_walkthrough_fixture.py` | 143's assembly over the tree finds the plan files and the case passages |
| Walkthrough doc | `docs/answerer-walkthrough.md` | The repeatable steps and the expected record for each case |
| Real-tail fixture | `tests/live/answering/fixtures/question_tails.json` (144) | Gains the walkthrough's tails |

Nothing is added under `src/`.

### Data Flow

```
setup.py --dir D --env-file F
  D/checkout   ← copy of project/, git init, first commit on main, .env copied (gitignored)
  D/cf         ← CONTEXT_FORGE_DATA_DIR=D/cf cf init   (in D/checkout)
  D/store      ← AMOEBA_STORE_DIR
  D/projects.yaml ← pipeline p4 + answerer section (models and cost cap from the live variables)
  amoeba submit create-project / link-cf-project (cf project id read from cf's own output)

per case:  PM drives one slice  →  p4 design step asks (forced by the slice entry, D2)
           →  132: QUESTION, HUMAN block  →  141: record pending
           →  144: sq_answer from D/store/.../answering/<run_id>/  →  decide  →  142: gate
           →  resume with instructions (answered)  |  declined → PM resolution
           →  design rerun with the answer  →  p4 completes  →  slice done
```

### State Management

All state lives under the walkthrough directory `D`: the scratch checkout's git history, the throwaway registry, the Amoeba store (records, journal, answering scratch directories) and the project config. Nothing persists outside `D`. The last walkthrough step checks that the real registry does not list the scratch project (D6).

## Technical Decisions

### D1 — One scratch project, pipeline `p4`, six slices driven one at a time

Status: decided

- PM answers are precedent within one project, so cases 3 and 4 have to run in the same project as the answers they reuse. All four cases share one project.
- The project's pipeline is the built-in `p4`: design a slice, then revise it until the review passes. Every forced question is asked at the design step. The pause, the answer, the resume with instructions and the completed run are the same for `p4` as for `p456`. 132's walkthrough already proved the full `p456` lifecycle against a real slice. A `p456` run would add an implementation and a merge to each of six slices without testing anything more of the answerer.
- "Completes" means the `p4` run completes and Amoeba marks the slice `done`.
- Each slice node is driven on its own, in order, and the next is driven only after the previous slice is `done`. Precedent depends on that order. Only one run is in flight at a time, which the checkout hold requires anyway.
- **Rejected:** `p456`, for its cost and wall time with no added coverage. **Rejected:** one project per case, because precedent does not cross projects.

### D2 — The slice entries make the design agent ask, unless its instructions already answer

Status: decided

- A design agent asks questions on its own judgement, which cannot be relied on. Each scratch slice entry therefore ends with a conditional instruction: *if your instructions do not already say X, write no design and end your reply with one question asking X.* The design agent always reads its slice plan entry, so the instruction reaches it whatever provider runs the step. A rules file may not reach it.
- The condition ends the loop. The rerun after a resume has the answer prepended to its prompt (004-direction), so it writes the design instead of asking again. If an agent asks again anyway, 142's answer limit sends the repeat to the PM.
- The instruction says "asking", never "ask the PM". The entry is itself a passage, and wording that reserves the question for the PM could lead the answer or check step to decline for that reason alone.
- Each question's wording is set by its entry, so cases 3 and 4 get a second question with the same meaning in different words. The agent still writes the actual text, which is why the tails are real (D8).
- **Revised 20261103 after the live run.** The conditional form ("if your instructions do not already say X") fails when the concept, the architecture or the rules already say X: the agent writes a design without asking. Slices 100, 101 and 104 therefore say "Before you design anything, write no design and end your reply with one question asking X; if your prompt already begins with an answer to that question, write the design instead", and slice 105 asks what license header text each new file opens with. The wording must not say that documents do not count: the entry is a passage, and the answerer declined on it.

### D3 — The merge question is grounded in the plan, so the screen is what declines it

Status: decided

- The architecture says slice branches merge to `main` automatically once their review passes. So case 2's question has a grounded answer that the check step can confirm, and the screen is what stops it. That is the screen's job: a fixed net that works after the model has said yes.
- The scratch config's `reserved_terms` is `[push, merge, release, DROP]`. The single word `merge` matches whatever wording the agent uses ("merge into `main`", "merge the branch to main"). A multi-word term would miss a reworded question, and the case would then fail because of the fixture's term list rather than because of the answerer. No other case's question or answer is about merging, pushing or releasing.
- Expected record: `declined`, `decline_reason reserved_term`, `reserved_term merge`, with no `sq_run` resume from the answerer. The PM then answers with a resume.
- If the check step refuses first (`check_said_no`, citing a reserved action), the question still reaches the PM safely, but the case has not shown the screen. D7 says what happens next.

### D4 — Case 4 uses the answer limit to send the exception to the PM

Status: decided

- For a PM answer to stand against an older rule, the PM must have answered a question that the rule already covers. Left alone, the answerer would answer that question from the rule. So slice 104's entry has the design agent ask two questions in order. The first is the storage format, which the concept answers and which uses the run's one answer (`answer_limit: 1`). The second asks whether new source files carry a license header. With the limit reached, 142's gate declines the second question `answer_limit_reached`, whatever the answering run concluded. If the run declines it first, it still reaches the PM. Either way the case does not depend on the model.
- The rule is committed partway through the walkthrough. Before slice 104 is driven, the user appends "Source files carry no license header." to the scratch `CLAUDE.md` and commits it on `main`. The rule's passage then carries that commit's date. The PM's answer to slice 104 ("every new source file starts with the MIT license header; this replaces the rules file for this project") is given after it, so it is the later passage. 143 dates both kinds of passage in UTC to the second (143, D5). The PM answers only after slice 104's design run and an answering run have finished, which takes minutes, so the two dates cannot share a second and there is no tie.
- Slice 105 asks what copyright notice each new file should open with. Expected: answered by the answerer, citing the PM passage. The check says yes because the PM passage is later than the rule. The record's `passage_index` shows both passages, with the rule's date before the PM answer's.
- `answer_limit: 1` holds for every case. Each other case asks one question per run.
- **Rejected:** having the PM resolve a block before the answering stage reaches it. That is a race with the tick and cannot be repeated.

### D5 — The walkthrough configuration

Status: decided

The setup script writes this, failing with the variable's name when one of the three live variables is unset:

```yaml
projects:
  scratch:
    pipeline: p4
    answerer:
      answer_limit: 1                       # D4
      reserved_terms: [push, merge, release, DROP]   # D3
      rules_paths: [CLAUDE.md]
      passages_max_chars: 100000            # the scratch plan is a few thousand characters
      answer_model: ${AMOEBA_LIVE_ANSWER_MODEL}
      check_model: ${AMOEBA_LIVE_CHECK_MODEL}
      max_concurrent_runs: 1                # one slice in flight at a time (D1)
      max_cost_usd: ${AMOEBA_LIVE_MAX_COST_USD}
```

- The `${…}` lines show where the script puts each variable's value. Amoeba's config loader does not expand variables; the file it writes holds literal values.
- The model aliases and the cost cap are the ones 140's and 144's live tiers already use, so there is one place to set them.

### D6 — Repeatable from the repository: tree, script, doc, and one deterministic test

Status: decided

- **Tree.** `scripts/answerer_walkthrough/project/` holds the scratch files at their CF paths (Implementation Details). They are committed in Amoeba's repository, so a later run of the walkthrough uses the same plan and the same forcing wording.
- **Script.** `setup --dir D --env-file F` refuses a `D` that already exists. It copies the tree, runs `git init`, commits on `main` and copies `F` to `D/checkout/.env`, which the tree's `.gitignore` excludes. It runs `cf init` in the checkout with `CONTEXT_FORGE_DATA_DIR=D/cf`, reads the CF project id from `cf get`'s output (stopping with an error if it is not there), and submits `create-project` and `link-cf-project` to `AMOEBA_STORE_DIR=D/store`. It writes `D/projects.yaml` (D5) and prints the `export` lines to run Amoeba against `D`. The script holds no secrets and no model names; the `.env` path and the live variables come from the user.
- **Script failures.** Any subprocess that exits non-zero stops the script. It reports the step, the command and its stderr, and names the partly built `D`, which it never deletes. The user removes `D` before a rerun.
- **Registry isolation.** Isolation comes from the exported `CONTEXT_FORGE_DATA_DIR=D/cf`, which every spawned `cf` and `sq` inherits, and from `--cf-data-dir D/cf`. The script does not inspect the real registry. The doc's last step runs `cf project list` with `CONTEXT_FORGE_DATA_DIR` unset and confirms that the scratch project is not listed.
- **Doc.** `docs/answerer-walkthrough.md` is the only full walkthrough: the commands, each case's PM answer text and the record fields to check. It is updated to what was run in Phase 6. The Verification Walkthrough below only points to it.
- **Fixture test.** Using 143's fixture-repository helper, the test runs `assemble_sources` over the tree for slices 100, 101 and 105. It checks that the concept, initiative plan, architecture and slice plan are all found, that a passage contains "JSON Lines" (case 1) and that a passage contains the automatic-merge rule (case 2). A rename that broke 143's lookup would otherwise surface only as a live decline. The test needs no LLM and no `sq`.
- **Rejected:** a script that also drives the cases. The PM's resolutions and the checks between cases are what the walkthrough demonstrates, and a script would hide them.

### D7 — Each case runs once; a wrong outcome is a recorded finding

Status: decided

- Each case runs once. Its result is written under the task, with the records and journal entries listed in the Verification Walkthrough.
- **Fixture cause.** If a case fails because of the scratch tree's wording, the tree is fixed and that one case is rerun on a fresh slice index. Examples: an agent that did not ask, or a passage that does not state the answer. Both runs are recorded.
- **Product cause.** If a case shows an actual defect in 140–144, one that is broken or high severity and reasonably likely to occur, it is filed as an issue (CLAUDE.md, "Found while implementing a slice") and the case is marked `BLOCKED:` on it. Examples: a wrong reason code, a missed reader, or a confirmed answer with no ground. The slice is not complete until the issue is resolved. A safe outcome that only fails to show the case (a decline, a question not asked) is not a defect: it is recorded in the task's Result and does not block the slice.
- **Model judgement.** Case 2 declined by the check step instead of the screen, or case 3 or 4's reworded question declined (`check_said_no` or `answerer_declined`), is safe but does not meet the case. It is recorded with the record's `decline_detail`. The case is rerun once on a fresh slice index. A second miss is recorded in the Result with both `decline_detail` values and the case is closed as shown in part. No issue is filed and nothing is marked `BLOCKED:`, because the outcome is safe.
- **Environment.** A design run can end without asking: `failed` (provider error, a missing key in the checkout's `.env`, a stall) or `orphaned`. These never reach the answerer. The outcome is recorded, its block is resolved with `stop`, and the case is repeated once on a fresh slice index. A second failure marks the case `BLOCKED:` on the cause. It is not a finding against the answerer.

### D8 — Every captured tail becomes a fixture

Status: decided

- Every `checkpoint.question` the walkthrough produces, including any unplanned question, is copied from `amoeba inspect questions --json` into `tests/live/answering/fixtures/question_tails.json`, with its run id, its capture date and `source: 145-walkthrough`. There are about seven, and taking all of them means nobody has to judge which shapes are new.
- If a tail shows a deterministic defect, the issue filed under D7 includes a stub-tier case built from that tail. Examples: a cut-off flag that is wrong, or a reserved term missed because of markdown around it.

### Technology Choices

- Nothing new. The script is stdlib Python (`subprocess`, `shutil`, `pathlib`), like the other `scripts/` demos, and calls the installed `git`, `cf` and `amoeba`.

### Patterns and Conventions

- The script prints what it created. Where a value comes from another tool's output, the script reads it and stops when it is missing; it never fills one in.
- The scratch tree contains no real project names, credentials or model aliases.

## Implementation Details

### Scratch Project Contents

A tiny command-line notes tool, chosen so the design agent's work stays small. Paths follow `file-naming-conventions.md`, so 143 finds them.

| File | Holds |
| --- | --- |
| `CLAUDE.md` | Two short rules (keep slices small; tests beside code). No rule on storage, dates, merging or headers until D4's commit |
| `project-documents/user/project-guides/000-concept.notes.md` | The tool's purpose. "All notes are stored as JSON Lines files, one note per line" (case 1) |
| `project-documents/user/project-guides/001-initiative-plan.notes.md` | One initiative, 100 |
| `project-documents/user/architecture/100-arch.notes.md` | Components. "Slice branches merge to `main` automatically once their review passes; agents do not need to ask" (case 2) |
| `project-documents/user/architecture/100-slices.notes.md` | Six slice entries, 100–105, each ending with its forcing sentence (below) |
| `.gitignore` | `.env` |

Nothing in the tree says how dates are formatted or whether files carry a license header. Those answers come only from the PM.

Forcing sentences (D2). Each follows the pattern "If your instructions do not already say …, write no design and end your reply with one question asking …":

| Slice | Case | Asks |
| --- | --- | --- |
| 100 Add a note | 1 | which storage format notes are kept in |
| 101 List notes | 2 | whether this slice's branch should merge to `main` once its review passes |
| 102 Show note dates | 3a | which date format user-facing timestamps use |
| 103 Sort by date | 3b | how times shown to the user should be written |
| 104 Export notes | 4a | first which storage format notes are kept in; then whether new source files carry a license header |
| 105 Import notes | 4b | what copyright notice each new file should open with |

## Integration Points

### Provides to Other Slices

- **144's live tier:** the walkthrough's real tails in `question_tails.json` (D8).
- **160 (notification bridge):** a repeatable live setup with real declines (`reserved_term`, `answer_limit_reached`, and the case 3a decline) to check notifications against later.
- **The PM:** `docs/answerer-walkthrough.md`, a demonstration that can be repeated after any change to the answerer or to Squadron.

### Consumes from Other Slices

- **144:** the stage, the eight config keys, the evidence columns and the listings. If a listing's column names differ from those below when 144 lands, the doc uses 144's names.
- **142:** `answer_limit_reached` and `reserved_term` with the matched term.
- **143:** plan lookup by naming convention, and commit dates on passages.
- **141:** the record, the PM-answer rule (a resume with instructions is precedent) and `inspect questions`.
- **140:** the shipped pipeline and its start-up probe. An `sq` without D8 fails the probe at start, before any case runs.

## Success Criteria

### Functional Requirements

- **Case 1.** Slice 100 is resumed by the answerer. The record is `answered`, `answered_by answerer`, `check_verdict yes`, citing a concept passage. The journal shows `sq_run`, `sq_answer`, then the resume with instructions that restate the question. The run completes and the slice is `done`.
- **Case 2.** Slice 101's record is `declined` (by the reserved-term screen or by the answer step; the PM accepts either, #23), and the answerer did not resume it. After the PM's resume with instructions, the run completes and the record is `answered` by the PM.
- **Case 3.** Slice 102 is declined (nothing on file) and answered by the PM. Slice 103's question, in other words, is answered by the answerer, citing the PM passage from slice 102. The run completes.
- **Case 4.** (The PM accepts the last step as not shown live, #24.) After the rule commit, slice 104's second question is declined (`answer_limit_reached`, or a decline by the answering run) and answered by the PM. Slice 105's question is answered by the answerer, citing slice 104's PM passage. `passage_index` shows the rule's date before the PM answer's. The run completes.
- At the end, the real registry does not list the scratch project, and nothing is written outside the walkthrough directory.

### Technical Requirements

- The fixture test passes without `sq` or a model.
- The setup script refuses an existing directory and a missing live variable, each with a message naming it. It stops when the CF project id is absent from `cf`'s output, and on any non-zero subprocess exit, reporting the step and leaving `D` in place.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass on the script and the test. The existing suites pass.

### Integration Requirements

- `docs/answerer-walkthrough.md` holds the steps as run, and `docs/process-contract.md`'s answerer section links it.
- Every captured tail is in `question_tails.json` with its run id and date, and 144's live tier still collects.
- Any defect found is an open issue, linked from the task notes.

### Verification Walkthrough

Run on 20261103 with squadron 0.24.16. The full walkthrough, with each case's commands, PM answers, records to check and what was observed, is `docs/answerer-walkthrough.md` (D6). The expected outcomes are the Success Criteria above.

1. **Fixture test.** Needs neither `sq` nor a model. `uv run pytest tests/runner/answering/test_walkthrough_fixture.py -v` passes (3 cases).
2. **Set up and start.** Needs a Squadron release with 140's D8, provider keys and the three live variables. Run `uv run python scripts/answerer_walkthrough.py setup --dir <D> --env-file <path to your .env>`, run the `export` lines it prints, export the keys in the shell that starts Amoeba, then `amoeba start --project-config <D>/projects.yaml --cf-data-dir <D>/cf`. The start-up log shows the `sq` probe and the answering-pipeline probe passing. Observed: both passed, and `amoeba inspect nodes --project scratch --json` lists initiative 100 and slices 100 to 105.
3. **The cases.** Follow `docs/answerer-walkthrough.md` from its first case. Observed: case 1 and case 3 as expected; case 2 declined by the answer step, not the screen (#23); case 4's first half as expected and its last step not shown (#24).

**Corrections found live:** the setup script also registers the concept, architecture and plan with Context Forge (`cf set`) and installs the project guide (`cf init --no-ide`), which `sq`'s design step needs. A slice is ready only when the next-lower index is `done`, so a rerun slice goes at the end of the plan. A forcing sentence must not say documents do not count (the answerer reads it as a passage).

## Implementation Notes

### Development Approach

1. The scratch tree and the fixture test. These need no Squadron.
2. The setup script, and step 2 run up to `amoeba start`. Without a D8 release, the start-up probe fails; record that.
3. The doc draft.
4. Step 3 live. These tasks carry `BLOCKED:` lines on 140's Squadron issue until a D8 release is installed.
5. The captured tails into `question_tails.json`, the issues for any findings, and the doc updated to what was run.

Relative effort: 2.

### Special Considerations

- **Spend.** Six `p4` runs and about seven answering runs, each answering run capped by `max_cost_usd`. A `p4` review loop that never passes ends in a `paused` checkpoint block, which is not a question. The PM resolves it with `resume` or `stop`, and the result is recorded under the task.
- **Unplanned questions.** A design agent may ask something no entry forced. It goes through the answerer like any question. Its outcome is recorded, its tail is captured (D8), and the PM answers it if it is declined.
- **Secrets.** The `.env` is copied into the scratch checkout, ignored by git, and never committed or printed.
