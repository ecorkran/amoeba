---
docType: slice-design
slice: findings-verdicts-and-provenance
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103]
interfaces: [105, 106]
dateCreated: 20260926
dateUpdated: 20260926
status: not_started
---

# Slice Design: findings-verdicts-and-provenance

## Overview

Slices 101–103 give Amoeba a node tree, a process that owns it, and a way for outside parts to write to it. None of that holds any *evidence*: when a review runs, nothing records what it said, where the verdict came from, or whether the verdict can be trusted. This slice adds the evidence layer:

1. **Verdict records.** Each review outcome is stored with full provenance: verdict, how the verdict was reached, whether the artifact was a provider-failure placeholder, reviewed SHA, model, template, judge score and criteria, SQ run id, and the upstream version label.
2. **Finding observations with content identity.** Each finding in a verdict is stored as an observation, keyed by a documented normalization of its location and summary. Squadron's positional `F001` is kept as data only.
3. **Per-iteration finding status.** For any verdict, the store answers which findings are new, which recur from the previous round, and which are gone.
4. **Judge samples and a calibration report.** Every judge invocation is its own verdict record. A read-only report groups them by template and model. Nothing is written back to Squadron.
5. **Mechanical check results** that record what was examined, so a check that ran against nothing is distinguishable from one that passed.
6. **The SQ 280 typed-artifact scope**, mapped onto these records rather than duplicated.

A `verdict` inbox kind lets the out-of-process Judge submit. New inspection listings make all of this visible without writing a client.

## Value

Developer value, and the unblocker for initiative 140. After this slice:

- The Runner (120) can ask "is this the same finding as last round?" and "is this PASS trustworthy?" from the store alone. Neither CF's gate nor Squadron's output answers either question.
- A derived PASS, a PASS with no findings behind it, and a provider-failure placeholder are separate values, not a single `PASS` string. CF's gate cannot tell these apart, and neither can a frontmatter reader that ignores `verdictSource`.
- The Judge (140) has somewhere to put N samples per invocation and a report to read them back from. That is the substrate half of consensus.
- A validator that exits 0 having checked zero files (cf#87/#88) is recorded as *vacuous*, not *passed*.
- Every ingested fact says which upstream produced it and at what version label, so a shape change upstream can be traced to the records it affected.

## Technical Scope

**Included**

- Store additions: migration `005`, and four tables: `verdicts`, `finding_observations`, `check_results`, `evidence_artifacts`.
- `amoeba.store.finding_identity`: the normalization rule and identity function. Pure functions, exported, versioned.
- Closed vocabularies for verdict, finding severity, verdict derivation, record source, check outcome, evidence-artifact kind, and the two derived classifications (`VerdictStanding`, `CheckStanding`).
- Store operations: `record_verdict`, `record_check`, `record_artifact`, and the read queries listed under API Contracts, including `finding_changes` and `calibration`.
- The `verdict` submission kind (enum member, payload model, effect), so the out-of-process Judge can write.
- A widened `amoeba submit` flag-typing rule so kinds with number, boolean, and list fields get CLI flags (D9).
- Five inspection listings (`verdicts`, `findings`, `checks`, `artifacts`, `calibration`) registered into 102's registry, plus one additive registry feature: value-taking options.
- Real Squadron review artifacts copied into `tests/fixtures/sq_reviews/` as the normalization rule's test input.
- `docs/evidence-contract.md`, and updates to `store-contract.md`, `inbox-contract.md`, and `CHANGELOG.md`.

**Excluded**

- **Parsing Squadron output** (stdout JSON or artifact frontmatter). The architecture assigns parsing to the Runner's control surface (initiative 120). The store takes typed records (D1).
- **"Same finding, reworded."** That is a Tier-2 judgment for initiative 140. The store matches formatting drift only (D2).
- **Finding dispositions** (`addressed`, `disputed`, accepted/rejected by a human) and **consensus results**. These are judgments owned by 140 and 120. They land through the kind seam when those initiatives design them.
- **Tier inference** on findings. That is 120's routing, pending Squadron dependency S1.
- **Detecting** review artifacts written by runs Amoeba did not launch. That is slice 105.
- Any write into Squadron's metrology store, and any threshold mutation. These are permanent Squadron constraints.
- Resolving `blocked_on_judge` nodes when a judge verdict arrives. A verdict is evidence; resolution stays an explicit act by the Runner or Judge through the existing `resolution` kind.
- Retention of verdicts and observations. Already Future Work in the slice plan.

## Dependencies

### Prerequisites

- **Slice 101:** `Store`, node records, the migration mechanism (`EXPECTED_SCHEMA_VERSION` goes from 4 to 5), and the typed failure modes.
- **Slice 102:** the inspection listing registry (`cli/inspect.py`, `Listing`), `Store.open_read_only`, the command journal (a verdict may reference the `SQ_RUN` entry that produced it), and the writer guard.
- **Slice 103:** the submission-kind seam (a `SubmissionKind` member, a `KIND_PAYLOAD_MODELS` entry, and a `KIND_EFFECTS` entry), `amoeba submit`, and the D2 idempotency pattern this slice reuses for record ids. The slice plan lists only [101, 102]. 103 is added here because the Judge's write path is 103's inbox.
- **PyYAML (dev dependency only)**, with its type stubs, so tests read the real artifact fixtures' frontmatter as YAML rather than through a hand-rolled reader. No new runtime dependency.

### Interfaces Required

From the store: `get_node`, `journal_entry`, the `_execute` error translation, and the single-transaction pattern `apply_submission` uses. From the inbox: `validate_envelope` → `KIND_PAYLOAD_MODELS[kind]`, and the `_Application` value passed to an effect. From the CLI: `LISTINGS`, `run_listing`, and `_takes_object` in `cli/submit.py`.

**Upstream ground truth, observed 20260926 against Squadron `4748b63c` (package 0.14.0).** Recorded as a dated observation, not a pinned version:

- `structured_findings[]` / frontmatter `findings:` entries are `{id, severity, category, summary, location}`. `id` is `F{i:03d}` by enumeration order. `severity` is lowercase. A missing location is the literal `unverified`.
- `verdictSource: stated | derived` is now emitted in both JSON and frontmatter (SQ slice 927 plans a third value, `imposed`). `fallback_used` is JSON-only. It is true for a derived verdict, and also for a CONCERNS/FAIL with zero parsed findings, where `verdictSource` stays `stated`.
- A provider failure writes `verdict: UNKNOWN` with no `verdictSource` into the normal artifact slot. It is marked only by a `## Provider Failure` body section.
- No Squadron output carries a run id or the Squadron version. A run file points at its review artifact; the artifact does not point back.
- Judge artifacts carry `score` (0–100) and `criteria`. The judge's verdict is always score-derived.

## Architecture

### Component Structure

```
src/amoeba/
  store/
    finding_identity.py     normalize_location, normalize_summary, finding_identity; IDENTITY_RULE_VERSION
    evidence_models.py      vocabularies, input and record dataclasses, standing classification
    sql_evidence.py         every statement and column name for the four tables
    mapping_evidence.py     row → record mapping (raises on an unknown enum value)
    verdicts.py             VerdictOperations: record_verdict, verdict(s), observations, findings, finding_changes
    checks.py               CheckOperations: record_check, checks; record_artifact, artifacts
    calibration.py          calibration(project_id) — read-only aggregation
    schema/005_findings_verdicts_and_provenance.sql
  inbox/
    evidence_payloads.py    VerdictPayload, FindingPayload (pydantic) → VerdictInput
  cli/
    inspect_evidence.py     row functions and Listing entries for the five listings
tests/fixtures/sq_reviews/  real Squadron review artifacts, unmodified, with README provenance
docs/evidence-contract.md
```

This follows the per-concern pattern 101–103 set: models, SQL, mapping, and an operations mixin added to `Store`'s bases. `evidence_models.py` is split if it passes the ~300-line budget. `store.py` (301), `cli/inspect.py` (281), and `cli/main.py` (251) are already near budget. The listing registrations therefore live in `inspect_evidence.py` and are concatenated into `LISTINGS`, not written inline.

**Dependency direction** is unchanged. `amoeba.inbox` converts its pydantic payload into the store's plain `VerdictInput`. The store never imports pydantic models from the inbox. `finding_identity.py` imports nothing from the store, so 105, 120, and 140 can compute an identity without opening one.

### Data Flow

**Record a verdict** (the in-process Runner calls it directly; the Judge goes through the inbox):

```
record_verdict(VerdictInput)                    # one transaction
  id already recorded?          → return the existing record (first wins; WARNING if content differs)
  node exists in this project?  → else raise (direct) / rejected (inbox)
  journal_entry_id, if given, is on the same node → else raise / rejected
  provider_failure ⇒ verdict UNKNOWN and no findings → else raise / rejected
  INSERT verdicts row  (recorded_seq assigned here: receiver order)
  for each finding, in submitted order:
      identity = finding_identity(location, summary)    # rule v1
      INSERT finding_observations row  (raw fields + normalized fields + identity + rule version)
  return VerdictRecord
```

Through the inbox, the `verdict` kind's effect calls the same private writer inside `apply_submission`'s transaction, with the submission id as the record id. A precondition failure is returned as a rejection reason, following 103's "rejection is a recorded outcome" convention. An unknown enum value never reaches the effect: payload validation fails first, and the file is quarantined as `invalid_payload`.

**Finding changes for a verdict** (read-time, D3):

```
finding_changes(verdict_id)
  target   = verdict(verdict_id);  if not comparable(target) → FindingChanges(comparable=False)
  baseline = latest verdict with: same node_id, same template, lower recorded_seq,
             comparable standing, and not in target's judge_group (when it has one)
  for each target observation: RECURRING if its identity is in baseline's identities, else NEW
  ABSENT   = baseline identities not in target's identities
```

A verdict is *comparable* when its standing is `stated`, `derived`, or `unattested`. A provider failure, an unparsed verdict, or a CONCERNS/FAIL with no findings behind it is never a baseline and never has changes. Otherwise a failed round would report every open finding as fixed.

### State Management

All durable state is in the project store, in the four new tables. Nothing new lives in memory or in the supervisor directory. Finding status, verdict standing, check standing, and the calibration report are derived on read from stored rows. None is stored, so changing a derivation rule never needs a data migration.

## Technical Decisions

D1–D9 are proposals a reasonable Project Manager could decide differently. **All nine await PM ratification.**

### Technology Choices

**D1 — The store takes typed records; this slice parses nothing from Squadron. (PM — pending)** The architecture puts parsing Squadron JSON and frontmatter in the Runner's control surface (120), not the substrate. The store's contract is `VerdictInput` and friends: already-parsed, already-typed values. What this costs: the slice-plan criterion "normalization tested against real Squadron finding text" is met by feeding real artifact fields into the normalization function in tests, not through a production parser. *Consequence for slice 105:* detecting a PM-launched review and ingesting it needs an artifact reader. 105's design decides whether that reader lives in 105 or in a shared module 120 also uses. This slice does not pre-build it.

**D2 — Finding identity is normalized location (without line references) plus normalized summary. Severity and category are excluded. (PM — pending)** The architecture's principle names severity, location, and summary. This proposal drops severity, for two reasons:

- *Severity is the reviewer's grade of an issue, not the issue.* In the captured 102 task-review series, a finding was regraded from `concern` to `note` between rounds. Keying on severity would report a regrade as one finding fixed and a different one raised.
- *Category is free-form* (`"uncategorized"` when missing) and model-assigned per run. The architecture forbids routing on it, and identity is routing's input.

Line references are stripped from locations because line numbers shift every round. That is why Squadron's own 305 screen avoids fuzzy location matching and needs an exact location to match.

What this rule does **not** do, stated plainly in the contract: match a reworded finding. The same captured series shows every carried-over finding reworded between rounds, for example *"The GRACE_EXPIRED exit criterion has no CLI-level test…"* becoming *"GRACE_EXPIRED → next-start recovery not tested as a distinct scenario"*. Under this rule those are two identities. That is correct for a store: "same issue, different words" is a judgment for 140, and the test suite pins this boundary with the real text. What the rule does catch is formatting drift (whitespace, backticks, case, trailing punctuation, moved line numbers) and a finding re-emitted at a different position, which is what positional ids break.

*Alternatives considered.* Squadron 305's exact `(location, category)` match was rejected because it depends on category and line-exact location. Metrology's hash over `(severity, category, summary, location)` was rejected because it depends on both excluded fields. Neither is a canonical normalization to reuse, which answers the slice plan's open question to sq-base. Two different findings with the same summary in the same file collapse to one identity. That is accepted and documented: both observations are still stored, and the collision shows up as a repeated identity within one verdict.

**D3 — Per-iteration finding status is computed on read, not stored. (PM — pending)** Status (`new` / `recurring` / `absent`) is a set difference between a verdict's identities and its baseline's. Storing it would duplicate what observations already say, and would make every rule change (baseline selection, identity version) a data migration. The query is bounded by one node's verdicts for one template, which is small.

**D4 — A judge sample is a verdict record; samples of one invocation share a `judge_group`. (PM — pending)** A judge run is an `sq review` with a judge template, and its sample fields (model, run id, score, verdict) are a subset of a verdict record's. A separate table would duplicate the provenance columns and split "every verdict" across two tables. `judge_group` is an opaque caller-supplied id. Samples in the same group are recorded individually and never collapsed, and they are excluded from each other's baselines. The consensus result is 140's computation and is not stored here.

**D5 — Verdict and check standing are closed, derived classifications. (PM — pending)** Each record exposes a `standing` computed from its stored fields by one function defined once. This is a deterministic predicate over data, like `BLOCKED_STATUSES`, not a decision: the substrate does not say whether to trust a PASS. It names which case the PASS is.

| `VerdictStanding` | Rule, evaluated top-down |
| --- | --- |
| `provider_failure` | `provider_failure` is true |
| `unparsed` | `verdict` is `UNKNOWN` |
| `findings_missing` | `verdict` ∈ {CONCERNS, FAIL} and zero findings recorded |
| `derived` | `derivation` is `derived`, or `fallback_used` is true |
| `unattested` | `derivation` is `not_reported` and `fallback_used` is not reported (for example, frontmatter written before `verdictSource` existed) |
| `stated` | everything else |

`findings_missing` is checked before `derived` because Squadron sets `fallback_used` for both cases. The stored findings tell them apart, even from frontmatter, which lacks `fallback_used`. The slice plan's false-negative predicate (`verdict == PASS && fallback_used`) is `verdict == PASS and standing == derived`.

| `CheckStanding` | Rule, evaluated top-down |
| --- | --- |
| `errored` | outcome is `errored` |
| `unattested` | `examined_count` not reported |
| `vacuous` | `examined_count` is 0 |
| `passed` / `failed` | the outcome |

**D6 — SQ 280's four types map onto records; only two need a new table. (PM — pending)** SQ 280 gave its types one-line descriptions and no fields. `review_findings` is a verdict plus its observations. `checkpoint` is the existing `blocked_on_sq_checkpoint` node carrying the SQ run id (101). Duplicating either would give the same fact two homes. `task_progress` and `devlog` have no existing home and no designed consumer, so they land in one `evidence_artifacts` table with a closed `kind`, opaque JSON `content`, and the standard provenance, like 103's message payloads. Their fields are specified when a consumer designs them.

### Patterns and Conventions

**D7 — Caller-supplied record ids make every record idempotent. (PM — pending)** This is 103's D2 applied to direct calls. Each input carries an `id`. Recording an id that already exists returns the existing record unchanged, and differing content is logged at WARNING (first wins). The Runner can generate the id when it journals the command, so re-ingesting after a crash between "run finished" and "verdict recorded" writes nothing twice. A verdict arriving through the inbox uses its submission id, so there is one id per fact. Slice 105 can derive a deterministic id from an artifact's bytes to make re-detection a no-op.

**D8 — Upstream version is a required opaque label, never compared. (PM — pending)** Every record carries `Provenance(upstream, upstream_version, source, source_path)`. `upstream_version` must be non-empty. The caller supplies whatever the upstream reports (for Squadron, `sq --version`, since no output carries it), and no code branches on or compares it. This matches the existing observers' treatment of `cf --version` and the standing rule that upstream versions are moving targets. `upstream` is free data (`squadron`, `context-forge`), never logic. `source` is closed: `stdout_json`, `artifact_frontmatter`, `command_output`, `document`.

**D9 — `amoeba submit` types flags by one rule: strings and enums are raw, everything else is JSON. (PM — pending)** 103's `_takes_object` accepts only `str`, `str | None`, and `dict`, and raises at parser build otherwise. That rule was added in 103's review for exactly this reason: a kind with other field types should fail loudly, not be mistyped. The `verdict` kind has booleans, numbers, and a findings list, so the rule widens to:

- A `str`, `StrEnum`, or optional of either takes the flag's text as is.
- Every other annotation takes the text as a JSON value (`--score 82.5`, `--fallback-used null`, `--findings '[…]'`).

Pydantic validates the result either way. The existing parametrized tests are extended rather than replaced.

**Vocabularies.** These are `StrEnum`s defined once in `evidence_models.py`:

- `ReviewVerdict` (`PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`)
- `FindingSeverity` (`pass`, `note`, `concern`, `fail`)
- `VerdictDerivation` (`stated`, `derived`, `not_reported`)
- `RecordSource`
- `CheckOutcome` (`passed`, `failed`, `errored`)
- `EvidenceArtifactKind` (`task_progress`, `devlog`)
- `FindingRecurrence` (`new`, `recurring`, `absent`)
- `VerdictStanding` and `CheckStanding`

Payload validation matches verdict and severity case-insensitively, because Squadron emits severity lowercase in `structured_findings` and uppercase in `findings[]`. An unknown value, such as a future `imposed` derivation, fails validation and is quarantined visibly. It is never mapped to a near neighbour. Squadron's `unverified` location literal is defined once in `finding_identity.py`.

**Unknown is a value.** `derivation` and `fallback_used` are required in the payload with explicit not-reported values (`not_reported`, `null`), so a submitter cannot omit them by accident.

**Error handling.** Direct store calls raise `InvalidTransitionError` or `ValueError` on precondition failures, consistent with `block()`. The inbox effect returns a rejection reason for the same conditions, checked as explicit branches, never by catching the exception.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `record_verdict(VerdictInput) -> VerdictRecord` | One transaction: id replay check, preconditions, verdict row, one observation row per finding. |
| `record_check(CheckInput) -> CheckRecord` | Same pattern, for a mechanical check. |
| `record_artifact(EvidenceArtifactInput) -> EvidenceArtifactRecord` | Same pattern, for `task_progress` / `devlog`. |
| `verdict(verdict_id)` / `verdicts(project_id, *, node_id=None)` | In `recorded_seq` order. |
| `observations(verdict_id)` | That verdict's findings, in submitted order. |
| `findings(project_id, *, node_id=None)` | One row per identity: node, latest severity and summary, first/last seen verdict, times seen. |
| `finding_changes(verdict_id) -> FindingChanges` | `comparable`, `baseline_verdict_id`, and observations tagged `new`/`recurring` plus `absent` identities (see Data Flow). |
| `checks(project_id, *, node_id=None)` / `artifacts(project_id, *, node_id=None, kind=None)` | In `recorded_seq` order. |
| `calibration(project_id) -> list[CalibrationRow]` | Per `(template, model)` over judge-scored verdicts: sample count, count by standing, count by verdict, score min/mean/max, and the number of judge groups whose samples disagree on verdict. Read-only; descriptive only. |

**`VerdictInput`** (frozen dataclass): `id`, `node_id`, `verdict`, `derivation`, `fallback_used: bool | None`, `provider_failure: bool`, `template`, `model`, `reviewed_sha | None`, `score: float | None`, `criteria: Mapping | None`, `tool_calls_made: int | None`, `sq_run_id | None`, `journal_entry_id | None`, `judge_group | None`, `findings: Sequence[FindingInput]`, `provenance: Provenance`.

**`FindingInput`**: `positional_id | None` (Squadron's `F001`, stored as data), `severity`, `category | None`, `summary`, `location | None`.

**`CheckInput`**: `id`, `node_id`, `name` (free data), `outcome`, `examined_count: int | None`, `examined: Mapping | None` (what was checked, opaque), `baseline_ref | None` (opaque, for example the SHA of `main` the result should be diffed against), `provenance`.

**`EvidenceArtifactInput`**: `id`, `node_id`, `kind`, `content: Mapping`, `provenance`.

Records are frozen dataclasses mirroring their inputs, plus `project_id`, `recorded_seq`, `recorded_at`, and a `standing` property where one applies.

**Identity (`amoeba.store.finding_identity`, rule v1):**

| Step | `normalize_summary` | `normalize_location` |
| --- | --- | --- |
| 1 | Unicode NFKC | `None`, empty, or `unverified` (any case) → `""` |
| 2 | Remove backticks | Unicode NFKC; `\` → `/`; strip a leading `./` |
| 3 | Casefold | Remove line references wherever they appear: `:N`, `:N-M`, `:N:C`, `#LN`, `#LN-LM`, and `, line N` forms |
| 4 | Collapse whitespace runs to one space; trim | Collapse whitespace; trim. **No casefold** (paths are case-sensitive) |
| 5 | Strip trailing `.`, `;`, `:` | — |

`finding_identity(location, summary)` = hex SHA-256 of `"v1" ␟ normalize_location(location) ␟ normalize_summary(summary)`. Each observation stores `identity_version`. Comparisons run only within one version. The raw fields are kept, so a later v2 can be computed for old rows by a migration.

**Inbox, the `verdict` kind:** the payload is `VerdictInput`'s fields flattened. `provenance` becomes `upstream`, `upstream_version`, `source`, and `source_path`, and the record id is the submission id. The effect checks the preconditions listed under Data Flow.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba submit verdict --project ID --by NAME --node-id ID --verdict V --derivation D --fallback-used JSON --provider-failure JSON --template T --model M --findings JSON --upstream U --upstream-version V --source S [optional fields…] [--id ID]` | Flags derived from `VerdictPayload` under D9. |
| `amoeba inspect verdicts --project ID [--node ID]` | `recorded_seq, id, node_id, template, model, verdict, standing, score, judge_group, upstream_version` |
| `amoeba inspect findings --project ID [--node ID]` | Identities (`findings()`). With `--verdict ID`: that verdict's observations tagged `new`/`recurring`, then `absent` identities, with the baseline id in a header line. |
| `amoeba inspect checks --project ID [--node ID]` | `recorded_seq, id, node_id, name, outcome, examined_count, standing, baseline_ref` |
| `amoeba inspect artifacts --project ID [--kind K]` | `recorded_seq, id, node_id, kind, upstream, recorded_at` |
| `amoeba inspect calibration --project ID` | One row per `(template, model)`. |

All listings accept `--json`. `--node`, `--verdict`, and `--kind` need a value, which the registry does not support today (only booleans and choices). `Listing` gains a `value_options` field of `ValueOption(flag, help_text)` entries, and `_add_inspect_parser` adds them generically. This is the one edit to 102's CLI plumbing, and it is additive.

### Database / Storage Schema

Migration `005_findings_verdicts_and_provenance.sql`, `EXPECTED_SCHEMA_VERSION` → 5. No backfill: no evidence exists before this slice.

- **`verdicts`**:
  - Ordering and identity: `recorded_seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `id` (UNIQUE), `project_id`, `node_id` (FK), `journal_entry_id` (nullable FK), `judge_group` (nullable).
  - The review itself: `verdict`, `derivation`, `fallback_used` (INTEGER nullable), `provider_failure` (INTEGER), `template`, `model`, `reviewed_sha`, `score` (REAL), `criteria` (JSON text), `tool_calls_made`, `sq_run_id`.
  - Provenance: `upstream`, `upstream_version`, `source`, `source_path`, `recorded_at`.
  - Indexes on `(project_id, node_id, template, recorded_seq)` (baseline lookup) and `(project_id, judge_group)`.
- **`finding_observations`**: `verdict_id` (FK), `ordinal`, `positional_id`, `severity`, `category`, `summary`, `location`, `normalized_location`, `normalized_summary`, `identity`, `identity_version`. PRIMARY KEY `(verdict_id, ordinal)`. Index on `(identity)`.
- **`check_results`**: `recorded_seq`, `id` (UNIQUE), `project_id`, `node_id` (FK), `name`, `outcome`, `examined_count`, `examined` (JSON text), `baseline_ref`, then provenance columns and `recorded_at`.
- **`evidence_artifacts`**: `recorded_seq`, `id` (UNIQUE), `project_id`, `node_id` (FK), `kind`, `content` (JSON text), then provenance columns and `recorded_at`.

The provenance column names are defined once in `sql_evidence.py` and shared by the three record tables.

## Integration Points

### Provides to Other Slices

- **105:**
  - `record_verdict` as the ingest target for detected reviews.
  - `provider_failure` and the standing table for "a failure artifact is a failure, not a review".
  - D7 for making re-detection idempotent.
  - `recorded_seq` on the three record tables as change sources for the feed.
- **106:** verdict ingestion for a journaled Squadron run (via `journal_entry_id`) in the end-to-end proof.
- **Initiative 120:**
  - `record_verdict`, `record_check`, and `record_artifact` in-process.
  - `finding_changes`, and the `standing` of verdicts and checks, for routing.
  - `finding_identity` for its own lookups.
- **Initiative 140:**
  - The `verdict` inbox kind for judge samples, with `judge_group`.
  - `verdicts(...)` and `calibration(...)` as its evidence source.
  - The kind seam, for adding dispositions and consensus records when 140 designs them.

### Consumes from Other Slices

These consume 101–103 through their documented contracts. Recorded changes to them go in `docs/store-contract.md`, `docs/inbox-contract.md`, and `CHANGELOG.md`:

- `store-contract.md` drops its "not a findings store" line and gains the evidence section, or points to `evidence-contract.md`.
- `SubmissionKind` gains `verdict`.
- `amoeba submit`'s flag-typing rule widens (D9).
- `Listing` gains `value_options`.
- `tests/test_cli_inspect.py::test_slice_104_listings_are_not_registered_here` is replaced by a test pinning the new registered set.

## Success Criteria

### Functional Requirements

- The same finding text submitted in two verdicts at different list positions, and so with different `positional_id`s, resolves to one identity, and `finding_changes` reports it `recurring`.
- Location line-reference changes (`:119-163` → `:218-240`, `#L12` → none) and summary formatting changes (whitespace, backticks, case, trailing period) do not change identity. A changed file path or changed summary words do.
- Using the captured 102 task-review series from `tests/fixtures/sq_reviews/`, consecutive rounds share **no** identity. The test asserts this and names it as the documented rewording boundary.
- `finding_changes` on a round-2 verdict returns the round-1 verdict as baseline and tags `new`, `recurring`, and `absent` correctly. On a provider-failure verdict it returns `comparable=False`. A provider-failure verdict recorded between two real rounds is skipped as a baseline.
- Each `VerdictStanding` row in D5 is produced by a record built for it. In particular, a PASS with `derivation=derived` is `derived`, a CONCERNS with `derivation=stated` and zero findings is `findings_missing`, and a provider failure is `provider_failure`.
- Recording a provider-failure verdict with findings, or with a verdict other than UNKNOWN, raises directly and is `rejected` through the inbox.
- Three judge samples sharing a `judge_group` are three verdict records with their own model, run id, score, and verdict. `calibration` reports them per `(template, model)` and counts the group as split when their verdicts differ.
- Recording a verdict, check, or artifact with an existing id returns the existing record, writes nothing, and logs a WARNING if the content differs.
- A `verdict` submission applied by the running process produces the record, with its id equal to the submission id. Applying it again changes nothing. An unknown `derivation` value is quarantined as `invalid_payload`.
- A check with `examined_count=0` and outcome `passed` has standing `vacuous`, not `passed`.
- Every verdict, check, and artifact record carries a non-empty `upstream_version`. Recording one without it fails.
- `amoeba inspect verdicts|findings|checks|artifacts|calibration` work with the process running and stopped. `findings --verdict ID` shows new, recurring, and absent.

### Technical Requirements

- Vocabularies are `StrEnum`s defined once. All SQL and column names live in `sql_evidence.py`. The identity rule has one definition and a version constant. The standing rules each have one function.
- `finding_identity.py` has no store imports and is covered by a table of normalization cases.
- Real artifacts from `project-documents/user/reviews/` (including `archive/`) are copied unmodified into `tests/fixtures/sq_reviews/`, with a README recording the capture date and why each is there. Hand-written or hand-edited reviews (for example `103-review.code…`, which carries `resolution:` keys Squadron never writes) are excluded or marked as such.
- A store at schema version 4 with nodes, journal entries, submissions, and messages upgrades to 5 with all of them intact.
- The writer guard is unchanged: no new module opens a store read-write.
- No source module references Squadron's metrology directory or config key (a test asserts it).
- `ruff`, `pyright` strict, and the full suite are clean. Source files stay near 300 lines.
- `docs/evidence-contract.md` exists. It states the identity rule, what the rule does not match, the standing tables, the baseline rule, and the provenance fields. `store-contract.md`, `inbox-contract.md`, and `CHANGELOG.md` are updated.

### Integration Requirements

- End to end through the real CLI as subprocesses: create a project, seed a gate node, submit two review rounds and a provider failure through `amoeba submit verdict`, `kill -9` and `start`, then confirm through read-only inspection that there are three verdict records, the correct changes on round 2, and no double apply.
- `docs/evidence-contract.md` is sufficient for an initiative 140 slice design to proceed without reading the implementation.

### Verification Walkthrough

Draft; refined with captured output when Phase 6 completes. Nothing outside the process can create nodes until initiative 120, and checks and artifacts have no inbox kind. So `scripts/demo_evidence.py` does both. It is run with the process stopped, takes the instance lock while it writes, and is added to the writer guard's `PERMITTED_SCRIPTS`, like `demo_inbox.py`. It seeds one gate node in the `demo` project and records two checks against it: one that examined 12 files, and one that examined 0 and "passed". It prints the node id. Round payloads live beside it as JSON files and use finding text taken from the captured 102 series.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
amoeba start &
amoeba submit create-project --project demo --by pm
amoeba stop
NODE=$(uv run python scripts/demo_evidence.py --print-node-id)
amoeba start &
```

**1. Round 1: a stated CONCERNS with three findings.**

```bash
amoeba submit verdict --project demo --by pm --id r1 --node-id "$NODE" \
  --verdict CONCERNS --derivation stated --fallback-used null --provider-failure false \
  --template tasks --model z-ai/glm-5.3 --upstream squadron --upstream-version 0.14.0 \
  --source artifact_frontmatter --findings "$(cat scripts/demo_evidence/round1.json)"
```

Expected: `amoeba inspect verdicts --project demo` shows `r1` with standing `stated`.

**2. Round 2: one finding carried over at a new position and with a moved line range, one gone, one new.** Submit `round2.json` as `r2` the same way.

Expected: `amoeba inspect findings --project demo --verdict r2` prints `baseline: r1`, one `recurring` row (the same text as r1's F003, now at F001), one `new` row, and two `absent` identities.

**3. A provider failure between rounds is not a baseline.** Submit `r3` with `--verdict UNKNOWN --derivation not_reported --provider-failure true --findings '[]'`, then submit round 2's payload again as `r4`.

Expected: `inspect verdicts` shows `r3` as `provider_failure`. `inspect findings --verdict r3` reports it is not comparable. `inspect findings --verdict r4` shows `baseline: r2` and every r4 finding `recurring`: r3 is skipped.

**4. A derived PASS and a PASS with no findings are not a PASS.** Submit `r5` with `--verdict PASS --derivation derived --fallback-used true`, and `r6` with `--verdict CONCERNS --derivation stated --fallback-used true --findings '[]'`.

Expected: standings `derived` and `findings_missing`.

**5. Judge samples stay separate.** Submit three verdicts with `--template judge-slice-vs-arch --judge-group g1`, three different `--model` values, and `--score` 88, 71, and 90 (verdicts PASS, CONCERNS, PASS).

Expected: `inspect verdicts` shows three rows. `amoeba inspect calibration --project demo` shows one row per model and one split group.

**6. A vacuous check is not a pass.** `amoeba inspect checks --project demo` shows the 12-file check as `passed` and the 0-file check as `vacuous`.

**7. Idempotency and restart.** Resubmit round 1 with `--id r1`, then `kill -9` the process and `amoeba start` again.

Expected: `inspect verdicts` lists the same rows as before, with no second `r1`, and `inspect submissions --project demo` shows the resubmission `applied` exactly once.

**8. Provenance is on every record.** `amoeba inspect verdicts --project demo --json` shows `upstream`, `upstream_version`, `source`, and `recorded_at` on each record.

**9. Normalization against real Squadron text.**

```bash
uv run pytest tests/store/test_finding_identity.py -v
```

Expected: the normalization case table passes, and the captured-series test passes, asserting that no identity is shared across the reworded 102 rounds.

## Risk Assessment

### Technical Risks

- **Silent normalization error.** This is the crux the slice plan names. A rule that is too loose merges distinct findings, and the Runner then believes an unfixed issue is being tracked when it is really two. A rule that is too strict splits one finding, and the Runner believes it was fixed. Both fail silently.
- **Upstream shape drift.** The `imposed` derivation (SQ 927), a changed severity vocabulary, or a new location format changes what callers submit.

### Mitigation Strategies

- The rule is deliberately narrow: formatting only, with no fuzzy matching. It is versioned per observation and keeps raw fields, so a correction is a new version plus a recompute migration, not lost history. The captured-series test pins the rewording boundary so that loosening it is a visible decision.
- Unknown enum values fail validation and are quarantined, never coerced. Every record carries its upstream version label for tracing. Fixtures record their capture date so a stale shape shows up as a reason to recapture.

## Implementation Notes

### Development Approach

1. `finding_identity.py` and its case-table tests, including fixture capture and the real-series test. This is the riskiest piece, and it depends on nothing.
2. Vocabularies, input and record dataclasses, and the standing functions, with table-driven tests of D5.
3. Migration 005, `sql_evidence.py`, mapping, and `VerdictOperations.record_verdict` with its preconditions and replay. Then observations and `verdicts` / `findings` reads, and the 4 → 5 upgrade test.
4. `finding_changes` with baseline selection, including the failure-skip and judge-group cases.
5. `record_check`, `record_artifact`, and their reads. Then `calibration`.
6. The `verdict` submission kind, the D9 flag-typing change, and tests extending 103's completeness tests.
7. The listing registry's `value_options` and the five listings. Update the pinned-registry tests.
8. `scripts/demo_evidence.py` and the round payloads, the end-to-end CLI test, the docs, and the CHANGELOG.

Test each step immediately after implementing it. Commit at the end of each numbered step.

### Special Considerations

- **The inbox is the only outside write path.** Checks and artifacts deliberately get no submission kind yet. Their producers (Runner, 105's detector) run in-process. Adding a kind later is the documented three-part seam.
- **Metrology constraint.** The calibration report is descriptive: it counts and summarizes. It does not recommend thresholds, which is 140's job and one it reports to the PM, and it never writes outside the project store. Escalated-gate admissibility is 140's filter to apply when it computes agreement.
- **Fixtures are real review artifacts from this repository.** Several carry hand-added keys (`resolution`, `resolvedBy`) or were written by hand after a tooling gap. The fixture README must say which files are pure Squadron output, because the normalization tests are only as honest as their input.
