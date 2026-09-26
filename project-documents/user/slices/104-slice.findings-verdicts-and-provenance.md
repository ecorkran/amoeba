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

7. **A Squadron review parser.** It turns `sq review --output json` stdout or a review artifact into a typed verdict. `amoeba ingest review` puts that parser in front of the inbox, so a real review can be recorded with a single command.

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
- `amoeba.upstream.squadron`, the review parser (D1): stdout JSON and review artifacts in, `ParsedReview` out.
- `amoeba ingest review`: parse a file, then submit it as a `verdict`.
- Real Squadron review artifacts copied into `tests/fixtures/sq_reviews/`, plus real `--output json` captures. They are the parser's and the normalization rule's test input.
- `docs/evidence-contract.md`, and updates to `store-contract.md`, `inbox-contract.md`, and `CHANGELOG.md`.

**Excluded**

- Parsing anything from Squadron other than review output: run files, pipeline state, and checkpoint prompts. Also parsing CF MCP results. These stay with 120 (D1).
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
- **PyYAML, as a new runtime dependency** (plus `types-PyYAML` in dev). Artifact frontmatter is YAML, including nested `findings:` lists and quoted strings, so the parser uses a real YAML reader rather than a hand-rolled one. It reads with `safe_load` only.

### Interfaces Required

From the store: `get_node`, `journal_entry`, the `_execute` error translation, and the single-transaction pattern `apply_submission` uses. From the inbox: `validate_envelope` → `KIND_PAYLOAD_MODELS[kind]`, and the `_Application` value passed to an effect. From the CLI: `LISTINGS`, `run_listing`, and `_takes_object` in `cli/submit.py`.

**Upstream ground truth, observed 20260926 against Squadron `4748b63c` (package 0.14.0).** Recorded as a dated observation, not a pinned version:

- `structured_findings[]` / frontmatter `findings:` entries are `{id, severity, category, summary, location}`. `id` is `F{i:03d}` by enumeration order. `severity` is lowercase. A missing location is the literal `unverified`.
- `verdictSource: stated | derived` is now emitted in both JSON and frontmatter (SQ slice 927 plans a third value, `imposed`). `fallback_used` is JSON-only. It is true for a derived verdict, and also for a CONCERNS/FAIL with zero parsed findings, where `verdictSource` stays `stated`.
- A provider failure writes `verdict: UNKNOWN` with no `verdictSource` into the normal artifact slot. It is marked only by a `## Provider Failure` body section.
- No Squadron output carries a run id or the Squadron version. A run file points at its review artifact; the artifact does not point back.
- Judge artifacts carry `score` (0–100) and `criteria`. The judge's verdict is always score-derived.

Confirmed with the Squadron session (sq-orch) on 20260926, with these issues filed:

- **squadron#139:**
  - `runId` / `run_id` on review output.
  - `squadronVersion` / `squadron_version`.
  - `providerFailure: true` in failure frontmatter.
  - The `Saved review to` line moved to stderr under `--output json`.
  - `location_verified` and the finding-scan counts added to JSON.
- **squadron#140:** judge verdicts are `UNKNOWN` in CLI stdout JSON.
- **squadron#141:** the parser's log-side `F` numbering disagrees with persisted ids.

SQ 927 (design committed, not built) adds:

- `verdictSource: imposed`;
- a synthetic `review-coverage` finding with no location;
- `diffTruncated`;
- `requestedModel`, with `aiModel` becoming the answering model.

No changes are planned to the severity values or the `unverified` literal. No canonical cross-run finding identity exists in Squadron; if Squadron adopts one, it will adopt this slice's rule.

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
  upstream/
    squadron/
      review.py             parse_review_json, parse_review_artifact → ParsedReview; to_verdict_input
      review_fields.py      Squadron key names and literals (verdictSource, `unverified`, the failure heading), defined once
  inbox/
    evidence_payloads.py    VerdictPayload, FindingPayload (pydantic) → VerdictInput
  cli/
    inspect_evidence.py     row functions and Listing entries for the five listings
    ingest.py               `amoeba ingest review`: parse, then submit()
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
             comparable standing, and not a sample of target's judge invocation (when it is one)
  for each target observation: RECURRING if its identity is in baseline's identities, else NEW
  ABSENT   = baseline identities not in target's identities
```

A verdict is *comparable* when its standing is `stated`, `derived`, `imposed`, or `unattested`. A provider failure, an unparsed verdict, or a verdict whose findings did not parse is never a baseline and never has changes. Otherwise a failed round would report every open finding as fixed.

### State Management

All durable state is in the project store, in the four new tables. Nothing new lives in memory or in the supervisor directory. Finding status, verdict standing, check standing, and the calibration report are derived on read from stored rows. None is stored, so changing a derivation rule never needs a data migration.

## Technical Decisions

D1–D9 are choices a reasonable Project Manager could make differently. Status as of 20260926: D1 was set by PM direction; D2, D4, and D5 are ratified; D3 and D6–D9 await ratification.

### Technology Choices

**D1 — The Squadron review parser is built here, as an adapter package outside the store. (PM — directed 20260926)** The architecture put parsing of Squadron JSON and frontmatter in the Runner's control surface (120). The sequence makes that unworkable:

- Slice 105 must ingest PM-launched reviews it detects on disk, and 105 runs before any of 120 exists.
- A parser that first appears in 120 would leave this slice testing normalization on hand-extracted strings rather than on what production actually consumes.

So the parser lands with the records it produces. The design keeps two boundaries:

- *Locality.* It lives in `amoeba.upstream.squadron`, not in `amoeba.store`. The store's contract is still typed input (`VerdictInput`) and it never imports the adapter. The adapter imports store vocabularies and models only, never `Store`. It is pure: text in, typed value out. It does no I/O beyond what its caller hands it and no store access, so it runs in-process (105, 120) and out-of-process (`amoeba ingest`) alike.
- *Scope.* It parses Squadron **review output** only: `sq review … --output json` stdout and review artifacts. Parsing CF MCP results and Squadron pipeline control stays with 120. The run-file reader in `process/observers/sq_runs.py` stays where it is; moving it is not this slice's business.

Resulting sequence: 104 ships the parser, the records, and `amoeba ingest review`. 105 adds detection and calls the same parser in-process. 120's Runner calls it on the stdout of runs it launched. `100-arch` is amended to match.

**D2 — Finding identity is normalized location (without line references) plus normalized summary. Severity and category are excluded. (PM — ratified 20260926)** The architecture's principle names severity, location, and summary. This proposal drops severity, for two reasons:

- *Severity is the reviewer's grade of an issue, not the issue.* In the captured 102 task-review series, a finding was regraded from `concern` to `note` between rounds. Keying on severity would report a regrade as one finding fixed and a different one raised.
- *Category is free-form* (`"uncategorized"` when missing) and model-assigned per run. The architecture forbids routing on it, and identity is routing's input.

Line references are stripped from locations because line numbers shift every round. That is why Squadron's own 305 screen avoids fuzzy location matching and needs an exact location to match.

What this rule does **not** do, stated plainly in the contract: match a reworded finding. The same captured series shows every carried-over finding reworded between rounds, for example *"The GRACE_EXPIRED exit criterion has no CLI-level test…"* becoming *"GRACE_EXPIRED → next-start recovery not tested as a distinct scenario"*. Under this rule those are two identities. That is correct for a store: "same issue, different words" is a judgment for 140, and the test suite pins this boundary with the real text. What the rule does catch is formatting drift (whitespace, backticks, case, trailing punctuation, moved line numbers) and a finding re-emitted at a different position, which is what positional ids break.

*Alternatives considered.* Squadron 305's exact `(location, category)` match was rejected because it depends on category and line-exact location. Metrology's hash over `(severity, category, summary, location)` was rejected because it depends on both excluded fields. Neither is a canonical normalization to reuse, which answers the slice plan's open question to sq-base. Two different findings with the same summary in the same file collapse to one identity. That is accepted and documented: both observations are still stored, and the collision shows up as a repeated identity within one verdict.

**D3 — Per-iteration finding status is computed on read, not stored. (PM — pending)** Status (`new` / `recurring` / `absent`) is a set difference between a verdict's identities and its baseline's. Storing it would duplicate what observations already say, and would make every rule change (baseline selection, identity version) a data migration. The query is bounded by one node's verdicts for one template, which is small.

**D4 — A judge sample is a verdict record; samples of one invocation share a `judge_invocation_id`. (PM — ratified 20260926, on condition of clear naming)** A judge run is an `sq review` with a judge template, and its sample fields (model, run id, score, verdict) are a subset of a verdict record's. A separate table would duplicate the provenance columns and split "every verdict" across two tables.

Names, used consistently in code, docs, and CLI:

- A **judge invocation** is one request to the Judge for N samples. It is identified by `judge_invocation_id`, an opaque caller-supplied id.
- A **judge sample** is one verdict record whose `judge_invocation_id` is set.
- A verdict record without one is an ordinary **review verdict**.

Samples of one invocation are recorded individually, never collapsed, and never serve as each other's baselines. The invocation's consensus is 140's computation and is not stored here.

**D5 — Verdict and check standing are closed, derived classifications. (PM — ratified 20260926)** Each record exposes a `standing` computed from its stored fields by one function defined once. This is a deterministic predicate over data, like `BLOCKED_STATUSES`, not a decision: the substrate does not say whether to trust a PASS. It names which case the PASS is.

| `VerdictStanding` | Rule, evaluated top-down |
| --- | --- |
| `provider_failure` | `provider_failure` is true |
| `unparsed` | `verdict` is `UNKNOWN` |
| `findings_unparsed` | `findings_parsed` is false, or `verdict` ∈ {CONCERNS, FAIL} with zero findings recorded |
| `imposed` | `derivation` is `imposed`: Squadron capped the verdict itself (SQ 927) |
| `derived` | `derivation` is `derived` |
| `unattested` | `derivation` is `not_reported`, for example frontmatter written before `verdictSource` existed |
| `stated` | everything else |

The table works on `derivation` and `findings_parsed`, not on `fallback_used` directly. Squadron sets `fallback_used` in three cases (sq-orch confirmed, 20260926):

- a derived verdict;
- a CONCERNS or FAIL with zero parsed findings;
- a PASS whose verdict parsed but whose findings did not.

The parser maps each case onto those two fields, so frontmatter (which lacks `fallback_used`) and JSON land in the same place. The raw `fallback_used` is still stored as provenance.

The slice plan's false-negative predicate (`verdict == PASS && fallback_used`) becomes `verdict == PASS and standing in {derived, findings_unparsed}`.

*Amended 20260926, after ratification, on upstream evidence:* `findings_missing` became `findings_unparsed` to cover the PASS case, and `imposed` was added ahead of SQ 927, whose design is committed.

| `CheckStanding` | Rule, evaluated top-down |
| --- | --- |
| `errored` | outcome is `errored` |
| `unattested` | `examined_count` not reported |
| `vacuous` | `examined_count` is 0 |
| `passed` / `failed` | the outcome |

**D6 — SQ 280's four types map onto records; only two need a new table. (PM — pending)** SQ 280 gave its types one-line descriptions and no fields. `review_findings` is a verdict plus its observations. `checkpoint` is the existing `blocked_on_sq_checkpoint` node carrying the SQ run id (101). Duplicating either would give the same fact two homes. `task_progress` and `devlog` have no existing home and no designed consumer, so they land in one `evidence_artifacts` table with a closed `kind`, opaque JSON `content`, and the standard provenance, like 103's message payloads. Their fields are specified when a consumer designs them.

### Patterns and Conventions

**D7 — Caller-supplied record ids make every record idempotent. (PM — pending)** This is 103's D2 applied to direct calls. Each input carries an `id`. Recording an id that already exists returns the existing record unchanged, and differing content is logged at WARNING (first wins). The Runner can generate the id when it journals the command, so re-ingesting after a crash between "run finished" and "verdict recorded" writes nothing twice. A verdict arriving through the inbox uses its submission id, so there is one id per fact. Slice 105 can derive a deterministic id from an artifact's bytes to make re-detection a no-op.

**D8 — Upstream version is a required opaque label, never compared. (PM — pending)** Every record carries `Provenance(upstream, upstream_version, source, source_path)`. `upstream_version` must be non-empty. The caller supplies whatever the upstream reports. For Squadron that is the `squadronVersion` stamp once squadron#139 lands, and until then an explicit label (for example, from `sq --version`). No code branches on the label or compares it. This matches the existing observers' treatment of `cf --version` and the standing rule that upstream versions are moving targets. `upstream` is free data (`squadron`, `context-forge`), never logic. `source` is closed: `stdout_json`, `artifact_frontmatter`, `command_output`, `document`.

**D9 — `amoeba submit` types flags by one rule: strings and enums are raw, everything else is JSON. (PM — pending)** 103's `_takes_object` accepts only `str`, `str | None`, and `dict`, and raises at parser build otherwise. That rule was added in 103's review for exactly this reason: a kind with other field types should fail loudly, not be mistyped. The `verdict` kind has booleans, numbers, and a findings list, so the rule widens to:

- A `str`, `StrEnum`, or optional of either takes the flag's text as is.
- Every other annotation takes the text as a JSON value (`--score 82.5`, `--fallback-used null`, `--findings '[…]'`).

Pydantic validates the result either way. The existing parametrized tests are extended rather than replaced.

**Vocabularies.** These are `StrEnum`s defined once in `evidence_models.py`:

- `ReviewVerdict` (`PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`)
- `FindingSeverity` (`pass`, `note`, `concern`, `fail`)
- `VerdictDerivation` (`stated`, `derived`, `imposed`, `not_reported`)
- `RecordSource`
- `CheckOutcome` (`passed`, `failed`, `errored`)
- `EvidenceArtifactKind` (`task_progress`, `devlog`)
- `FindingRecurrence` (`new`, `recurring`, `absent`)
- `VerdictStanding` and `CheckStanding`

Payload validation matches verdict and severity case-insensitively, because Squadron emits severity lowercase in `structured_findings` and uppercase in `findings[]`. An unknown value fails validation and is quarantined visibly. It is never mapped to a near neighbour. Squadron's `unverified` location literal is defined once in `finding_identity.py`.

**Unknown is a value.** `derivation`, `fallback_used`, and `findings_parsed` are required in the payload. Their not-reported forms (`not_reported`, `null`) must be passed explicitly, so a submitter cannot omit them by accident.

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
| `calibration(project_id) -> list[CalibrationRow]` | Per `(template, model)` over judge-scored verdicts: sample count, count by standing, count by verdict, score min/mean/max, and the number of judge invocations whose samples disagree on verdict (`split_invocations`). Read-only; descriptive only. |

**`VerdictInput`** (frozen dataclass): `id`, `node_id`, `verdict`, `derivation`, `fallback_used: bool | None`, `findings_parsed: bool | None`, `provider_failure: bool`, `diff_truncated: bool | None`, `template`, `model` (the answering model when Squadron reports it), `requested_model | None`, `reviewed_sha | None`, `score: float | None`, `criteria: Mapping | None`, `tool_calls_made: int | None`, `sq_run_id | None`, `journal_entry_id | None`, `judge_invocation_id | None`, `findings: Sequence[FindingInput]`, `provenance: Provenance`.

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

**Squadron review parser (`amoeba.upstream.squadron`):**

| Call | Effect |
| --- | --- |
| `parse_review_json(text) -> ParsedReview` | Decodes the first JSON object in `text` with `raw_decode` and ignores anything after it. Today that is the `Saved review to …` line Squadron prints to stdout (squadron#139 moves it to stderr). |
| `parse_review_artifact(text) -> ParsedReview` | Splits the leading `---`-delimited frontmatter, reads it with `yaml.safe_load`, and scans the body for the two headings the frontmatter does not reflect. |
| `to_verdict_input(parsed, *, node_id, record_id=None, upstream_version=None, judge_invocation_id=None, journal_entry_id=None) -> VerdictInput` | Composes the store input. `record_id` defaults to `sq-review-` plus the first 32 hex characters of SHA-256 of the input text, so re-ingesting the same bytes is a no-op (D7). `upstream_version` is taken from the parsed input if Squadron stamped one; otherwise the argument is required. With neither, it raises. |

`ParsedReview` carries the `VerdictInput` review fields plus `source` (`stdout_json` or `artifact_frontmatter`), `digest`, and the optional `upstream_version` and `sq_run_id` the input stated.

Mapping rules:

| `VerdictInput` field | From stdout JSON | From an artifact |
| --- | --- | --- |
| `verdict` | `verdict` | `verdict` |
| `derivation` | `verdictSource`; `not_reported` if absent | same |
| `fallback_used` | `fallback_used` | `null`: not in frontmatter |
| `findings_parsed` | false when `fallback_used` is true and `verdictSource` is `stated`; otherwise true | false when the body has a *Findings Not Parsed* heading or the frontmatter has no `findings:` key; otherwise true |
| `provider_failure` | false: a provider failure produces no JSON | true when the frontmatter says `providerFailure: true` (squadron#139), or the body has a *Provider Failure* heading |
| `template` | `template_name` | `reviewType` |
| `model` / `requested_model` | `model` / `requested_model` | `aiModel` / `requestedModel` |
| `diff_truncated` | `diff_truncated` | `diffTruncated` |
| findings | `structured_findings[]` | `findings:` |
| `sq_run_id`, `upstream_version` | `run_id`, `squadron_version` | `runId`, `squadronVersion` |

Keys added by squadron#139 and SQ 927 are read when present and are `null` when absent, so the parser works before and after those land. Headings are matched leniently: any level, any case, surrounding whitespace ignored. Squadron key names and literals live once in `review_fields.py`. Unknown keys are ignored, including the `resolution` and `resolvedBy` keys this repository has added by hand. A missing `verdict`, a non-mapping frontmatter, or no JSON object raises `SquadronParseError`. Nothing is defaulted.

*Judge templates:* stdout JSON reports `verdict: UNKNOWN` for every judge template (squadron#140), because the score-derived verdict is applied only when the review runs inside a pipeline. The parser records what it is given, so such a record's standing is `unparsed`. Until #140 is fixed, judge samples are ingested from the artifact. The contract doc says so.

*One assumption to check against fixtures:* that `template_name` in JSON and `reviewType` in frontmatter carry the same string for the same review. Baseline selection groups by `template`, so a mismatch would split one series in two. If a captured pair disagrees, the mapping gains a normalization step before this slice closes.

**Inbox, the `verdict` kind:** the payload is `VerdictInput`'s fields flattened. `provenance` becomes `upstream`, `upstream_version`, `source`, and `source_path`, and the record id is the submission id. The effect checks the preconditions listed under Data Flow.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba submit verdict --project ID --by NAME --node-id ID --verdict V --derivation D --fallback-used JSON --provider-failure JSON --template T --model M --findings JSON --upstream U --upstream-version V --source S [optional fields…] [--id ID]` | Flags derived from `VerdictPayload` under D9. |
| `amoeba ingest review --project ID --node ID --by NAME (--artifact PATH \| --stdout-json PATH) [--upstream-version V] [--judge-invocation ID] [--id ID]` | Parses the file with the adapter, then calls `submit()` with a `verdict` payload. It prints the submission id. Works whether the process is running or stopped, like `submit`. A parse failure exits non-zero and submits nothing. |
| `amoeba inspect verdicts --project ID [--node ID]` | `recorded_seq, id, node_id, template, model, verdict, standing, score, judge_invocation_id, upstream_version` |
| `amoeba inspect findings --project ID [--node ID]` | Identities (`findings()`). With `--verdict ID`: that verdict's observations tagged `new`/`recurring`, then `absent` identities, with the baseline id in a header line. |
| `amoeba inspect checks --project ID [--node ID]` | `recorded_seq, id, node_id, name, outcome, examined_count, standing, baseline_ref` |
| `amoeba inspect artifacts --project ID [--kind K]` | `recorded_seq, id, node_id, kind, upstream, recorded_at` |
| `amoeba inspect calibration --project ID` | One row per `(template, model)`. |

All listings accept `--json`. `--node`, `--verdict`, and `--kind` need a value, which the registry does not support today (only booleans and choices). `Listing` gains a `value_options` field of `ValueOption(flag, help_text)` entries, and `_add_inspect_parser` adds them generically. This is the one edit to 102's CLI plumbing, and it is additive.

### Database / Storage Schema

Migration `005_findings_verdicts_and_provenance.sql`, `EXPECTED_SCHEMA_VERSION` → 5. No backfill: no evidence exists before this slice.

- **`verdicts`**:
  - Ordering and identity: `recorded_seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `id` (UNIQUE), `project_id`, `node_id` (FK), `journal_entry_id` (nullable FK), `judge_invocation_id` (nullable).
  - The review itself: `verdict`, `derivation`, `fallback_used` (INTEGER nullable), `findings_parsed` (INTEGER nullable), `provider_failure` (INTEGER), `diff_truncated` (INTEGER nullable), `template`, `model`, `requested_model`, `reviewed_sha`, `score` (REAL), `criteria` (JSON text), `tool_calls_made`, `sq_run_id`.
  - Provenance: `upstream`, `upstream_version`, `source`, `source_path`, `recorded_at`.
  - Indexes on `(project_id, node_id, template, recorded_seq)` (baseline lookup) and `(project_id, judge_invocation_id)`.
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
  - The `verdict` inbox kind for judge samples, with `judge_invocation_id`.
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
- Each `VerdictStanding` row in D5 is produced by a record built for it. In particular, a PASS with `derivation=derived` is `derived`, a CONCERNS with `derivation=stated` and zero findings is `findings_unparsed`, `derivation=imposed` is `imposed`, and a provider failure is `provider_failure`.
- Recording a provider-failure verdict with findings, or with a verdict other than UNKNOWN, raises directly and is `rejected` through the inbox.
- Three judge samples sharing a `judge_invocation_id` are three verdict records with their own model, run id, score, and verdict. `calibration` reports them per `(template, model)` and counts the invocation in `split_invocations` when their verdicts differ.
- Recording a verdict, check, or artifact with an existing id returns the existing record, writes nothing, and logs a WARNING if the content differs.
- A `verdict` submission applied by the running process produces the record, with its id equal to the submission id. Applying it again changes nothing. An unknown `derivation` value is quarantined as `invalid_payload`.
- A check with `examined_count=0` and outcome `passed` has standing `vacuous`, not `passed`.
- Every artifact in `tests/fixtures/sq_reviews/` parses to the verdict, derivation, and findings its frontmatter states. The captured provider-failure artifact parses to standing `provider_failure`. A judge artifact yields its `score` and `criteria`.
- A captured stdout JSON followed by Squadron's `Saved review to …` line parses. The same review's artifact and stdout JSON produce the same identities.
- `fallback_used: true` with `verdictSource: stated` in JSON, and a *Findings Not Parsed* body in an artifact, each give standing `findings_unparsed`, including on a PASS.
- A missing `verdict`, non-mapping frontmatter, or text with no JSON object raises `SquadronParseError`. `to_verdict_input` with no upstream version in the input and none passed raises.
- `amoeba ingest review` on the same file twice produces one verdict record. On an unparseable file it exits non-zero and leaves nothing in `inbox/new/`.
- Every verdict, check, and artifact record carries a non-empty `upstream_version`. Recording one without it fails.
- `amoeba inspect verdicts|findings|checks|artifacts|calibration` work with the process running and stopped. `findings --verdict ID` shows new, recurring, and absent.

### Technical Requirements

- Vocabularies are `StrEnum`s defined once. All SQL and column names live in `sql_evidence.py`. The identity rule has one definition and a version constant. The standing rules each have one function.
- `finding_identity.py` has no store imports and is covered by a table of normalization cases.
- Real artifacts from `project-documents/user/reviews/` (including `archive/`) are copied unmodified into `tests/fixtures/sq_reviews/`, with a README recording the capture date and why each is there. Hand-written or hand-edited reviews (for example `103-review.code…`, which carries `resolution:` keys Squadron never writes) are excluded or marked as such. The fixtures also include:
  - a pipeline-run judge artifact, for example Squadron's own `302-review.judge.slice-vs-arch…`;
  - at least one real `sq review … --output json` stdout capture, with its trailing line intact. This needs a live paid provider run, which the PM launches.
  - a real degraded *Findings Not Parsed* artifact, if one can be found. If none can, the README records it as missing, and that parser branch is tested on a real artifact with the heading added, which the README also labels.
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

**1. Ingest a real review series.** The three captured rounds of the 102 task review (part 1) are real Squadron artifacts.

```bash
F=tests/fixtures/sq_reviews
for r in 102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md \
         102-review.tasks.resident-process-and-recovery.part-1.md.archived \
         102-review.tasks.resident-process-and-recovery.part-1.md; do
  amoeba ingest review --project demo --node "$NODE" --by pm --artifact "$F/$r" --upstream-version 0.14.0
done
```

(The fixture filenames are settled at capture. The archived middle round needs a distinct name.)

Expected:

- `amoeba inspect verdicts --project demo` shows three `tasks` verdicts, CONCERNS, CONCERNS, then PASS, all `stated`, with `source` `artifact_frontmatter`.
- `amoeba inspect findings --project demo --verdict <round-2 id>` shows the first round as its baseline, **no** `recurring` rows, and every round-1 finding `absent`. This is the documented rewording boundary, shown on real data.

**2. Ingest a real provider failure.** Run `amoeba ingest review` on the captured failure artifact (`103-review.tasks…part-2`, archived, OpenRouter 402).

Expected: its standing is `provider_failure`, and `inspect findings --verdict` on it reports it is not comparable.

**3. Recurrence across positions.** Real data holds no verbatim recurrence, so two built payloads (`scripts/demo_evidence/round{1,2}.json`) take real finding text from round 1 and reorder it. Round 2 puts round 1's F003 at F001, changes its line range, drops one finding, and adds one.

```bash
amoeba submit verdict --project demo --by pm --id r1 --node-id "$NODE" \
  --verdict CONCERNS --derivation stated --fallback-used null --findings-parsed true \
  --provider-failure false --template demo --model demo-model --upstream squadron \
  --upstream-version 0.14.0 --source artifact_frontmatter \
  --findings "$(cat scripts/demo_evidence/round1.json)"
```

Submit `round2.json` as `r2` the same way.

Expected: `inspect findings --verdict r2` prints `baseline: r1`, one `recurring` row, one `new` row, and one `absent` identity.

**4. The PASS cases that are not a PASS.** Submit three verdicts:

- `r3`: `--verdict PASS --derivation derived --fallback-used true`
- `r4`: `--verdict PASS --derivation stated --fallback-used true --findings-parsed false`
- `r5`: `--verdict CONCERNS --derivation imposed`

Expected: standings `derived`, `findings_unparsed`, and `imposed`.

**5. Judge samples stay separate.** Ingest the captured pipeline-run judge artifact three times with `--judge-invocation j1`, each with a distinct `--id`. Then submit two built samples with different `--model` values and scores, one of them CONCERNS.

Expected:

- `inspect verdicts` shows every sample as its own row.
- `amoeba inspect calibration --project demo` shows one row per `(template, model)`, with `split_invocations` = 1.

**6. A vacuous check is not a pass.** `amoeba inspect checks --project demo` shows the 12-file check as `passed` and the 0-file check as `vacuous`.

**7. Idempotency and restart.** Ingest round 1's artifact again without `--id`, so the digest id repeats. Then `kill -9` the process and run `amoeba start`.

Expected:

- `inspect verdicts` lists the same rows as before.
- `inspect submissions --project demo` shows the repeat submission as a no-op against the existing id. Nothing is applied twice.

**8. Provenance is on every record.** `amoeba inspect verdicts --project demo --json` shows `upstream`, `upstream_version`, `source`, `source_path`, and `recorded_at` on each record.

**9. The parser and the rule against real Squadron text.**

```bash
uv run pytest tests/upstream tests/store/test_finding_identity.py -v
```

Expected: every fixture parses to its stated fields, the normalization case table passes, and the captured-series test confirms that no identity is shared across the reworded 102 rounds.

## Risk Assessment

### Technical Risks

- **Silent normalization error.** This is the crux the slice plan names. A rule that is too loose merges distinct findings, and the Runner then believes an unfixed issue is being tracked when it is really two. A rule that is too strict splits one finding, and the Runner believes it was fixed. Both fail silently.
- **Upstream shape drift.** Squadron changes its output shape without semver. SQ 927 and squadron#139 are both in flight and add keys to the output the parser reads.

### Mitigation Strategies

- The rule is deliberately narrow: formatting only, with no fuzzy matching. It is versioned per observation and keeps raw fields, so a correction is a new version plus a recompute migration, not lost history. The captured-series test pins the rewording boundary so that loosening it is a visible decision.
- The parser reads the in-flight keys as optional, so it works before and after they land. sq-orch will flag when 927 merges.
- Unknown enum values fail validation and are quarantined, never coerced. Every record carries its upstream version label for tracing. Fixtures record their capture date so a stale shape shows up as a reason to recapture.

## Implementation Notes

### Development Approach

1. `finding_identity.py` and its case-table tests, including fixture capture and the real-series test. This is the riskiest piece, and it depends on nothing.
2. Vocabularies, input and record dataclasses, and the standing functions, with table-driven tests of D5.
3. Migration 005, `sql_evidence.py`, mapping, and `VerdictOperations.record_verdict` with its preconditions and replay. Then observations and `verdicts` / `findings` reads, and the 4 → 5 upgrade test.
4. `finding_changes` with baseline selection, including the failure-skip and judge-sample cases.
5. `record_check`, `record_artifact`, and their reads. Then `calibration`.
6. The `verdict` submission kind, the D9 flag-typing change, and tests extending 103's completeness tests.
7. `amoeba.upstream.squadron` against every fixture, then `amoeba ingest review`. Check the `template_name`/`reviewType` assumption as soon as a JSON capture exists.
8. The listing registry's `value_options` and the five listings. Update the pinned-registry tests.
9. `scripts/demo_evidence.py` and the round payloads, the end-to-end CLI test, the docs, and the CHANGELOG.

Test each step immediately after implementing it. Commit at the end of each numbered step.

### Special Considerations

- **The inbox is the only outside write path.** Checks and artifacts deliberately get no submission kind yet. Their producers (Runner, 105's detector) run in-process. Adding a kind later is the documented three-part seam.
- **Metrology constraint.** The calibration report is descriptive: it counts and summarizes. It does not recommend thresholds, which is 140's job and one it reports to the PM, and it never writes outside the project store. Escalated-gate admissibility is 140's filter to apply when it computes agreement.
- **Fixtures are real review artifacts from this repository.** Several carry hand-added keys (`resolution`, `resolvedBy`) or were written by hand after a tooling gap. The fixture README must say which files are pure Squadron output, because the normalization tests are only as honest as their input.
