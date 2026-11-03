---
docType: reference
project: amoeba
slice: live-walkthrough
dateCreated: 20261103
dateUpdated: 20261103
status: in_progress
---
# Answerer walkthrough

## Purpose

Run the question answerer against real Squadron runs, on a throwaway project, and see
what it does: the records, the journal entries and the resumed runs. Four cases:

1. A question the plan answers is answered by the answerer.
2. A question about merging is declined by the reserved-term screen, and the PM answers.
3. A PM answer is reused when the question comes back in other words.
4. A newer PM answer stands against an older rule.

Everything lives under one directory `D`. The real Context Forge registry is never
written. Repeat this after any change to the answerer or to Squadron.

**Results.** The expected records below are what the design says should happen. The
"Observed" lines are filled in from the run recorded in
`project-documents/user/tasks/145-tasks.live-walkthrough.md`; until a case shows one,
it has not been recorded here.

## Prerequisites

- A Squadron release whose `sq` passes Amoeba's start-up probes. The probes decide;
  a version number does not.
- Provider keys for the design agents in a `.env` file (any path; it is copied into the
  scratch checkout and never committed).
- Three variables in your shell, the same ones 140's live tier uses:
  `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL`, `AMOEBA_LIVE_MAX_COST_USD`
  (a number above zero).
- `cf`, `git` and `amoeba` on `PATH` (`uv run` from the repository root does this for
  `amoeba`).

## Set up and start

```
uv run python scripts/answerer_walkthrough.py setup --dir D --env-file /path/to/.env
```

`D` must not exist. The script prints two `export` lines and an `amoeba start`
command. Run the exports in the shell you will use for every step below. Start
Amoeba in a second terminal with the printed command; it stays in the foreground.

The start-up log must show both probes passing:

```
sq probe passed: `sq runs wait` has the shape the Runner needs
answering pipeline probe passed: `sq run --validate` exited 0
```

A probe failure that names missing Squadron capabilities means the installed `sq`
cannot run the answering pipeline; upgrade it. Any other failure is a defect.

Find the six slice nodes (indexes 100 to 105) and their ids:

```
amoeba inspect nodes --project scratch --json
```

In the commands below, `<node>` is the `id` of the slice with that `cf_index`.
Each slice is driven only after the previous one is `done`.

## Driving a slice and answering as the PM

Drive one slice:

```
amoeba submit intent --project scratch --by pm --node-id <node> --body '{"intent": "drive"}'
```

The design run asks its question and pauses. Watch with `amoeba inspect questions
--project scratch` and `amoeba inspect nodes --project scratch`.

To answer as the PM, find the block and resolve it with a resume:

```
amoeba inspect blocked --project scratch --json
amoeba submit resolution --project scratch --by pm --blocked-state-id <id> \
    --detail "answered by the PM" --decision resume --instructions "<answer text>"
```

If a design run fails or ends without asking (a provider error, a missing key), it never
reaches the answerer. Resolve its block with `--decision stop`, note it, and repeat the
case once on a fresh slice index.

What to check after a case:

- `amoeba inspect questions --project scratch --json`: the record's `state`,
  `answered_by`, `check_verdict`, `outcome`, `reserved_term`, `decline_detail`,
  `cited_passages` and `passage_index`.
- `amoeba inspect journal --project scratch`: `sq_run` and `sq_answer` entries.
- `amoeba inspect nodes --project scratch`: the slice's `status`.

## Case 1: answered from the plan (slice 100)

Drive slice 100. Its plan entry makes the design agent ask which storage format notes
use; the concept says JSON Lines.

Expect:

- the record is `answered`, `answered_by` is `answerer`, `check_verdict` is `yes`, and
  `cited_passages` includes the concept passage;
- the journal shows the design `sq_run`, an `sq_answer`, then a resume of the design run
  whose instructions restate the question;
- the run completes and the slice is `done`.

## Case 2: the screen declines a merge question (slice 101)

Drive slice 101 after slice 100 is `done`. Its question is whether the branch merges
once its review passes. The architecture answers it, so the answering run can say yes;
the term `merge` in the project's `reserved_terms` is what stops it.

Expect the record `declined`, `outcome` `reserved_term`, `reserved_term` `merge`, and no
resume from the answerer. Then answer as the PM with this text:

> Yes. Merge the branch to main once its review passes, as the architecture says.

Expect the run to complete and the record to become `answered`, `answered_by` `pm`.

If the check step declined first (`outcome` `check_said_no`), record its `decline_detail`
and repeat once on a fresh slice index, copying slice 101's forcing sentence into the
scratch plan.

## Case 3: a PM answer reused when reworded (slices 102, 103)

Drive slice 102. Nothing on file says how dates are written, so the question is declined.
Answer as the PM with:

> Write dates as YYYY-MM-DD, in UTC.

When slice 102 is `done`, drive slice 103. It asks the same thing in other words. Expect
the record `answered` by the answerer, citing the PM passage from slice 102, and the
run to complete. A decline (`check_said_no` or `answerer_declined`) is recorded with its
`decline_detail`; repeat once on a fresh slice index.

## Case 4: a PM answer stands against an older rule (slices 104, 105)

First commit a rule in the scratch checkout, on `main`:

```
echo "Source files carry no license header." >> D/checkout/CLAUDE.md
git -C D/checkout commit -am "rule: no license header"
```

Drive slice 104. It asks two questions in order. The first, the storage format, is
answered by the answerer and uses the run's one answer. The second, whether new source
files carry a license header, is declined: `answer_limit_reached`, or a decline by the
answering run. Wait until the design run and the answering run have both finished, then
answer as the PM with:

> Every new source file starts with the MIT license header; this replaces the rules file for this project.

The PM answer is dated after the rule, so it is the later passage.

When slice 104 is `done`, drive slice 105. It asks what copyright notice each new file
opens with. Expect the record `answered` by the answerer, citing slice 104's PM passage,
with `passage_index` listing the rule's date before the PM answer's, and the run to
complete.

## Final checks

- With `CONTEXT_FORGE_DATA_DIR` unset, `cf project list` does not list `scratch` at
  `D/checkout`.
- Nothing was written outside `D`.
- Stop Amoeba with `amoeba stop`, then remove `D`.
