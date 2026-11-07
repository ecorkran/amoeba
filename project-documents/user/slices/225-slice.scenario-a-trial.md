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
---

# Slice Design: Scenario A Trial

## Overview

Switch Amoeba on for real work in the PM's own repos, let real runs pause, and count from `decisions` and `status` the share of questions answered without the PM. Wrong answers, false screen matches and questions that should have been answered are recorded with what would have fixed them. The result is a short note with the numbers and a verdict: go on to 227, or rethink the design.

This is a trial, not a build. The only code is the answering run's opt-out flag and the hook config line (amoeba#35, deferred here by 223), plus fixtures and fixes for real shapes the tests missed. Answering spend is not measured (amoeba#38).

## Scope

**Included:** registration and install (D1, D2), the opt-out flag and hook line (D3), the trial and its ledger (D5, D6), the verdict (D7), fixtures for real shapes (D9), and the note `user/analysis/220-analysis.scenario-a-trial.md` with the verdict recorded in the plans (D10).

**Excluded:** the call log (D4, amoeba#34), closing waiting questions whose run moved on (amoeba#36; the note says whether the trial shows a need), the `wrong_checkout` skip (amoeba#37, waits on `ecorkran/squadron#303`), scenario B, MCP (226).

## Dependencies

- **Slices 223 and 224 merged:** `handle_pause`, `answer`, `status`, `decisions` and `mark_read` work on the CLI.
- **`ecorkran/squadron#302`** (command started on pause, with a per-run opt-out). Without it nothing starts `handle_pause` and there is no trial. If it hasn't landed when implementation reaches D3, that task gets a `BLOCKED:` line.
- **`ecorkran/squadron#303`**, which 224 needs for `status` to show missed hooks.
- **`ecorkran/squadron#299`, not blocking.** Until it lands, the answer and check models are non-Claude aliases, as in 223.

## Technical Decisions

### D1 — Programs and members
Status: decided

| Program | Members | Concept |
|---|---|---|
| `trading` | `trading-data`, `trading-engine`, `trading-ui` | `trading-data`: `project-documents/user/project-guides/000-concept.trading.md` |

Trading is the multi-repo program the design exists for, and all three repos are active with a `CLAUDE.md`. `trading-api` is left out (no rules file, no commits). Amoeba is not a member, so the trial never counts questions about its own fixes. Each member's `rules_paths` is `[CLAUDE.md]` and the default authorize list holds. Registration is one `amoeba set_up` call (Walkthrough step 2).

### D2 — Install and config
Status: decided

- **Install:** `uv tool install --force <amoeba repo>` from the slice branch, not editable, so branch switches don't change the running tool. Reinstall after each D9 fix, only when `pgrep -f "amoeba handle_pause"` finds nothing. A pause whose hook fires during a reinstall is an ordinary missed hook, caught up at the next review pass (D6). Each ledger row notes the commit installed when its pause was handled.
- **Config:** `~/.config/amoeba/config.yaml` from the example in `docs/config-contract.md`. The values used are copied into the note.
- **Environment:** the hook's environment must reach `sq`, `cf`, `git`, `amoeba` and the model credentials. The sanity pass (Walkthrough step 4) proves it before anything counts.

### D3 — Hook line and the answering run's opt-out (amoeba#35)
Status: decided

`operations/answering_run.py` defines `PAUSE_COMMAND_OPT_OUT_FLAG` once, in #302's shipped form, and adds it to the answering run's `sq run` command, with a unit test. The `answering_run` skip in `handle_pause` stays as the store-side check. `docs/squadron-hook.md` gets the exact config line and how a watching PM passes the opt-out. If #302 ships a user-level setting it is configured once, and pauses outside the members skip as `not_a_project` or `not_in_program`; if per-project, it is configured in each D1 member. Closes amoeba#35.

### D4 — No call log
Status: decided

The call log (amoeba#34) is not built: the share does not need it, because a hook call that wrote no row leaves its pause visible in `status` as a missed hook, which counts against the share, and the catch-up call run from a terminal shows any error. A missed question whose cause the catch-up doesn't show is recorded as `cause unknown`, never guessed. amoeba#34 stays open.

### D5 — Trial window and stopping rule
Status: decided

- **Start:** `trial_start`, the UTC time of the first run after the sanity pass, recorded in the note.
- **Stop:** the first review pass at which the ledger holds at least 20 counted questions from at least two members. Below 20, one question moves the share by more than five points.
- **Counted question:** an agent question from an in-process run in a D1 member, paused after `trial_start`. Questions a watching PM handled first (opt-out run, PM answered or resumed outside Amoeba) are listed as excluded and left out of the count. Amoeba's own answering runs are not counted.
- Amoeba stays on after the trial.

### D6 — Review passes and the ledger
Status: decided

After each working session, an agent runs `amoeba decisions --since <trial_start>` and `amoeba status` from outside every member.

**Catch-up:** every run `status` lists as `unhandled`, `claim_stale` or `answered_unresumed` is passed to `handle_pause` from its listed directory, and its question is counted by that call's outcome.

The note holds one row per question, keyed on `(run_id, paused_at)`, recording: answered without the PM or not (an automatic answer that was resumed and not overridden or judged wrong); for the rest, the `waiting_reason` or why Amoeba missed it; anything that went wrong (a wrong answer, a false screen match, a question that should have been answered); and one line on what would have fixed it (a rule line, a passage, a prompt change, a code fix). A PM override is always a wrong answer. The PM can change any row.

### D7 — Verdict
Status: decided

**Go** when more than half of the counted questions were answered without the PM, **rethink** otherwise. Wrong answers are recorded with their fix, not used as a second test. An automatic answer that authorized an item on its member's not-authorized list gets an issue against 223's check and screen, whatever the verdict.

### D8 — What may change during the trial
Status: decided

Member rules files, authorize-list changes through `set_up`, and D9 fixes may change; the ledger notes the commit. Nothing that changes what an answer says (prompts, passage assembly, the screen's phrase list, models, limits, including a mid-trial #299) changes until after the verdict, or the trial measures a moving system. Such changes are recorded as proposed fixes.

### D9 — Real shapes become fixtures
Status: decided

A crash, parse failure or unreadable input met in a real run (`handle_pause` exit 3, `RunFileProblem`, `PollFailure`, `sources_missing`, `sources_unreadable`) gets its raw output (secrets redacted) as a fixture under `tests/fixtures/`, a test that fails for the reported reason, a fix committed on the slice branch, and a reinstall (D2). A D9 fix only lets the existing path run; anything touching answer content falls under D8.

### D10 — Recording the verdict
Status: decided

- **The note** (docType `analysis`) holds the setup, `trial_start` and stop pass, the ledger, the counts (answered without the PM, waiting by reason, wrong answers, false screen matches, should-have-answered), the verdict, proposed fixes, and whether amoeba#36 is needed. The tally is a `jq` recipe over the CLI's JSON, kept in the note's appendix.
- **Go:** the initiative plan's 220 entry gains one line with the share and a link to the note.
- **Rethink:** the 227 slice plan entry and the initiative plan's 220 entry gain `Status: on hold, scenario A trial verdict: rethink (see note)`, and the note lists the design questions the numbers raise.

## Success Criteria

- The three D1 members are registered, and a pause in each starts `handle_pause` through the hook.
- Real work runs in at least two members, and the ledger holds at least 20 counted questions from at least two members, with every question in `decisions` and every missed hook in `status` after `trial_start` accounted for.
- The note gives the D10 counts with proposed fixes, and states go or rethink; the plans reflect it.
- The answering run's command carries the opt-out flag (unit-tested). Each D9 shape has a fixture and a test that failed before its fix. Format, lint, typecheck and tests pass after each fix. amoeba#35 is closed.

## Verification Walkthrough

Draft. Needs 223 and 224 merged and Squadron with #302 and #303.

1. **Checks and install**, on the slice branch after the D3 commit:
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   uv tool install --force .
   which amoeba
   ```
2. **Config and members.** Write `~/.config/amoeba/config.yaml`. Then, from `trading-data`:
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
   Expect `applied`; a repeat gives `unchanged`.
3. **Hook.** Add the config line from `docs/squadron-hook.md` to Squadron's config.
4. **Sanity pass, not counted.** In `trading-data`, run 223's live fixture pipeline (`<amoeba repo>/tests/live/pause/`) and leave it to pause. With no command typed, expect `decisions` to show an `answerer` record with `resume.outcome: resumed`, or `status` to list it under `waiting_on_pm`, and no question record for the answering run's id. A pause in the amoeba repo leaves nothing in the store.
5. **Trial.** Record `trial_start`. The PM works as normal. Review passes per D6.
6. **Stop and verdict.** At the D5 stop, run the tally, check the counts add up to the ledger's rows, and record the verdict (D7, D10).

## Risks

- **Wrong answers in real repos.** The default not-authorized list holds, so no answer can authorize a push, a merge to main, a release, a destructive database statement or a policy change, and every answer is read at each review pass.
- **Too few questions.** The stop rule counts questions, not time; 226 can proceed alongside.
- **The real store.** First use of `~/.config/amoeba/`. Tests keep using `AMOEBA_HOME`, and nothing destructive runs against the real store.
