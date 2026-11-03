---
docType: reference
project: amoeba
slice: live-walkthrough
dateCreated: 20261103
dateUpdated: 20261103
status: complete
---
# Answerer walkthrough

## Purpose

Run the question answerer against real Squadron runs, on a throwaway project, and see
what it does: the records, the journal entries and the resumed runs. Four cases:

1. A question the plan answers is answered by the answerer.
2. A question about merging is declined and the PM answers.
3. A PM answer is reused when the question comes back in other words.
4. A newer PM answer stands against an older rule.

Everything lives under one directory `D`. The real Context Forge registry is never
written. Repeat this after any change to the answerer or to Squadron.

Each case ends with an "Observed" line: what happened on 20261103 with Squadron 0.24.16
(answer model `glm-flash`, check model `deepseek4-flash`). Two cases did not go as the
design expected; each says so and names its issue.

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

`D` must not exist. The script registers the scratch checkout with Context Forge
(`cf init --no-ide`, which installs the AI project guide the design step needs, then
`cf set concept`, `arch` and `plan`), commits it, and queues the project and its link in
the store's inbox. It prints two `export` lines and an `amoeba start` command. Run the
exports in the shell you will use for every step below.

The answering runs start from `D/store/answering/`, outside the checkout, so they take
provider keys from Amoeba's own environment. Export the keys from your `.env` in the
shell that starts Amoeba. Start it in a second terminal with the printed command; it
stays in the foreground.

The start-up log must show both probes passing:

```
sq probe passed: `sq runs wait` has the shape the Runner needs
answering pipeline probe passed: `sq run --validate` exited 0
```

A probe failure that names missing Squadron capabilities means the installed `sq`
cannot run the answering pipeline; upgrade it. Any other failure is a defect.

Find the slice nodes (indexes 100 to 105) and their ids:

```
amoeba inspect nodes --project scratch --json
```

In the commands below, `<node>` is the `id` of the slice with that `cf_index`.
A slice is ready only when the slice with the next-lower index is `done`, so drive
them in order. The project's plan is re-read about every 30 seconds.

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

A run whose review loop never passes ends in a `paused` block (`loop_exhausted`), which
is not a question. Resolve it with `--decision resume` to run the loop again.

If a design run fails or ends without asking, it never reaches the answerer. Resolve its
block with `--decision stop`, note it, and repeat the case on a fresh slice. A fresh
slice goes at the end of the scratch plan, after the last slice, because of the
ordering rule above: add an entry to `D/checkout`'s `100-slices.notes.md` (the same
forcing sentence as the case's slice), commit it on `main` and wait for the node.

What to check after a case:

- `amoeba inspect questions --project scratch --json`: the record's `state`,
  `answered_by`, `check_verdict`, `outcome`, `reserved_term`, `decline_detail`,
  `cited_passages` and `passage_index`.
- `amoeba inspect journal --project scratch`: `sq_run` and `sq_answer` entries. A resume
  after an answer is a second `sq_run` with `continuation: resume`.
- `amoeba inspect nodes --project scratch`: the slice's `status`.

## Case 1: answered from the plan (slice 100)

Drive slice 100. Its plan entry makes the design agent ask which storage format notes
use; the concept says JSON Lines.

Expect:

- the record is `answered`, `answered_by` is `answerer`, `check_verdict` is `yes`, and
  `cited_passages` includes the concept passage;
- the journal shows the design `sq_run`, an `sq_answer`, then a second `sq_run` that
  resumes the design run;
- the run completes and the slice is `done`.

**Observed 20261103:** as expected. Cited the concept passage; the question tail was
flagged `truncated` and was still answered.

## Case 2: a merge question reaches the PM (slice 101)

Drive slice 101 after slice 100 is `done`. Its question is whether the branch merges
once its review passes. The architecture answers it, so a yes is available; the term
`merge` in the project's `reserved_terms` would stop it if the answer step said yes.

Expect the record `declined` and no resume from the answerer. Then answer as the PM
with this text:

> Yes. Merge the branch to main once its review passes, as the architecture says.

Expect the run to complete and the record to become `answered`, `answered_by` `pm`.

**Observed 20261103:** the PM half worked. The decline was `answerer_declined`, not
`reserved_term`: the answering prompt itself tells the answer step to decline any
answer that authorizes a merge to main, so the screen never saw a yes. A rerun (slice
106) did the same. See ecorkran/amoeba#23.

## Case 3: a PM answer reused when reworded (slices 102, 103)

Drive slice 102. Nothing on file says how dates are written, so the question is declined.
Answer as the PM with:

> Write dates as YYYY-MM-DD, in UTC.

When slice 102 is `done`, drive slice 103. It asks the same thing in other words. Expect
the record `answered` by the answerer, citing the PM passage from slice 102, and the
run to complete. A decline (`check_said_no` or `answerer_declined`) is recorded with its
`decline_detail`; repeat once on a fresh slice.

**Observed 20261103:** as expected. Slice 102 declined `answerer_declined` (no passage
states the format); slice 103 answered by the answerer, check yes, citing P20, the PM
passage.

## Case 4: a PM answer stands against an older rule (slices 104, 105)

First commit a rule in the scratch checkout, on `main`:

```
echo "Source files carry no license header." >> D/checkout/CLAUDE.md
git -C D/checkout commit -am "rule: no license header"
```

Drive slice 104. It asks two questions in order. The first, the storage format, is
answered by the answerer and uses the run's one answer. The second, whether new source
files carry a license header, is declined `answer_limit_reached`, even when the check
says yes. Wait until the design run and the answering run have both finished, then
answer as the PM with:

> Every new source file starts with the MIT license header; this replaces the rules file for this project.

The PM answer is dated after the rule, so it is the later passage. The resumed agent may
ask its first question again, because the second resume carries only the latest answer.
The limit declines it too; answer it as the PM.

When slice 104 is `done`, drive slice 105. It asks what license header text each new
source file opens with. Expect the record `answered` by the answerer, citing slice 104's
PM passage, with `passage_index` listing the rule's date before the PM answer's, and the
run to complete.

**Observed 20261103:** the first half worked, on slice 109 (a rerun): the first question
was answered by the answerer, the second declined `answer_limit_reached` with check yes,
and the PM answered after the rule's commit. The second half did not: slice 110 (the
rerun of 105) wrote its design without asking, because the agent found the MIT answer
in slice 109's design. Earlier tries failed on forcing wording: slice 104 skipped both
questions; slice 107's wording, which told the agent that documents do not count,
made the answerer decline its own first question. See ecorkran/amoeba#24.

## Final checks

- With `CONTEXT_FORGE_DATA_DIR` unset, `cf project list` does not list `scratch` at
  `D/checkout`.
- Nothing was written outside `D`.
- Stop Amoeba with `amoeba stop`, then remove `D`.
