---
docType: slice-design
slice: judge-samples-checks-and-calibration
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [104, 105, 106]
interfaces: [110]
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: judge-samples-checks-and-calibration

## Overview

Slice 104 stores review verdicts and their findings. It stores `score` and `criteria` because review files carry them, but nothing uses them, and nothing ties the samples of one Judge request together. This slice adds three kinds of evidence and one report:

1. **Judge samples.** A judge sample is a verdict record with a `judge_invocation_id`. Samples of one invocation are recorded one by one and never merged. The out-of-process Judge (initiative 140) submits them through 104's existing `verdict` inbox kind, which gains one optional key.
2. **A calibration report.** `calibration(project_id)` summarizes judge samples by review type and model: counts, verdict spread, score range, and how many invocations disagreed with themselves. It is read-only and descriptive, and it writes nothing to Squadron.
3. **Check results.** A mechanical check (a validator, a test run, `cf check`) is recorded with what it examined. A check that examined nothing has standing `vacuous`, never `passed`.
4. **Work records.** SQ 280's `task_progress` and `devlog` types land in one small table with opaque JSON content, until a consumer defines their fields. SQ 280's other two types already have homes: `review_findings` is 104's verdict and its findings, and `checkpoint` is 101's blocked state.

The first draft of this design is inside slice 104's draft at commit `c525a63` (its D4, D5, and D6). This document starts from it and brings it up to date against 104 and 105 as designed and built.

## Value

Developer value:

- Initiative 140 gets somewhere to put N samples per Judge request and a report to read them back from. That is the substrate half of consensus. Computing consensus stays 140's job.
- The Runner (120) can tell a validator that exited 0 having checked zero files (cf#87/#88) from one that checked twelve and passed.
- The PM can see, per judge template and model, how scores and verdicts spread, without writing SQL and without touching Squadron's metrology store.

## Technical Scope

**Included**

- `judge_invocation_id` on `VerdictInput`, `VerdictRecord`, the `verdicts` table, the `verdict` payload (optional key), `verdict_to_payload`, 105's `to_verdict_input`, and `amoeba ingest review --judge-invocation-id`.
- One precondition on judge samples: every sample of an invocation is on the same node (D2).
- 104's previous-round rule gains one exclusion: a judge sample never takes a sample of its own invocation as its previous round (D3).
- A `judge_invocation_id` filter on `verdicts(...)`, and on `amoeba inspect verdicts`.
- `calibration(project_id) -> tuple[CalibrationRow, ...]` and `amoeba inspect calibration` (D4).
- `record_check`, `check`, `checks`, the `CheckOutcome` and `CheckStanding` vocabularies, `check_standing`, and `amoeba inspect checks` (D5).
- `record_work`, `work_records`, the `WorkRecordKind` vocabulary, and `amoeba inspect work-records` (D6).
- `RecordSource` gains `command_output` and `document`.
- The next store migration (`007` if 106 lands first, as planned) and `EXPECTED_SCHEMA_VERSION` + 1.
- `scripts/demo_checks.py`, which seeds checks and work records for the walkthrough.
- New judge review fixtures in `tests/fixtures/sq_reviews/`, recorded in the README.
- Documentation: `docs/evidence-contract.md` gains judge-sample, calibration, check, and work-record sections. `docs/inbox-contract.md`'s stale line "Slice 104 adds verdict and judge-sample kinds" is corrected. `docs/store-contract.md` and `CHANGELOG.md` are updated.

**Excluded**

- **Consensus.** Aggregating an invocation's samples into one answer, storing that answer, and resolving `blocked_on_judge` nodes are 140's. A judge sample is evidence; resolution stays an explicit `resolution` submission.
- **Recommendations and thresholds.** The report counts and summarizes. Recommending a threshold is 140's work, reported to the PM. Nothing here mutates a threshold or writes outside the project store (the architecture's metrology constraint).
- **Excluding escalated-gate samples from agreement data.** The store does not know which gates were escalated. 140 applies that filter when it computes agreement.
- **Calibration across projects.** Each project has its own store file, so the report is per project. Combining projects is a later report's job.
- **Inbox kinds for checks and work records.** Their producers (the Runner, 106's tenant) run in-process. A kind can be added later through 103's three-part seam.
- **Checks and work records on 106's change feed.** Putting a table on the feed means a new `ChangeKind` and a trigger (106's D8). Nothing subscribes to these yet. Judge samples are verdicts, so they already emit `verdict_recorded`.
- **Fields for `task_progress` and `devlog`.** Content stays an opaque JSON object until a consumer designs it.

## Dependencies

### Prerequisites

- **Slice 104:** `VerdictInput`, `VerdictRecord`, the `verdicts` table, the `verdict` inbox kind and its payload keys, the first-wins retry rule, `finding_changes` and its previous-round rule, the `Listing` registry with `value_options`, and `docs/evidence-contract.md`.
- **Slice 105:** `to_verdict_input`, `verdict_to_payload`, and `amoeba ingest review`, which this slice extends with the invocation id. It also parses `score` and `criteria` from judge files. *Added at slice design:* the slice plan lists only 104.
- **Slice 106:** it takes migration 006, and it changes the previous-round query to group by `source_document`. This slice edits the same query, so it builds on 106's version. *Added at slice design.* If 106 slips, this slice takes 006 and 106 rebases onto it; nothing else changes.
- **Slices 101 and 103**, through 104: the migration mechanism, `Store`, `submit()`, and the writer guard.

### Interfaces Required

**What Squadron writes for judges today.** This is a dated observation, not a version pin, checked on 20260928 against squadron `main` at `5cd5f76d`.

- Judge templates are named with a dot (`judge.slice-vs-arch`, `judge.tasks-vs-slice`, `judge.findings-addressed`). The review file's `reviewType` carries that name.
- A judge file carries `score` (0–100) and a `criteria` mapping of criterion name to 0–100. It also carries findings in the usual shape.
- A judge file's verdict comes from the score by threshold, computed by Squadron's `enforce_judge`. Squadron writes **no** `verdictSource` for it, on purpose. 105's parser maps the absence to `not_reported`, so a judge sample read from a file has standing `unattested`. That is the honest label: Squadron did not say how the verdict was reached. The report shows it; nothing here reinterprets it.
- Stdout JSON reports `verdict: UNKNOWN` for judge templates (squadron#140, still open). A sample read from stdout therefore has standing `unparsed`. Judge samples are ingested from the file, which 105 already recommends for every review.

From Amoeba: 104's `_verdict_writer.py` and `verdicts.py`, `sql_evidence.py`, `mapping_evidence.py`, `verdict_payload.py`, `inbox/evidence_payloads.py`, and `cli/inspect.py`'s `LISTINGS`.

## Architecture

### Component Structure

```
src/amoeba/store/
  evidence_models.py    + judge_invocation_id on VerdictInput; RecordSource + 2 members
  check_models.py       CheckOutcome, CheckStanding, check_standing, CheckInput/Record,
                        WorkRecordKind, WorkRecordInput/Record, CalibrationRow
  calibration.py        summarize_judge_samples(records) — pure, no SQL
  checks.py             CheckOperations mixin: record_check, check, checks,
                        record_work, work_records
  sql_checks.py         column names and statements for check_results and work_records
  mapping_checks.py     row ↔ record for the two tables
  _verdict_writer.py    + the D2 precondition
  verdicts.py           + judge_invocation_id filter, D3 exclusion, calibration()
  verdict_payload.py    + VERDICT_JUDGE_INVOCATION_ID
  schema/007_judge_samples_checks_and_work.sql
src/amoeba/inbox/evidence_payloads.py   + judge_invocation_id: str | None = None
src/amoeba/upstream/squadron/review.py  + judge_invocation_id argument (105's module)
src/amoeba/cli/
  ingest.py             + --judge-invocation-id
  inspect_evidence.py   + calibration rows; verdict rows gain judge_invocation_id
  inspect_checks.py     check and work-record rows
  inspect.py            + three listings; --judge-invocation-id on verdicts
scripts/demo_checks.py
```

`sql_evidence.py` (204 lines) and `mapping_evidence.py` (293) are near the size limit, so the two new tables get their own SQL and mapping modules. `Store` gains the `CheckOperations` mixin beside `VerdictOperations`.

### Data Flow

**A judge invocation, from outside the process:**

```
Judge (140) picks invocation id J, runs N judge reviews
  for each review file:
    amoeba ingest review --artifact F --judge-invocation-id J …   (or submit verdict)
      → verdict submission with judge_invocation_id = J
  resident process applies each:
    record_verdict                       one transaction, as in 104
      replay check (first wins)
      node exists; journal entry on the same node         (104)
      provider-failure rule                                (104/105)
      J already has samples on another node? → rejected    (D2)
      INSERT verdict row with judge_invocation_id = J; findings as in 104
```

**The calibration report** (read-only, works with the process stopped):

```
calibration(project_id)
  records = verdicts with judge_invocation_id set, in recorded_seq order
  summarize_judge_samples(records)       pure: group by (review_type, model)
  → CalibrationRow per group, sorted by review_type, model
```

**A check, in-process** (the Runner, later 106's tenant):

```
record_check(CheckInput)                  one transaction
  replay check (first wins; WARNING if content differs)
  node exists in the project; name and upstream_version non-empty
  examined_count ≥ 0; if examined is given, examined_count == len(examined)
  INSERT check_results row
```

`record_work` follows the same pattern for `work_records`.

### State Management

All durable state is in the project store: one new column on `verdicts` and two new tables. Check standing and the calibration report are derived on read and never stored, like 104's verdict standing, so changing either rule needs no data migration.

## Technical Decisions

D1 and D5's standing table were ratified in 104's draft on 20260926. D2–D4 and D6 are pending PM ratification.

### Technology Choices

**D1 — A judge sample is a verdict record; samples of one invocation share a `judge_invocation_id`. (PM — ratified 20260926, on condition of clear naming; carried from 104's draft D4.)** A judge run is an `sq review` with a judge template, and a sample's fields (model, run id, score, verdict) are a subset of a verdict record's. A separate table would duplicate every provenance column and split "every verdict" across two tables.

Names, used the same way in code, docs, and CLI:

- A **judge invocation** is one request to the Judge for N samples, identified by `judge_invocation_id`, an opaque id the caller picks.
- A **judge sample** is a verdict record whose `judge_invocation_id` is set.
- A verdict record without one is a **review verdict**.

The id is caller-supplied data and is not part of 105's digest record id. So one review file is one sample: ingesting the same file into a second invocation is a no-op that keeps the first. A caller that really wants the same file in two invocations passes `--id`.

**D2 — Every sample of one invocation is on the same node.** An invocation judges one gate. `record_verdict` rejects a sample whose invocation already has a sample on a different node (direct call: `ValueError`; inbox: `rejected` with the reason). The check is one indexed lookup. Without it, a typo in `--node` would silently split an invocation across gates, and 140's consensus would read half of it. Nothing else about an invocation is constrained: samples may differ in model, review type, and verdict. If 140 finds a real need for one invocation spanning nodes, it drops this rule.

### Patterns and Conventions

**D3 — A judge sample never compares against its own invocation.** 104's `finding_changes` picks the previous round as the latest comparable verdict on the same node and review type (106 adds `source_document`). For a judge sample, that would be the previous sample of the same invocation: sample 3 would report sample 2's findings as `recurring`, which is two models agreeing, not an issue carried across rounds. So when the target is a judge sample, the previous-round query also excludes samples with the same `judge_invocation_id`. Its previous round is then the latest sample of an earlier invocation. Review verdicts are unaffected, and judge review types never match ordinary ones, so the two never mix.

**D4 — The calibration report is descriptive, per `(review_type, model)`, over judge samples only.** `CalibrationRow` holds:

| Field | Meaning |
| --- | --- |
| `review_type`, `model` | The group. `model` is the answering model. |
| `samples` | Judge samples in the group. |
| `invocations` | Distinct invocations with at least one sample in the group. |
| `split_invocations` | Of those, invocations whose samples, across **all** models, carry more than one verdict. Samples with standing `provider_failure` or `unparsed` are left out of that comparison, because a failed call is not a disagreement. |
| `by_verdict` | Count per `ReviewVerdict`. |
| `by_standing` | Count per `VerdictStanding`. |
| `scored` | Samples with a score. |
| `score_min`, `score_mean`, `score_max` | Over scored samples; `None` when `scored` is 0. |

An invocation that spans three models counts in each of the three rows, so `split_invocations` summed down the table overcounts. The contract says so. Per-invocation detail is `verdicts(project_id, judge_invocation_id=J)`.

*Why this shape:* it is what the architecture calls calibration evidence, stated as counts a PM can read. Anything that interprets the counts (agreement rates, recommended thresholds, admissibility) is 140's. `criteria` stays per sample, readable through `verdict(id)`; averaging criteria across models whose criterion names drift is interpretation, so the report does not do it.

*The aggregation* is a pure function over `VerdictRecord`s in `calibration.py`, not SQL. The standing is a Python rule (104), so SQL cannot group by it without duplicating the rule. Judge samples per project are few, and the function is tested on built records with no store.

**D5 — A check records what it examined; standing is derived. (Standing table ratified 20260926 in 104's draft D5.)** `CheckInput`:

- `id`, `node_id`, `name` (free text: `cf check`, `pytest`, `validate-slice-design`)
- `outcome: CheckOutcome` (`passed`, `failed`, `errored`)
- `examined_count: int | None` — `None` means the check did not report it; required, with no default, as with 104's "unknown is a value"
- `examined: tuple[str, ...] | None` — what was examined (paths, test ids), when the producer has it
- `provenance: Provenance`

| `CheckStanding` | Rule, top to bottom |
| --- | --- |
| `errored` | outcome is `errored` |
| `unattested` | `examined_count` is `None` |
| `vacuous` | `examined_count` is 0 |
| `passed` / `failed` | the outcome |

`vacuous` covers a failed check that examined nothing too: it failed at nothing, which is no more informative than passing at nothing. `check_standing` is defined once in `check_models.py`, like `verdict_standing`.

**D6 — SQ 280's four types map onto records; two need a table, and they share one. (PM — pending; carried from 104's draft D6.)** SQ 280 gave its types one-line descriptions and no fields.

- `review_findings` is a verdict and its findings (104). A second home would give one fact two places.
- `checkpoint` is a `blocked_on_sq_checkpoint` node carrying the SQ run id (101).
- `task_progress` and `devlog` have no home and no designed consumer. They share one `work_records` table with a closed `WorkRecordKind`, an opaque JSON-object `content`, and the standard provenance, like 103's message payloads.

The table is named `work_records`, not "artifacts", because "review artifact" already means a Squadron review file throughout 104, 106, and 105. Fields are designed when a consumer needs them; until then the store checks only that `content` is a JSON object.

**Vocabulary and provenance.** `RecordSource` gains `command_output` (checks) and `document` (work records read from a file). It stays one vocabulary, describing what the caller read the record from. It is not restricted per record type. Checks and work records carry the same `Provenance` as verdicts, so every recorded item has a non-empty `upstream_version` (the slice plan's criterion). For a check, `upstream` names the tool (`context-forge`, `pytest`) and the version is whatever that tool reports.

**Ids and retries.** Checks and work records follow 104's rule: a caller-supplied id, first wins, a WARNING when a replay's content differs.

**Error handling.** Direct calls raise `ValueError` on a failed precondition, as `record_verdict` does. The inbox path for judge samples returns the D2 reason as a rejection, checked as an explicit branch in `_verdict_rejection`, never by catching the exception. No broad `except` is added.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `verdicts(project_id, *, node_id=None, judge_invocation_id=None)` | 104's read, with one more filter. |
| `calibration(project_id) -> tuple[CalibrationRow, ...]` | D4. Read-only. |
| `record_check(CheckInput) -> CheckRecord` | One transaction; D5 preconditions; first wins. |
| `check(check_id) -> CheckRecord \| None` / `checks(project_id, *, node_id=None)` | In `recorded_seq` order. `CheckRecord.standing` is computed. |
| `record_work(WorkRecordInput) -> WorkRecordRecord` | Same pattern. |
| `work_records(project_id, *, node_id=None, kind=None)` | In `recorded_seq` order. |

`WorkRecordInput`: `id`, `node_id`, `kind: WorkRecordKind`, `content: Mapping[str, object]`, `provenance`.

**Inbox.** The `verdict` payload gains `judge_invocation_id: str | None = None`. Because 103's `amoeba submit` builds flags from the payload model, `amoeba submit verdict --judge-invocation-id J` exists with no CLI code. An empty string is refused by payload validation.

**105's parser.** `to_verdict_input(..., judge_invocation_id=None)` passes the id through. It stays out of `review_record_id` (D1).

**CLI:**

```
amoeba ingest review … [--judge-invocation-id ID]
amoeba inspect verdicts --project ID [--node ID] [--judge-invocation-id ID]
amoeba inspect calibration --project ID
amoeba inspect checks --project ID [--node ID]
amoeba inspect work-records --project ID [--node ID] [--kind task_progress|devlog]
```

- `verdicts` gains a `judge_invocation_id` column (blank for review verdicts).
- `calibration` columns: `review_type, model, samples, invocations, split_invocations, pass, concerns, fail, unknown, score_min, score_mean, score_max`. `--json` rows also carry `by_standing` and `scored`.
- `checks` columns: `recorded_seq, id, node_id, name, outcome, examined_count, standing, upstream_version`. `--json` adds `examined` and the provenance fields.
- `work-records` columns: `recorded_seq, id, node_id, kind, upstream_version, recorded_at`. `--json` adds `content`.

All are read-only listings in 102's registry and work with the process running or stopped. No new exit code.

### Database / Storage Schema

Migration `007_judge_samples_checks_and_work.sql` (the next free number), `EXPECTED_SCHEMA_VERSION` + 1. Nothing to backfill: existing verdicts are review verdicts, and `judge_invocation_id` is `NULL` for them.

- **`verdicts`** gains `judge_invocation_id TEXT` (nullable) and an index on `(project_id, judge_invocation_id)` for D2's lookup, the filter, and D3's exclusion.
- **`check_results`**: `recorded_seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `id` (UNIQUE), `project_id`, `node_id` (FK `nodes`), `name`, `outcome`, `examined_count` (INTEGER, nullable), `examined` (JSON text, nullable), `upstream`, `upstream_version`, `source`, `source_path`, `recorded_at`. Index on `(project_id, node_id, recorded_seq)`.
- **`work_records`**: `recorded_seq`, `id` (UNIQUE), `project_id`, `node_id` (FK), `kind`, `content` (JSON text), the same provenance columns, `recorded_at`. Index on `(project_id, node_id, kind, recorded_seq)`.

As in 104, no `CHECK` constraints on vocabulary columns; the mapping raises on an unknown value. Column names are defined once in `sql_checks.py`, and the provenance column names are shared with `sql_evidence.py` rather than repeated.

## Integration Points

### Provides to Other Slices

- **110:** judge samples through `amoeba submit verdict --judge-invocation-id`, read back through `verdicts(..., judge_invocation_id=J)`, for its Judge actor (step 5 of its sequence).
- **Initiative 140:** the judge-sample write path, the per-invocation read, and `calibration` as its evidence source. The kind seam remains for consensus records when 140 designs them.
- **Initiative 120:** `record_check`, `check_standing`, and `record_work` in-process; checks' `vacuous` standing for gating.
- **106 (later):** checks and work records can join the change feed by adding a `ChangeKind` and a trigger.

### Consumes from Other Slices

- **104:** unchanged in behavior for review verdicts. It gains a column, a filter, one rejection rule that applies only to judge samples, and D3's exclusion, which applies only to judge samples.
- **106:** its migration and its previous-round query, extended here. Its `verdict_recorded` trigger fires for judge samples unchanged; the trigger's payload does not carry `judge_invocation_id`, so a subscriber reads `verdict(id)`, as it already does for the standing.
- **105:** `to_verdict_input`, `verdict_to_payload`, and `ingest review`, each extended by one argument or key. 105's round-trip test covers the new key.

## Success Criteria

### Functional Requirements

- Three samples sharing one `judge_invocation_id`, with different models, scores, and verdicts, are three verdict records, each with its own model, run id, score, criteria, and verdict. `verdicts(project, judge_invocation_id=J)` returns exactly those three in arrival order.
- A sample whose invocation already has a sample on another node raises directly and is `rejected` through the inbox, with the reason. A review verdict is never affected by D2.
- `finding_changes` on the second sample of an invocation does not use the first sample as its previous round. With an earlier invocation present, it uses that invocation's latest comparable sample. Review verdicts' previous rounds are unchanged (104's and 106's tests pass as they are).
- `calibration` over a built set gives the D4 fields exactly, including: an invocation split across two models counts in both rows; a provider-failure sample does not make an invocation split; `score_*` are `None` when nothing is scored. `summarize_judge_samples` is tested on built records with no store.
- A check with `examined_count=0` and outcome `passed` has standing `vacuous`; the same with outcome `failed` is `vacuous`; `examined_count=None` is `unattested`; `errored` wins over everything. Each `CheckStanding` row is produced by a record built for it.
- `record_check` rejects a negative count, a count that disagrees with `examined`, an empty name, an unknown node, and an empty `upstream_version`.
- `record_work` stores and returns content as given; content that is not a JSON object is rejected. `work_records(kind=…)` filters.
- Recording a check or work record with an existing id returns the existing record, writes nothing, and logs a WARNING if the content differs.
- `amoeba ingest review --judge-invocation-id J` on the judge fixture records a sample with `score` and `criteria` from the file and standing `unattested`.
- `amoeba inspect verdicts|calibration|checks|work-records` work with the process running and stopped.

### Technical Requirements

- Vocabularies are `StrEnum`s defined once. `check_standing` has one definition. Column names are defined once. The provenance columns are not repeated between `sql_evidence.py` and `sql_checks.py`.
- A store at the previous schema version, holding nodes, journal entries, submissions, messages, verdicts, and findings, upgrades with all of them intact and every verdict's `judge_invocation_id` `NULL`.
- The writer guard is unchanged: `scripts/demo_checks.py` takes the instance lock and is named in the guard's allow-list, like `demo_evidence.py`.
- No source module references Squadron's metrology directory or config key (104's test covers the new modules).
- **Fixtures**, copied byte for byte and given README entries:
  - Squadron's `302-review.judge.slice-vs-arch.design-phase-judge-templates.md`: real, July 2026, no stamp. Pins `score` and a `criteria` mapping.
  - One fresh judge file, captured at implementation with `sq review` on a judge template and `--model glmflash`, in a throwaway copy of this repository. Pins today's judge frontmatter and the absent `verdictSource`. The README records the exact command.
- The public-API test's pinned export set is updated.
- `ruff`, `pyright` strict, and the full suite are clean. Source files stay near 300 lines.
- `docs/evidence-contract.md` states the D1 names, D2, D3, D4 (including the overcount note and what the report does not do), the check standing table, D6's mapping, and the judge-standing observation. `inbox-contract.md`, `store-contract.md`, and `CHANGELOG.md` are updated.

### Integration Requirements

- End to end through the real CLI as subprocesses: create a project, seed a node, ingest the judge fixture as one sample of `j1` and submit two built samples of `j1` with other models (one CONCERNS), submit one sample of `j1` against a different node, then `kill -9` and `start`. Read-only inspection then shows three samples of `j1`, one rejected submission naming D2, and a calibration table with `split_invocations` 1 in every row that `j1` touches.

### Verification Walkthrough

Draft; refined with captured output when Phase 6 completes. The setup is 105's: `uv run` from the repository root, wait for `running` after each start, and an empty `--sq-runs-dir`.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
SQ_RUNS="$(mktemp -d)"
wait_running() { until uv run amoeba status | grep -q '^running'; do sleep 0.2; done; }
uv run amoeba start --sq-runs-dir "$SQ_RUNS" &
wait_running
uv run amoeba submit create-project --project demo --by pm
uv run amoeba stop
NODE=$(uv run python scripts/demo_evidence.py)
OTHER=$(uv run python scripts/demo_checks.py --node "$NODE")
uv run amoeba start --sq-runs-dir "$SQ_RUNS" &
wait_running
F=tests/fixtures/sq_reviews
JUDGE="$F/302-review.judge.slice-vs-arch.design-phase-judge-templates.md"
```

`demo_checks.py` does not exist yet. It records three checks on `$NODE` (12 files examined and passed, 0 examined and passed, and one with no count) and one `task_progress` work record. It also seeds a second node for step 4 and prints only that node's id.

**1. A judge sample from a real file.**

```bash
uv run amoeba ingest review --project demo --node "$NODE" --by judge \
  --artifact "$JUDGE" --upstream-version pre-stamp --judge-invocation-id j1
uv run amoeba inspect verdicts --project demo --judge-invocation-id j1 --json
```

Expected: one row with `review_type: judge.slice-vs-arch`, `verdict: PASS`, `standing: unattested`, and `judge_invocation_id: j1`. `uv run amoeba inspect verdicts --project demo --json` for that id shows `score: 98.0`.

**2. More samples of the same invocation stay separate.**

```bash
for m in glm-5.3 kimi-k3; do
  uv run amoeba submit verdict --project demo --by judge --node-id "$NODE" \
    --judge-invocation-id j1 --verdict CONCERNS --derivation not_reported \
    --fallback-used null --findings-parsed true --provider-failure false \
    --review-type judge.slice-vs-arch --model "$m" --score 71 \
    --upstream squadron --upstream-version 0.15.0 --source artifact_frontmatter \
    --findings '[]'
done
```

Expected: `inspect verdicts --judge-invocation-id j1` shows three rows, one per model. None of them is merged.

**3. The calibration report.**

```bash
uv run amoeba inspect calibration --project demo
```

Expected: three rows under `judge.slice-vs-arch`, one per model. Each shows `samples 1`, `invocations 1`, `split_invocations 1` (PASS against CONCERNS). The minimax row shows score 98; the other two show 71.

**4. An invocation stays on one node.** Submit a fourth `j1` sample as in step 2, with `--node-id "$OTHER"`. Expected: `uv run amoeba inspect submissions --project demo` shows it `rejected`, with a reason naming the invocation and its node. `inspect verdicts` still shows three samples.

**5. A vacuous check is not a pass.**

```bash
uv run amoeba inspect checks --project demo
uv run amoeba inspect work-records --project demo --json
```

Expected: the checks read `passed`, `vacuous`, and `unattested`. The work record shows `kind: task_progress` with its content as recorded.

**6. Survives a crash.** `kill -9` the process, start it, and `wait_running`. Expected: every listing above shows the same rows, and nothing is applied twice.

**7. The tests.**

```bash
uv run pytest tests/store/test_calibration.py tests/store/test_checks.py tests/store/test_judge_samples.py -v
```

## Implementation Notes

### Development Approach

1. **Vocabularies and pure rules.** `check_models.py`, `check_standing`, `CalibrationRow`, and `summarize_judge_samples`, each with table-driven tests on built records. Depends on nothing.
2. **Migration.** The migration, `sql_checks.py`, and the upgrade test.
3. **Judge samples.** `judge_invocation_id` through `VerdictInput`, mapping, payload keys, `VerdictPayload`, and `verdict_to_payload`; the D2 precondition on both paths; the `verdicts` filter; D3 in the previous-round query. Then `calibration()`.
4. **Checks and work records.** `CheckOperations`, its mapping, and tests.
5. **Parser and ingest.** 105's `to_verdict_input` argument and `--judge-invocation-id`; capture the fresh judge fixture and add both judge fixtures.
6. **Listings.** The three new listings and the verdict column and filter; update the pinned registry test.
7. **Proof and docs.** `scripts/demo_checks.py`, the end-to-end CLI test, the docs, and the `CHANGELOG`.

Test each step as soon as it is built, and commit after each step.

### Special Considerations

- **Judge standing reads `unattested`, by design.** Squadron deliberately writes no `verdictSource` for a threshold verdict. A reader of the report may take `unattested` for a defect. The contract doc explains it in one paragraph, and the report shows verdicts and standings side by side so the judge verdict itself is still readable.
- **The report must not become a threshold tool.** It has no parameters beyond the project and returns counts only. Anything that turns counts into advice belongs to 140 and goes to the PM.
