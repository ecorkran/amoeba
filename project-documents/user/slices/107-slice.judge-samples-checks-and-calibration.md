---
docType: slice-design
slice: judge-samples-checks-and-calibration
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105, 106]
interfaces: [108, 109, 110]
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

# Slice Design: judge-samples-checks-and-calibration

## Overview

Slice 104 stores what a review said. This slice stores the rest of the evidence the Runner and the Judge need:

1. **Judge samples.** A judge sample is a verdict record that carries a `judge_invocation_id`. The samples of one invocation are recorded one by one and never merged. They are never each other's "previous round".
2. **A calibration report.** A read-only summary of judge samples, grouped by review type and model. It counts and describes. It writes nothing back to Squadron and recommends nothing.
3. **Check results.** A mechanical check (a validator, a test run, `cf check`) is recorded with what it examined. A check that examined nothing is labelled `vacuous`, never `passed`.
4. **The rest of the SQ 280 typed-artifact scope.** `review_findings` is already 104's verdicts and findings. `checkpoint` is already 101's blocked state. `task_progress` and `devlog` get one small table with opaque content and an in-process writer, until a consumer defines their fields.

It also closes GitHub issue #2: a judge review's stdout JSON that reports `UNKNOWN` with a score is refused, and the operator is sent to the saved file.

The first draft of this design is in 104's git history (commit `c525a63`, D4–D6). This document starts from it and from what 104–106 actually shipped.

## Value

Developer value, and the substrate half of initiative 140's consensus work.

- **The Judge (140)** has somewhere to put N samples per invocation, a way to read them back, and a report that shows how each model's samples behave. Consensus itself stays 140's computation.
- **The Runner (120)** can tell a vacuous check from a pass. Field data shows validators that exit 0 having checked zero files (cf#87/#88). In the store, that check is `vacuous`.
- **Every record says where it came from** and at what upstream version label, including checks and progress records that do not come from Squadron.

## Technical Scope

**Included**

- Migration `007`:
  - a nullable `judge_invocation_id` column on `verdicts`;
  - two tables, `check_results` and `progress_records`;
  - one feed trigger, for checks, following 106's convention.
- `judge_invocation_id` on `VerdictInput`, on the `verdict` payload, on `to_verdict_input`, and on `amoeba ingest review` (`--judge-invocation`).
- Store operations: `record_check`, `check`, `checks`, `record_progress` (write-only), and `calibration`. `verdicts` gains a `judge_invocation_id` filter.
- The previous-round lookup skips samples of the target's own judge invocation.
- One new check on recording a sample: all samples of one invocation are on the same node and the same review type.
- One inbox kind, `check`, through 103's three-part seam.
- Listings: `inspect checks` and `inspect calibration`. `inspect verdicts` gains a `judge_invocation_id` column and a `--judge-invocation` option.
- The refusal of judge stdout that reports `UNKNOWN` with a score, in `parse_review_json` (issue #2).
- A real judge-template review artifact in `tests/fixtures/sq_reviews/`.
- `docs/evidence-contract.md`, `inbox-contract.md`, `feed-contract.md`, `store-contract.md`, and `CHANGELOG.md` updates.

**Excluded**

- **Consensus.** Turning N samples into `(resolution, confidence)` belongs to initiative 140. No consensus record is stored here. 140 adds one through the kind seam when it designs it.
- **Thresholds and recommendations.** The calibration report describes. Recommending a threshold to the PM is 140's job. Nothing here writes to Squadron's metrology store or reads it.
- **Excluding escalated-gate verdicts from agreement data.** Squadron's metrology rule is that these are inadmissible. The calibration report reports no agreement metric, so it carries no agreement data (D3). Agreement is 140's computation, and so is the escalated-gate attribute it filters on: GitHub issue #4.
- **The progress-record reader, record type, inbox kind, listing, and feed change.** Nothing reads progress records yet. They arrive with the first consumer: GitHub issue #5.
- **Per-criterion means in the calibration report.** No consumer is named: GitHub issue #6.
- **Diffing a check against its baseline.** The store keeps `baseline_ref`. The Runner (120) decides what a red check means.
- **Fields for `task_progress` and `devlog`.** Their content is opaque JSON until a consumer defines it.
- **Multi-part task reviews sharing a series** (`source_document` as a series key, issue #3). It changes the same previous-round lookup, but it is its own follow-up, as 106 recorded.
- **Resolving a `blocked_on_judge` node when samples arrive.** A sample is evidence. Resolution stays an explicit act through the `resolution` kind.

## Dependencies

### Prerequisites

- **Slice 101:** `Store`, nodes, and the migration mechanism (`EXPECTED_SCHEMA_VERSION` goes from 6 to 7).
- **Slice 102:** the listing registry (`Listing`, `ValueOption`, `LISTINGS`), `Store.open_read_only`, and the writer guard.
- **Slice 103:** the submission-kind seam (a `SubmissionKind` member, a `KIND_PAYLOAD_MODELS` entry, a `KIND_EFFECTS` entry) and `amoeba submit`.
- **Slice 104:** `verdicts`, `VerdictInput`, `VerdictWriter`, the trust label, `Provenance`, `RecordSource`, the previous-round lookup, the retry rule (first wins), and `amoeba submit`'s flag rule (text and enums as typed, everything else JSON).
- **Slice 105:** `parse_review_json`, `parse_review_artifact`, `to_verdict_input`, and `amoeba ingest review`. Judge samples are ingested through them.
- **Slice 106:** migration 006 and its trigger convention, and the feed invariant test, which requires a new `ChangeKind` for each new table.

101, 102, and 103 were added to the slice plan's dependency list at design time: this slice adds a migration, listings, and an inbox kind.

No new packages.

### Interfaces Required

From the store: `VerdictWriter._verdict_rejection`, `VerdictOperations._previous_round`, `StoreBase._execute`, and the one-transaction pattern of `record_verdict`. From the inbox: `KIND_PAYLOAD_MODELS`, `KIND_EFFECTS`, and `MODEL_CONFIG`. From the CLI: `LISTINGS`, `ValueOption`, and the parser built by `add_ingest_parser`.

**What Squadron does with judge reviews.** Observed 20261015 against squadron `e9de4da4` (package 0.22.0), recorded as a dated observation:

- Judge templates are `judge.slice-vs-arch`, `judge.tasks-vs-slice`, and `judge.findings-addressed`. Their `reviewType` is that dotted name.
- A judge's verdict is decided by its score against two floors, by default 75 (PASS) and 50 (CONCERNS), overridable per template and per pipeline step. A missing or out-of-range score gives `UNKNOWN`.
- **squadron#140 is fixed** (closed 20261015, fixed in 0.21.9, commit `b51272b7`). `sq review` now sets the threshold verdict before display, so stdout JSON, the terminal, and the saved file all carry it. Captures from before 0.21.9 still say `verdict: UNKNOWN` with a score.
- **A judge verdict carries no `verdictSource`.** Squadron's parser leaves it unset when the score decides the verdict (`review/parsers.py`). 105 reads an absent `verdictSource` as `not_reported`, so every judge sample's trust label is `unattested`. That is accurate ("the input did not say how the verdict was reached"), and this slice does not change the label.
- **squadron#139 is closed.** Pipeline runs stamp `runId` and `squadronVersion`. A CLI run carries no `runId`.
- No `sq review` subcommand runs a judge template directly. Judge reviews come from pipelines: `judge-cycle` begins with a `judge.slice-vs-arch` review.

## Architecture

### Component Structure

```
src/amoeba/store/
  check_models.py         CheckOutcome, CheckStanding, check_standing, ProgressKind,
                          ToolSource; CheckInput/Record, ProgressInput;
                          `check` payload keys, defined once; payload → input
  calibration.py          CalibrationRow; CalibrationOperations.calibration (read-only)
  sql_checks.py           every statement and column name for the two new tables
  mapping_checks.py       row → CheckRecord (raises on an unknown enum value)
  _check_writer.py        CheckWriter: the check's checks and insert, shared by
                          record_check and the `check` effect (the VerdictWriter pattern)
  checks.py               CheckOperations: record_check, check, checks, record_progress
  schema/007_judge_samples_checks_and_progress.sql
  evidence_models.py      + VerdictInput.judge_invocation_id; Provenance generic
                          over its source vocabulary
  verdicts.py             + sample-aware previous round; verdicts(judge_invocation_id=)
  _verdict_writer.py      + the invocation-consistency check
  feed_models.py          + ChangeKind.CHECK_RECORDED
src/amoeba/inbox/
  check_payloads.py       CheckPayload (pydantic)
src/amoeba/upstream/squadron/
  review_json.py          + the judge-stdout refusal
  review.py               + to_verdict_input(judge_invocation_id=)
src/amoeba/cli/
  inspect_checks.py       checks and calibration listings
  inspect_evidence.py     + judge_invocation_id column and --judge-invocation
  ingest.py               + --judge-invocation, and the sample id
```

This follows the per-concern pattern of 101–106: models, SQL, mapping, a writer base, and an operations mixin added to `Store`'s bases. `evidence_models.py` (264 lines), `mapping_evidence.py` (293), and `cli/inspect.py` (342) are at or past budget, so the new concerns get their own modules. Two splits are required, not optional: the pydantic `CheckPayload` lives in `amoeba.inbox` because the store never imports pydantic (its keys are defined once in `check_models.py`, as 104 did for verdicts), and `CheckWriter` is a base class so the inbox effect does not import a sibling operation class (the `BlockWriter` and `VerdictWriter` pattern). Listings are appended to `LISTINGS` from `inspect_checks.py`, not written inline. The store never imports pydantic. `calibration.py` reads `verdicts` only and writes nothing.

### Data Flow

**Recording a judge sample.** The Judge runs Squadron N times and ingests each saved review. The process applies each one as a `verdict`:

```
amoeba ingest review --artifact F --judge-invocation J …     (×N, one per sample)
  parse_review_artifact(F) → to_verdict_input(…, judge_invocation_id=J) → submit
apply (verdict effect, inside apply_submission's transaction):
  id already recorded?  → no-op (103's replay rule; record_verdict: 104's retry rule)
  104's checks (node, journal entry, provider failure, upstream version)
  J set and an earlier sample of J is on another node or review type?
                                    → rejected, reason names both       ← new
  insert the verdict row with judge_invocation_id = J
```

The D2 check runs last, inside the same transaction as the insert, and only when the id is new. A rejected sample writes nothing, so it never defines an invocation. The first **recorded** sample does: its node and review type are the invocation's.

The Judge can also submit samples it parsed itself with `amoeba submit verdict --judge-invocation-id J`, or through the inbox API.

**The previous round, sample-aware.** 104's lookup gains one skip:

```
_previous_round(target)
  for each earlier verdict on the same node and review type, latest first:
    skip if its standing is not comparable              (104)
    skip if target is a sample and it is a sample of the same invocation   ← new
    return it
```

A sample's previous round can be a sample of an earlier invocation, or an ordinary review of the same type. Ordinary reviews are unaffected.

**Recording a check or a progress record.** In-process callers (the Runner) call `record_check` / `record_progress`. Outside producers submit a `check`; progress records have no inbox kind yet (D6). Both check paths run `CheckWriter`'s checks and insert:

```
record_check(CheckInput)                      # one transaction
  id already recorded? → return it (WARNING if content differs; first wins)
  node exists in this project? → else NodeNotFoundError / rejected
  examined_count, if given, is ≥ 0 → else ValueError / rejected
  upstream_version is not empty    → else ValueError / rejected
  insert the check_results row → trigger appends a check_recorded change
```

`record_progress` is write-only: it checks the node and `upstream_version`, then inserts with `INSERT OR IGNORE` on the id, so a retried id is a no-op. It returns nothing and appends no feed change. Reading the record back, and the first-wins WARNING on differing content, come with the reader (issue #5).

**Calibration** is computed on read from judge-sample rows. See D3.

### State Management

All durable state is in the project store: one new column and two new tables. The check standing and the calibration report are computed from stored rows when asked. Neither is stored, so changing either rule needs no data fix. This matches 104's trust label.

## Technical Decisions

D1, D3 (the descriptive-only part), and D5 carry ratifications from the first draft (20260926). The others are new or changed, and await PM ratification.

### Technology Choices

**D1 — A judge sample is a verdict record with a `judge_invocation_id`.** *(PM ratified 20260926, on condition of clear naming.)* A judge run is a Squadron review with a judge template. Its sample fields (model, run id, score, verdict) are a subset of a verdict's. A separate table would duplicate the provenance columns and split "every verdict" across two tables. The names, used the same way in code, docs, and CLI:

- A **judge invocation** is one request to the Judge for N samples. Its id is `judge_invocation_id`: opaque, supplied by the caller.
- A **judge sample** is a verdict record whose `judge_invocation_id` is set.
- A verdict without one is an ordinary **review verdict**.

**D2 — Samples of one invocation are one question.** *(New, pending.)* An invocation asks one question N times, so every sample of it must be on the same node and of the same review type. The verdict writer checks this against the invocation's earlier samples and rejects a mismatch. Without it, a mistyped id would silently mix two questions into one invocation, and 140's agreement computation over it would be wrong. Samples of one invocation are never each other's previous round, because they are parallel answers, not successive rounds.

D2 adds a check only to verdicts that carry `judge_invocation_id`, a field no shipped verdict has. Verdicts recorded under 104's rules are unaffected.

- *A wrong first sample.* If the first recorded sample has the wrong node or review type, it fixes the invocation that way, and later correct samples are rejected. Samples are never edited, so the remedy is a **new invocation id**. The rejection reason says so, and so does `evidence-contract.md`.
- *The same review under two invocations.* `ingest review`'s default id for a sample includes the invocation (see Retry), so the second invocation gets its own record rather than a silent no-op.

**D3 — The calibration report is descriptive, per review type and model.** *(Descriptive-only ratified 20260926. The columns are new and pending.)* `calibration(project_id)` returns one row per `(review_type, model)` over judge samples:

| Field | Meaning |
| --- | --- |
| `samples` | Judge samples in this group. |
| `invocations` | Distinct invocations with at least one sample in this group. |
| `pass`, `concerns`, `fail`, `unknown` | Samples by verdict. |
| `provider_failures` | Samples whose trust label is `provider_failure`. |
| `score_min`, `score_mean`, `score_max` | Over samples with a score. `null` when none has one. |

`model` is required on every verdict (104: NOT NULL, no default), so every sample has one. The report groups on the stored value as given and never substitutes or drops a row.

**The report carries no agreement data.** It counts and describes each group's samples on their own. It does not compare samples with each other, within an invocation or across models, and it recommends no threshold. Squadron's metrology rule makes escalated-gate verdicts inadmissible as **agreement** data. Agreement is 140's computation, and so is the escalated-gate attribute it must filter on, because 140 defines how judges are invoked and is the only submitter that knows (GitHub issue #4). That attribute arrives with 140's own records and migration. The report must not be consumed as agreement evidence, and `evidence-contract.md` says so. Per-criterion means are deferred (GitHub issue #6).

**D4 — Judge stdout that reports `UNKNOWN` with a score is refused.** *(New, pending. Closes issue #2.)* `parse_review_json` raises `SquadronParseError` when the JSON says `verdict: UNKNOWN` and carries a `score`. The message claims no version: "stdout JSON with a score reports verdict UNKNOWN; ingest the saved review file instead". `amoeba ingest review` exits `REVIEW_UNREADABLE` (12) and submits nothing.

The input has three causes, and the saved file is the right source for each:

- *Squadron before 0.21.9* (squadron#140) put the real verdict only in the file. The file records it.
- *An out-of-range judge score*, which still gives `UNKNOWN` today. The file also says `UNKNOWN`, and ingesting it records an explicit unknown: standing `unparsed`.
- *A non-judge review with no verdict and an incidental score.* Squadron's score extraction is not judge-aware: any review whose output has a top-level `score:` line gets one (`review/parsers.py`, `_extract_score`; observed squadron 0.22.0). So a non-judge review can legitimately report `UNKNOWN` with a score. It is not blocked from ingest: its saved file records the same explicit unknown.

The rule does not test for a judge template, because the only signal is the template's name, and names are never used as logic.

**A deliberate exception to "unknown is a value".** That principle says unparseable input is recorded as explicitly unknown. Here the input is not unknown; it is a stdout capture whose verdict field may be wrong while a better source exists. Recording it would put a possibly wrong verdict in the store. The refusal is not silent: it fails at the ingest boundary with the reason, and the unknown case is still recorded, through the file. `evidence-contract.md` states the exception.

The rule reads the JSON's own fields, never the version label, which is never compared (104). The artifact parser is unchanged.

### Patterns and Conventions

**D5 — A check records what it examined; its standing is derived.** *(PM ratified 20260926.)* `CheckStanding` is computed by one function, checked top to bottom:

| `CheckStanding` | When |
| --- | --- |
| `errored` | the outcome is `errored` |
| `unattested` | `examined_count` was not reported |
| `vacuous` | `examined_count` is 0, whatever the outcome |
| `passed` / `failed` | the outcome |

A failed check that examined nothing is `vacuous` too: it tells you nothing about the code. `baseline_ref` is opaque, for example the SHA of `main` that a result should be compared against. `name` is free data (`cf check`, `pytest`) and is never used as logic.

**D6 — SQ 280's four types map onto records; one new table holds two of them.** *(Pending since 20260926.)* `review_findings` is a verdict plus its observations (104). `checkpoint` is the `blocked_on_sq_checkpoint` node carrying the SQ run id (101). A second home for either would give one fact two records. `task_progress` and `devlog` have no home and no designed consumer, so they go into `progress_records`: a closed `progress_kind`, opaque JSON `content`, and the standard provenance, like 103's message payloads. This is exactly what the slice plan entry assigns: "a small record table with opaque content until a consumer defines their fields". Only the table and a write-only `record_progress(ProgressInput)` are built, so the table has a tested way in. The reader, a `ProgressRecord` type and its row mapping, the inbox kind, the listing, and the feed change are cut until a consumer exists (GitHub issue #5). Store tests write through `record_progress` and read the row back with SQL.

**D7 — Checks get an inbox kind now.** *(New, pending. The first draft deferred it.)* Every check producer that exists today is outside the process: the PM running a validator, CI, the Judge. The Runner, the only in-process writer, does not exist until 120. The kind is the documented three parts: a `SubmissionKind` member (`check`), a payload model, and an effect that calls `CheckWriter` inside `apply_submission`'s transaction. The submission id becomes the record id, as for `verdict`. Progress records get no kind yet (D6).

**D8 — Checks and progress records have their own source vocabulary.** *(New, pending.)* They do not come from Squadron's review output, so they do not use `RecordSource`, which is unchanged. `ToolSource` (`command_output`, `document`) is a separate `StrEnum`. There is still one provenance type: `Provenance` becomes generic over its source vocabulary (`Provenance[RecordSource]` on verdicts, `Provenance[ToolSource]` on checks and progress records), with the same four fields (`upstream`, `upstream_version` required and non-empty and never compared, `source`, `source_path`). Verdicts cannot take a tool source by type, so no guard is needed and 104's verdict rules are unchanged. The provenance column names are shared.

**D9 — The check table gets a change kind; the verdict trigger is unchanged.** *(New, pending.)* 106's rule is that a new table with readers needs a new `ChangeKind`. Migration 007 adds `changes_check_recorded` (payload: `name`, `outcome`, `examined_count`). It carries no standing, for the same reason `verdict_recorded` carries no trust label: it is computed on read. `progress_records` gets no trigger until it has a reader (issue #5); 106's invariant test does not track that table. `verdict_recorded` does not gain `judge_invocation_id`. The Judge supplies its own sample ids and reads each record by `subject_id`, and rewriting a shipped trigger is churn without a consumer.

**Retry.** Checks and samples use 104's rule (progress records: D6): the caller supplies the id; recording an existing id returns the existing record, with a WARNING if the content differs. `ingest review`'s default id for an ordinary review is 105's digest of the parsed review, unchanged. For a sample (`--judge-invocation J`), the default id is that digest followed by `.` and `J`. So the same file twice under one invocation is a no-op, and the same file under a second invocation is a separate sample. 105's digest and `RECORD_ID_FORMAT_TAG` do not change. `evidence-contract.md` states this.

**Word lists** are `StrEnum`s, each defined once in `check_models.py`:

- `CheckOutcome`: `passed`, `failed`, `errored`
- `CheckStanding`: the table above
- `ProgressKind`: `task_progress`, `devlog`

An unknown word fails payload validation and is quarantined. It is never mapped to a near match. Migration 007's trigger literals repeat the `ChangeKind` values, and 106's invariant test ties them together.

**Errors.** Direct calls raise `NodeNotFoundError` or `ValueError` on a failed check, as `record_verdict` does. The inbox effects return a rejection reason for the same checks, tested as plain branches. `check(id)` returns `None` for an unknown id, as `verdict(id)` does.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `verdicts(project_id, *, node_id=None, judge_invocation_id=None)` | 104's method with one more filter. In arrival order. |
| `record_check(CheckInput) -> CheckRecord` | One transaction: retry check, checks, insert. |
| `check(check_id)` / `checks(project_id, *, node_id=None)` | In arrival order. |
| `record_progress(ProgressInput) -> None` | Write-only (D6). A retried id is a no-op. |
| `calibration(project_id) -> list[CalibrationRow]` | D3. Ordered by review type, then model. |

All `record_*` methods take `project_id` as a keyword, as `record_verdict` does.

**Inputs** (frozen dataclasses; records mirror them, plus `project_id`, `recorded_seq`, `recorded_at`):

- `VerdictInput` gains `judge_invocation_id: str | None = None`.
- `CheckInput`: `id`, `node_id`, `name`, `outcome: CheckOutcome`, `examined_count: int | None`, `examined: Mapping | None` (what was checked, opaque), `baseline_ref: str | None`, `provenance: Provenance[ToolSource]`. `CheckRecord` adds a `standing` property.
- `ProgressInput`: `id`, `node_id`, `progress_kind: ProgressKind`, `content: Mapping`, `provenance: Provenance[ToolSource]`. It has no record type yet (D6).

`examined_count` has no default: a submitter passes `null` to say "not reported", as for `findings_parsed`.

**Parser:** `to_verdict_input(…, judge_invocation_id=None)` passes the value through. It is not part of `ParsedReview` and not part of the record-id digest.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba ingest review … [--judge-invocation ID]` | 105's command; sets `judge_invocation_id` on the submitted verdict. Without `--id`, a sample's id is the digest id plus `.ID` (Retry). |
| `amoeba submit verdict … [--judge-invocation-id ID]` | The flag comes from the payload model. |
| `amoeba submit check --project P --by B --node-id N --name NAME --outcome O --examined-count JSON --upstream U --upstream-version V --source S [--examined JSON] [--baseline-ref R] [--source-path PATH] [--id ID]` | Flags from `CheckPayload`. |
| `amoeba inspect verdicts --project P [--node ID] [--judge-invocation ID]` | Gains a `judge_invocation_id` column after `standing`. |
| `amoeba inspect checks --project P [--node ID]` | `recorded_seq, id, node_id, name, outcome, examined_count, standing, baseline_ref, upstream_version` |
| `amoeba inspect calibration --project P` | One row per `(review_type, model)`, D3's fields. |

All listings work whether the process is running or stopped, and accept `--json`.

### Database / Storage Schema

Migration `007_judge_samples_checks_and_progress.sql` sets `EXPECTED_SCHEMA_VERSION` to 7. Nothing to backfill: existing verdicts get `judge_invocation_id` null, which is what they are.

- **`verdicts`:** `ALTER TABLE … ADD COLUMN judge_invocation_id TEXT`. Index on `(project_id, judge_invocation_id)`, for the D2 check and the filter.
- **`check_results`:** `recorded_seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `id` (UNIQUE), `project_id`, `node_id` (FK), `name`, `outcome`, `examined_count` (INTEGER, nullable), `examined` (JSON text, nullable), `baseline_ref`, `upstream`, `upstream_version`, `source`, `source_path`, `recorded_at`. Index on `(project_id, node_id, recorded_seq)`.
- **`progress_records`:** `recorded_seq`, `id` (UNIQUE), `project_id`, `node_id` (FK), `progress_kind`, `content` (JSON text), the four provenance columns, `recorded_at`. Index on `(project_id, node_id, recorded_seq)`.
- **Trigger:** `changes_check_recorded`, AFTER INSERT, written as 006 writes them. `recorded_at` is copied from the row. `progress_records` has none (D9).

No CHECK constraints on vocabulary columns, as in 005 and 006. Column names are defined once, in `sql_checks.py`, and the `verdicts` addition in `sql_evidence.py`.

## Integration Points

### Provides to Other Slices

- **108:** migration number 008 follows this one. 108 adds its own `ChangeKind` by the same trigger convention.
- **109:** the new listings, which 109 moves into `amoeba.inspection` with the rest. The `check` kind, which the network surface accepts like any other submission.
- **110:** judge samples, checks, and progress records in the end-to-end contract proof.
- **Initiative 120:** `record_check` and `record_progress` in-process, and `CheckStanding` for routing.
- **Initiative 140:** judge samples through `verdict` with `judge_invocation_id`, `verdicts(…, judge_invocation_id=)` to read an invocation back, and `calibration` as its evidence source. Consensus records join through the kind seam when 140 designs them.

### Consumes from Other Slices

Changes to earlier contracts, each recorded in the contract docs and `CHANGELOG.md`:

- **104:** `VerdictInput` and the `verdict` payload gain an optional field. The previous-round lookup gains the sample skip. The verdict writer gains one check (D2), which applies only to verdicts carrying the new field. `RecordSource` is unchanged (D8). `inspect verdicts` gains a column, so the test pinning its columns is updated.
- **105:** `parse_review_json` refuses one more input (D4). `to_verdict_input` and `ingest review` gain one optional argument. The record-id digest is unchanged, so no `RECORD_ID_FORMAT_TAG` bump; a sample's default id appends the invocation to it.
- **106:** one `ChangeKind` member and trigger. The invariant test's scripted sequence gains a check.
- **103:** one `SubmissionKind` member. 103's completeness tests cover it.
- **102:** two listings appended to `LISTINGS`. The pinned-registry test is updated.

## Success Criteria

### Functional Requirements

- Three judge samples sharing a `judge_invocation_id` are three verdict records, each with its own model, run id, score, and verdict. `verdicts(…, judge_invocation_id=J)` returns exactly those three, in arrival order.
- A sample whose invocation already has samples on another node, or of another review type, fails when recorded directly and is rejected through the inbox, with a reason naming both and saying to use a new invocation id. A rejected first sample leaves the invocation undefined, so a correct sample after it is recorded.
- Ingesting one judge file under invocations `j1` and `j2` gives two samples. Ingesting it twice under `j1` gives one.
- `finding_changes` on a sample never names a sample of its own invocation as the previous round. It can name a sample of an earlier invocation. An ordinary review's previous round is unchanged.
- `calibration` returns one row per `(review_type, model)`, with the counts D3 defines and no field comparing samples with each other. An `UNKNOWN` sample is counted in `unknown`. Score statistics ignore samples without a score.
- Nothing in `src/` references Squadron's metrology directory or config key (a test asserts it), and `calibration` issues no write.
- A check with `examined_count=0` and outcome `passed` has standing `vacuous`. So does one with outcome `failed`. A check with `examined_count` null has standing `unattested`. An `errored` outcome is `errored` whatever the count.
- A negative `examined_count` fails directly and is rejected through the inbox.
- `record_progress` writes a row whose content reads back unchanged (through SQL in the test). A retried id writes nothing.
- Recording a check or verdict with an existing id returns the existing record, writes nothing, and logs a WARNING if the content differs.
- Every check and progress record carries a non-empty `upstream_version`. Recording one without it fails.
- Recording a check appends exactly one `check_recorded` change. A retried check appends none. Recording a progress record appends none.
- The real judge artifact in `tests/fixtures/sq_reviews/` parses to its stated verdict, score, and criteria. Ingested with `--judge-invocation`, it is a judge sample.
- `parse_review_json` on a judge capture with `verdict: UNKNOWN` and a score raises `SquadronParseError`, with a message that names the saved file and no Squadron version. `amoeba ingest review --stdout-json` on it exits 12 and leaves nothing in `inbox/new/`. A capture with a real verdict and a score parses.

### Technical Requirements

- Each word list is a `StrEnum` defined once. All SQL and column names for the new tables live in `sql_checks.py`. The check standing has one function. `ToolSource` is separate from `RecordSource`, and `Provenance` is one generic type over both.
- A store at version 6 with nodes, verdicts, findings, changes, watches, and detections upgrades to 7 with all of them intact, and its existing verdicts read back with `judge_invocation_id` null.
- 106's feed invariant test passes with the two new kinds in its sequence, and fails if either trigger is missing.
- The judge fixture is a real Squadron artifact from a pipeline run on squadron 0.21.9 or later, captured at implementation time in a throwaway copy of a repository. The fixture README records the command, the Squadron version, and the date. The D4 refusal test uses a real stdout capture with its verdict edited to `UNKNOWN` and a score added, labelled as edited in the README, like the existing `findings-not-parsed-edited` fixture.
- The writer guard is not weakened. No new permitted scripts.
- `ruff`, `pyright` strict, and the full suite are clean. Source files stay near 300 lines.
- `docs/evidence-contract.md` gains sections on judge samples (names, D2 and its new-invocation remedy, previous-round skip, sample ids), calibration (D3, what it does not do, and that it must not be consumed as agreement evidence, citing issues #4 and #6), checks (D5), progress records (D6, citing issue #5), and the D4 refusal as a stated exception to "unknown is a value". `inbox-contract.md` documents the `check` kind, `feed-contract.md` the `check_recorded` change kind, `store-contract.md` the new methods. GitHub issue #2 is closed with a pointer to D4.

### Integration Requirements

- End to end through the real CLI as subprocesses: create a project, seed a node, ingest a judge artifact under one invocation, submit two more samples and a check through `amoeba submit`, `kill -9`, and `start`. Read-only inspection then shows three samples, a calibration row, a `vacuous` check, and nothing applied twice. `amoeba feed` shows one change for each record.
- `docs/evidence-contract.md` is enough for an initiative 140 slice design to proceed without reading the code.

### Verification Walkthrough

Draft; it is refined with real output when Phase 6 is complete. Run in **bash** from the repository root (`$BASE` relies on word splitting; in zsh use `${=BASE}`). `scripts/demo_evidence.py` (104) seeds one node in the `demo` project and prints its id. The judge fixture's filename is settled at capture; `$JUDGE` below stands for it.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
uv run amoeba submit create-project --project demo --by pm
uv run amoeba stop
NODE=$(uv run python scripts/demo_evidence.py)
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
JUDGE=tests/fixtures/sq_reviews/<judge fixture>.md
```

**1. A real judge sample.**

```bash
uv run amoeba ingest review --project demo --node "$NODE" --by judge \
  --artifact "$JUDGE" --judge-invocation j1
uv run amoeba inspect verdicts --project demo --judge-invocation j1
```

Expected: one row with review type `judge.slice-vs-arch`, the file's verdict and model, standing `unattested` (judges carry no `verdictSource`), and `judge_invocation_id` `j1`. `--json` shows its `score` and `criteria`.

**2. More samples stay separate.** Submit two built samples in the same invocation: the same review type, the second model twice, one PASS and one CONCERNS.

```bash
BASE="--project demo --by judge --node-id $NODE --review-type judge.slice-vs-arch \
  --upstream squadron --upstream-version 0.22.0 --source artifact_frontmatter \
  --provider-failure false --fallback-used null --findings-parsed true \
  --derivation not_reported --judge-invocation-id j1"
uv run amoeba submit verdict $BASE --id s2 --model model-b --verdict PASS --score 81 --findings '[]'
uv run amoeba submit verdict $BASE --id s3 --model model-b --verdict CONCERNS --score 62 --findings '[]'
uv run amoeba inspect calibration --project demo
```

Expected: `inspect verdicts --judge-invocation j1` lists three rows. `inspect calibration` shows two rows. The `model-b` row has `samples` 2, `invocations` 1, `pass` 1, `concerns` 1, and `score_min` 62, `score_max` 81.

**3. A sample on the wrong node is refused.** Seeding a second node needs the process stopped (`demo_evidence.py` takes the lock). Instead, submit a sample of `j1` with `--review-type slice`.

Expected: `inspect submissions --project demo` shows it `rejected`, with a reason naming `j1`'s review type.

**4. A vacuous check is not a pass.**

```bash
CHECK="--project demo --by pm --node-id $NODE --upstream cf \
  --upstream-version 0.0.0-demo --source command_output"
uv run amoeba submit check $CHECK --id c1 --name validate --outcome passed --examined-count 12
uv run amoeba submit check $CHECK --id c2 --name validate --outcome passed --examined-count 0
uv run amoeba submit check $CHECK --id c3 --name validate --outcome passed --examined-count null
uv run amoeba inspect checks --project demo
```

Expected standings: `c1` `passed`, `c2` `vacuous`, `c3` `unattested`.

**5. Judge stdout reporting `UNKNOWN` with a score is refused.**

```bash
uv run amoeba ingest review --project demo --node "$NODE" --by judge \
  --stdout-json tests/fixtures/sq_reviews/<edited judge stdout>.json; echo "exit $?"
```

Expected: the stderr message points at the saved file, `exit 12`, and nothing new appears under the project's `inbox/new/`.

**6. Retry, restart, and the feed.** Re-run step 1's ingest and resubmit `c2`, then `kill -9` the process and start it again.

Expected: `inspect verdicts --json` and `inspect checks --json` are byte-identical before and after. `uv run amoeba feed --project demo --after 0` shows one `check_recorded` per check and one `verdict_recorded` per sample, with no repeats.

**7. The tests.** Progress records have no CLI surface yet (issue #5); their store tests run here.

```bash
uv run pytest tests/store/test_checks.py tests/store/test_calibration.py \
  tests/store/test_feed_invariant.py tests/upstream -v
```

Expected: the standing table, the calibration counts, the invariant test with the new kinds, and the judge fixture and refusal tests all pass. The same flow runs automatically in the end-to-end CLI test.

## Implementation Notes

### Development Approach

1. Capture the judge fixture (a PM step: a pipeline run in a throwaway copy of a repository) and write its README entry. The parser test against it and the D4 refusal follow.
2. `check_models.py` with the standing function and its table-driven test. `ToolSource`, and `Provenance` made generic (104's tests unchanged).
3. Migration 007, `sql_checks.py`, mapping, `CheckWriter`, `CheckOperations`, and the 6 → 7 upgrade test.
4. `judge_invocation_id` through `VerdictInput`, the payload, the writer's D2 check, `verdicts`' filter, and the previous-round skip.
5. `calibration` and its tests.
6. The `check` kind, extending 103's completeness tests. The feed trigger and the invariant test's new step.
7. `ingest --judge-invocation` and the sample id, the listings, and the pinned-registry and column tests.
8. The end-to-end CLI test, the docs, the CHANGELOG, and closing issue #2.

Test each step right after building it. Commit after each step.

### Special Considerations

- **The metrology constraint is permanent.** The calibration report counts and summarizes. It never writes outside the project store and never reads Squadron's metrology store. Recommending thresholds to the PM is 140's.
- **The trust label of judge samples is `unattested`** because Squadron omits `verdictSource` for score-decided verdicts. If Squadron starts stamping one, the label follows with no change here. `evidence-contract.md` says so, so 140 does not read `unattested` as "untrustworthy".
