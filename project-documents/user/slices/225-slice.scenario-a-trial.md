---
docType: slice-design
slice: scenario-a-trial
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 223-slice.pause-handling
- 224-slice.status-and-decisions
interfaces:
- 227-slice.program-dependencies
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
turns: 22
promptTokens: 1606246
cachedTokens: 1505715
cacheWriteTokens: 100489
completionTokens: 22307
durationSeconds: 251.7
costUsd: 1.551697
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.5516969000000003
    completionTokens: 22307
---

# Slice Design: Scenario A Trial

## Overview

This slice switches Amoeba on for real work in the PM's own repos and measures scenario A. The Squadron hook starts `handle_pause` on every pause. Real runs pause on real questions. The share of questions answered without the PM is counted from `decisions` and `status`. Wrong answers, false screen matches and questions that should have been answered are each recorded with what would have fixed them. The result is a note with the numbers and a verdict: go on to 227, or rethink the design.

Little code is written. Three things are added so the trial can run and be counted:

- Squadron's pause-command opt-out on Amoeba's answering run, and the exact hook config line (amoeba#35, assigned here by 223).
- A log line for each `handle_pause` call that writes no question record (amoeba#34), so a hook call that failed or skipped leaves a trace. A hook has no terminal.
- A fixture and a fix for any real shape the tests didn't cover.

## Value

Verification. Before scenario B is built, it decides whether Amoeba takes most real questions off the PM's plate. Answering spend isn't measured here (amoeba#38). The architecture makes this the test of the whole design: if most real questions still reach the PM, the design is rethought and 227 is not built.

## Technical Scope

**Included:**

- Registering the trial programs and members in the real store (D1), and installing and configuring Amoeba for real use (D2).
- The hook config line and the answering run's opt-out flag (D3, amoeba#35).
- The `handle_pause` call log (D4, amoeba#34).
- The trial: the stopping rule (D5), a ledger that classifies every question (D6), and the verdict rule (D7).
- Fixtures and fixes for shapes met in real runs (D9).
- The note `user/analysis/220-analysis.scenario-a-trial.md`, and the verdict recorded in the initiative plan and the slice plan (D10).

**Excluded:**

- Changes to the answering prompts, passages or screen during the trial. They are recorded as proposed fixes and made after the verdict (D8).
- Closing waiting questions whose run moved on (amoeba#36) and the `wrong_checkout` skip (amoeba#37). The note records whether the trial shows a need for #36. #37 waits on `ecorkran/squadron#303`.
- Scenario B rule lines, MCP (226) and any spend cap per time window.

## Dependencies

### Prerequisites

- **Slices 223 and 224 merged.** `handle_pause`, `answer`, `status`, `decisions` and `mark_read` work on the CLI.
- **`ecorkran/squadron#302` landed** (command started on pause, with a per-run opt-out). Without it nothing starts `handle_pause`, and there is no trial. If it hasn't landed when implementation reaches D3, that task gets a `BLOCKED:` line.
- **`ecorkran/squadron#303` landed.** 224 is not complete without it, and `status` needs it to show missed hooks.
- **`ecorkran/squadron#299`, not blocking.** Until it lands, the config names non-Claude models for the answer and check steps, as in 223.

### Interfaces Required

- **223:** `handle_pause` and its `HandlePauseResult` (outcome, `skip_reason`, `waiting_reason`, question key, `answering_run_id`), `docs/squadron-hook.md`, `operations/answering_run.py` where the answering command is built, and `config/home.py`'s `logs_dir()`.
- **224:** `decisions --since` with each record's `answered_by`, `prior_answer_seq`, `based_on` and `resume`; `status` with `waiting_on_pm` (`waiting_reason`, `run_state`) and each run's `pause` class (`unhandled`, `claim_stale`, `answered_unresumed`).
- **222:** `set_up`, the config file and the real store at `~/.config/amoeba/`.

## Architecture

### Component Structure

```
src/amoeba/
├── operations/answering_run.py   # + PAUSE_COMMAND_OPT_OUT_FLAG on the answering run (D3)
├── cli/main.py                   # + a call-log line for each handle_pause call that writes no row (D4)
├── cli/call_log.py               # append_call_line(): the one writer of the log (D4)
└── config/home.py                # + CALL_LOG_FILE under logs_dir() (D4)
docs/squadron-hook.md             # + the exact hook config line (D3)
tests/fixtures/…                  # + shapes met in real runs (D9)
project-documents/user/analysis/220-analysis.scenario-a-trial.md   # ledger, numbers, verdict
```

### Data Flow

1. A run in a member pauses. Squadron starts `amoeba handle_pause <run_id>` in the run's directory (#302).
2. `handle_pause` answers and resumes, records the question as waiting on the PM, or skips. On a skip or an exit 3, the CLI appends one line to the call log (D4).
3. The PM answers waiting questions through an agent (`amoeba answer`). The PM marks read with `mark_read` as normal use. The trial doesn't depend on the marker, because it counts from a fixed start time.
4. At each review pass (D6), an agent in the amoeba repo runs `amoeba decisions --since <trial start>`, `amoeba status` from outside every member, and reads the call log. It adds each new question to the ledger in the note and classifies it.
5. When the stopping rule is met (D5), the agent computes the numbers, applies the verdict rule (D7), and records the verdict (D10).

### State Management

- **Real store** at `~/.config/amoeba/amoeba.sqlite3`: the trial's question and answer records. The trial reads it only through the CLI. No test and no tally writes to it.
- **Call log** at `~/.config/amoeba/logs/handle_pause.jsonl`: one JSON line per call that writes no row (D4).
- **The note:** the ledger and the results. It is the only trial state kept in the repo.

## Technical Decisions

### D1 — Programs and members
Status: decided

One program, three members, all of them repos the PM works in now:

| Program | Members | Concept |
|---|---|---|
| `trading` | `trading-data`, `trading-engine`, `trading-ui` | `trading-data`: `project-documents/user/project-guides/000-concept.trading.md` |

- **Why trading.** It is the multi-repo program the design exists for, and its program concept exercises the program passages. Each of the three repos has `CLAUDE.md` and `AGENTS.md`, and all have commits within the last week. Three members cover the plan's two.
- **Amoeba is not a member.** The trial's own work (D9 fixes, review passes) happens in the amoeba repo. If it were a member, the trial would count questions about itself.
- `trading-api` is left out. Context Forge lists it, but the checkout has no rules file and no commits.
- Each member's `rules_paths` is `[CLAUDE.md]`. No member changes its authorize list at the start. The defaults hold until the PM allows an item, which is normal use and is noted in the ledger.
- Registration is one `amoeba set_up` call, run from a member's checkout. The request document is kept in the note's appendix.

### D2 — Installation and configuration for real use
Status: decided

- **Install.** `uv tool install --force <amoeba repo>`, run from the slice branch after the D3 and D4 code is committed. The install is not editable, so switching branches in the amoeba repo doesn't change the running tool. It is reinstalled after each D9 fix, and each reinstall is noted in the ledger with its commit. A reinstall runs only when `pgrep -f "amoeba handle_pause"` finds no process. Only `handle_pause` runs from the tool directory. Answering runs and resumes are `sq` processes, and a reinstall doesn't touch them. A pause whose hook fires during a reinstall is an ordinary missed hook, and the review pass catches it up (D6).
- **Config.** `~/.config/amoeba/config.yaml`, copied from the example in `docs/config-contract.md`. The values used (models, `max_cost_usd`, `answer_limit`, `answering_wait_seconds`, `resume_wait_seconds`, the default authorize list) are copied into the note. Until #299 lands, the answer and check models are non-Claude aliases.
- **Environment.** The hook's environment must reach `sq`, `cf`, `git`, `amoeba` and the model credentials (`docs/squadron-hook.md`). The first sanity pass (Verification Walkthrough step 4) proves this before real runs count.

### D3 — The hook line and the answering run's opt-out (amoeba#35)
Status: decided

- `operations/answering_run.py` defines `PAUSE_COMMAND_OPT_OUT_FLAG` once, in the form #302 ships, and adds it to the answering run's `sq run` command. A unit test checks that the built command contains it. The `answering_run` skip in `handle_pause` stays as the store-side check.
- `docs/squadron-hook.md` gives the exact config line in #302's form, and how a person watching a run passes the opt-out. #302 doesn't promise to record the opt-out anywhere a reader can see it afterward. This task checks whether the shipped version does, and writes where it is recorded, or that it isn't, into the doc (D6).
- **Where it is configured.** #302 proposes a user-level setting. If it ships that way, it is configured once in the PM's Squadron config. Every pause on the machine then starts `handle_pause`, and pauses outside the members are skipped as `not_a_project` or `not_in_program` and leave only a call-log line. If #302 ships a per-project setting, it is configured in each D1 member and nowhere else.
- Closes amoeba#35.

### D4 — The `handle_pause` call log (amoeba#34)
Status: decided

- As amoeba#34 proposed, the CLI appends one JSON line for each `handle_pause` call that writes no question row: an outcome of `skipped`, or exit 3. The file is `logs_dir() / CALL_LOG_FILE`, where `CALL_LOG_FILE = "handle_pause.jsonl"` is defined in `config/home.py`. Each line holds `at` (UTC), `run_id`, `cwd`, `exit_code`, and either `skip_reason` with its detail, or `error` (exception name and message). Calls that write a row are already in `decisions` and `status`, so they are not logged again.
- **Why now, ahead of 223's "until 225 shows the need".** `status` shows that a member's paused question run has no record, but not why. Without a terminal, a hook call that failed with exit 3 leaves its error nowhere. A `missed` ledger row (D6) needs that cause to name its fix, and the cause can't be recovered after the trial. A redirect in the hook line itself would depend on #302 running the command through a shell, which #302 doesn't promise.
- `cli/call_log.py` holds the one writer. It is called at the CLI boundary, because only the process boundary sees both the result and an exit-3 error, and the operation itself stays unchanged. 226 starts `handle_pause` as a detached CLI process, never in-process, so those calls are logged too. So the log records completed calls only. A call killed partway (machine asleep, session killed) leaves no line. `status` still shows its pause as `unhandled` or `claim_stale` (D6).
- Each line is written with one append to a file opened in append mode. Short lines from simultaneous calls don't interleave.
- **A failed append** (an `OSError`) prints `warning: call log not written: <reason>` on stderr and keeps the call's own exit code. The call's real work has already happened, and exit 3 would misreport it. This is the one handled exception, with a comment saying why.
- Nothing prunes the log, the same as 223's logs.
- Closes amoeba#34.

### D5 — Trial window and stopping rule
Status: decided

- **Start.** The UTC time of the first counted run, after the sanity pass, is recorded in the note as `trial_start`. Everything before it is excluded.
- **Stop.** The trial ends at the first review pass where the ledger holds at least 20 counted questions, from at least two members. With fewer than 20, one question moves the share by more than five points, which is too much for a majority call.
- **Counted question.** An agent question from an in-process (`sdk`) run in a D1 member, paused after `trial_start`, that Amoeba could have answered first. Scenario A is the unattended run, so questions a watching PM handled are kept in the ledger as `excluded` and left out of the count (D6). Amoeba's answering runs, prompt-only runs and other checkpoint kinds are not counted either. They are listed in the ledger only when something went wrong with them.
- Amoeba stays on after the trial ends. The trial closes the count. It doesn't switch anything off.

### D6 — The ledger: classifying every question
Status: decided

The note holds one ledger row per counted question, keyed on `(run_id, paused_at)`. A review pass runs after each working session in which members ran pipelines. It adds rows from three sources, which together leave no question out:

- `decisions --since <trial_start>`: every answered question. Several answers to one question are one row.
- `status`, from outside every member: questions still `waiting_on_pm`, and paused question runs that are `unhandled`, `claim_stale` or `answered_unresumed`.
- The call log: every hook call that wrote no row, including exit 3 and skips that mean something went wrong (`other_member`, `already_claimed` with no claimant).

**Catch-up.** The review pass passes every `unhandled`, `claim_stale` and `answered_unresumed` run to `handle_pause`, following its `next` entry from `status`. This is 224's catch-up, which the architecture gives agents for missed hooks. The row is then classed by that call's outcome. A pause caught up this way is classed like any other, and the ledger notes the catch-up and the cause the call log gives.

Each row gets exactly one class:

| Class | When | In the count | Answered without the PM |
|---|---|---|---|
| `auto_right` | The question's answer is automatic, it was resumed, and it was not judged wrong | yes | yes |
| `auto_wrong` | An automatic answer the PM overrode (`pm` answer with a `prior_answer_seq` of an `answerer` answer), or one the review pass judged wrong from the run's later output or the PM's word | yes | no |
| `waiting` | Sent to the PM, by `waiting_reason`: answered later by the PM, or still waiting | yes | no |
| `missed` | Amoeba delivered no answer, and catch-up couldn't fix it: the run left the pause before a question row existed, a catch-up call failed, Amoeba skipped the pause wrongly, or an automatic answer was still not resumed at the stop pass | yes | no |
| `excluded` | A watching PM handled the question, with the reason: the run was started with #302's opt-out, the PM answered while Amoeba's claim was live, or the PM resumed the run outside Amoeba (`not_delivered`) | no | — |

If Squadron records the opt-out (D3), the review pass reads it there. If it doesn't, member runs don't use the opt-out during the trial, and the note says so. A watched run is then answered and resumed like any other, which the architecture already accepts ("Taking over a watched run"). `excluded` rows say nothing about whether Amoeba can answer, so they are reported as a count and left out of the share.

A `missed` row whose cause the call log doesn't show (no line, or the log couldn't be written) is recorded as `cause unknown`. The cause is never guessed.

Each row also records, where it applies:

- **What went wrong:** a wrong answer, a false screen match (`reserved_term` where the PM's own answer would have passed), or a question that should have been answered (the PM's answer follows from the member's rules, the concept or an earlier PM answer).
- **What would have fixed it:** one of `rule_line`, `passage`, `prompt`, `screen`, `code`, with one line of detail. A `code` fix links its D9 fixture.

`auto_wrong` is judged by the agent doing the review pass, from the record and the run's later output. A PM override is always `auto_wrong`. The PM can reclassify any row, and the note keeps the change.

### D7 — The verdict rule
Status: decided

The architecture's test decides the verdict on its own. It is **go** when `auto_right` is more than half of the counted questions, and **rethink** otherwise ("if most still wait on the PM, the design is rethought").

Wrong answers are recorded with their fix (D6), not used as a second test. An automatic answer that authorized an item on its member's not-authorized list is filed as an issue against 223's check and screen (D10). It doesn't gate 227, which doesn't use the answering code.

### D8 — What may change during the trial
Status: decided

- **May change:** member rules files. Writing a standing call into a repo's rules is how the architecture expects the share to rise, so it is normal use. The ledger notes the commit, and later rows can show the effect. Also: authorize-list changes through `set_up`, and D9 fixes for crashes and parse failures.
- **Does not change:** the answering prompts, passage assembly, the screen's phrase list, the config's models and limits. This holds if `ecorkran/squadron#299` lands mid-trial: the models change to Claude only after the verdict. A proposed change is recorded as a fix and made after the verdict. Otherwise the trial measures a moving system and the numbers mean nothing.

### D9 — Shapes met in real runs become fixtures
Status: decided

- A real shape the tests didn't cover is a case where no answer was produced because of a crash, a parse failure or unreadable input: any `handle_pause` exit 3, a `RunFileProblem`, a `PollFailure` on real output, or a `sources_missing` or `sources_unreadable` on a real plan. A D9 fix only lets the existing path run. Anything that would change what an answer says (prompts, passage selection, the screen) is a proposed fix under D8, even when the trigger is one of these.
- For each one, the raw output (redacted only of secrets) goes into the matching `tests/fixtures/` directory, with a test that fails for the reported reason. Then the code is fixed and the tool reinstalled (D2).
- Rows before and after a fix are pooled. Each ledger row notes the commit installed when its pause was handled, so the rows a fix affected can be read off.
- These are bugs in 222 to 224 code met while implementing this slice. A fix that the trial needs to continue is made in this slice, committed on the slice branch. Anything else becomes an issue only if it is actually broken, per the project's fix rules.

### D10 — Recording the verdict
Status: decided

- **The note** `user/analysis/220-analysis.scenario-a-trial.md` (docType `analysis`, initiative index 220, as the naming conventions prefer) holds: the setup (D1, D2), `trial_start` and the stop pass, the ledger, the counts per class and per `waiting_reason`, the D7 verdict, the list of proposed fixes grouped by kind, and whether amoeba#36 is needed (how many `moved_on` and `not_listed` waiting rows built up). Answering spend is deferred to amoeba#38.
- **Go:** the 227 entry in the slice plan is unchanged, and the initiative plan's 220 entry gains one line: scenario A passed, with the share and a link to the note.
- **Barred items:** whatever the verdict, each automatic answer that authorized an item on its member's not-authorized list gets one issue against 223's check and screen, named in the note.
- **Rethink:** the 227 entry gains `Status: on hold, scenario A trial verdict: rethink (see note)`, the initiative plan's 220 entry says the same, and the note lists the design questions the numbers raise. Rethinking the design is new planning work outside this slice.

### Technology Choices

No new packages. The tally is a `jq` recipe over the JSON from `decisions`, `status` and the call log. It is kept in the note's appendix, written against the real output, so the counts can be rerun. Nothing in `src` computes trial numbers, because the trial runs once.

### Patterns and Conventions

- `PAUSE_COMMAND_OPT_OUT_FLAG` and `CALL_LOG_FILE` are each defined once.
- The call log has one writer, at the CLI boundary, like the CLI's other process-boundary handling.
- Ledger class names and fix kinds are defined once, in the note's header, and used in every row.

## Implementation Details

### API Contracts

No new operation and no change to any result model. The call log's line format (D4) goes in `docs/squadron-hook.md`, beside the hook line, since that is where a person debugging a hook looks.

## Integration Points

### Provides to Other Slices

- **227:** the go or rethink verdict that gates it.
- **226:** the call log covers the detached CLI calls MCP starts, with no MCP change.
- **Future work:** the proposed fixes list, and evidence for or against amoeba#36.

### Consumes from Other Slices

- **223 and 224:** the operations as built. A failure met in real use is handled by D9.
- **Squadron #302:** the hook. If its form differs from the proposal, only D3's flag constant and the doc line change.

## Success Criteria

### Functional Requirements

- The three D1 members are registered in the real store, and a pause in each starts `handle_pause` through the hook.
- Real work runs in at least two members, and the ledger holds at least 20 counted questions from at least two members.
- Every counted question has one ledger class. Every question row in the store after `trial_start`, every missed hook `status` showed, and every call-log line with exit 3 is in the ledger.
- The note gives answered without the PM, waiting on the PM by reason, wrong answers, false screen matches, and questions that should have been answered, each with its proposed fix.
- The note states go or rethink by D7's rule, and the initiative plan and slice plan reflect it (D10).

### Technical Requirements

- The answering run's command carries the opt-out flag, and a unit test checks it.
- A skipped `handle_pause` call and one that exits 3 each append one call-log line, a call that writes a row appends none, and a failed append doesn't change the exit code. All three are unit-tested with a temporary `AMOEBA_HOME`.
- Each D9 shape has a recorded fixture and a test that failed before its fix.
- Format, lint, typecheck and the default test suite pass after each fix.
- amoeba#34 and amoeba#35 are closed by their commits.

### Integration Requirements

- 227 can start, or is held, on the recorded verdict.

### Verification Walkthrough

Draft. It needs 223 and 224 merged, and Squadron with #302 and #303.

1. **Checks and install.** On the slice branch, after the D3 and D4 commits:
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   uv tool install --force .
   which amoeba
   ```
   Expect all checks to pass, and `amoeba` on the `PATH` from uv's tool directory.

2. **Config and members.** Write `~/.config/amoeba/config.yaml` from the example in `docs/config-contract.md`. Then, from `trading-data`:
   ```bash
   amoeba set_up --file - <<'EOF'
   program: trading
   concept:
     member: trading-data
     path: project-documents/user/project-guides/000-concept.trading.md
   members:
     - project: trading-data
       rules_paths: [CLAUDE.md]
     - project: trading-engine
       rules_paths: [CLAUDE.md]
     - project: trading-ui
       rules_paths: [CLAUDE.md]
   EOF
   ```
   Expect `applied`. A repeat gives `unchanged`.

3. **Hook.** Add the config line from `docs/squadron-hook.md` to Squadron's config. The exact line exists only once #302 has shipped.

4. **Sanity pass, not counted.** In `trading-data`, run 223's live fixture pipeline (`<amoeba repo>/tests/live/pause/`) with `sq run` and leave it to pause. Expect, with no command typed:
   - `amoeba decisions --since <time before the run>` shows one `answerer` record for that run id with `resume.outcome: resumed`. Or, if trading-data's rules don't settle the fixture's question, `amoeba status` lists it under `waiting_on_pm`. Either one shows the hook and its environment work. The call log has no line for that run.
   - The answering run's own pause, if any, is not handled: its call-log line is `skipped` with `answering_run`, or there is no line, because the opt-out flag was passed.
   Then, in the amoeba repo, which is in no program, run any pipeline until it pauses. Expect a call-log line with `not_in_program` or `not_a_project` and nothing in the store.

5. **Start the trial.** Record `trial_start` in the note. The PM works as normal in the members.

6. **Review pass**, after each working session:
   ```bash
   amoeba decisions --since <trial_start>
   cd /tmp && amoeba status
   jq -c 'select(.at >= "<trial_start>")' ~/.config/amoeba/logs/handle_pause.jsonl
   ```
   Pass each run whose `next` names `handle_pause` to it from the listed directory. Then add each new question to the ledger with its class (D6). A `waiting` question is shown to the PM, who answers through `amoeba answer`. A D9 shape gets its fixture and fix.

7. **Stop and verdict.** At the first pass with 20 counted questions from two members, run the appendix's tally recipe. Expect counts that add up to the ledger's row count. Apply D7, write the verdict, and update the plans (D10).

## Risk Assessment

### Technical Risks

- **Wrong answers in real repos.** A wrong automatic answer goes into every dispatch of a real resumed run.
- **Too few questions.** The members may not ask 20 agent questions soon. Then the trial waits, and 226 can go ahead beside it.

### Mitigation Strategies

- The default not-authorized list holds for every member at the start, so no answer can authorize a push, a merge to main, a release, a destructive database statement or a policy change. Every answer is in `decisions`, and each review pass reads them.
- The stopping rule counts questions, not time, so a slow trial is still a valid one. Nothing else in the plan waits on it apart from 227.

## Implementation Notes

### Development Approach

1. D3: the opt-out flag and the hook line, once #302 has shipped. Test, commit.
2. D4: the call log and its tests. Commit.
3. D1 and D2: install, config, registration. Verification Walkthrough steps 1 to 4. Start the note, with the setup and the sanity results.
4. The trial: review passes (D6), with D9 fixes committed as they come up.
5. The tally, the verdict and the plan updates (D7, D10). Commit the note.

Effort: 2/5. The code is small. Most of the slice is waiting for real runs and classifying them.

### Special Considerations

- **The real store.** This is the first use of `~/.config/amoeba/`. Tests keep using `AMOEBA_HOME`. No destructive statement is run against the real store. If the trial needs a fresh start, the PM decides.
- **Answer text in the note.** Questions and answers from the PM's repos go into the note as written. They come from the PM's own runs, and the note is in the PM's own repo.
