---
docType: reference
project: amoeba
slice: findings-verdicts-and-provenance
dateCreated: 20260927
dateUpdated: 20261030
status: complete
---

# The Amoeba Evidence Contract

This document is the contract for review evidence in the store: verdict
records, the findings each review reported, how findings are matched across
rounds, and the trust label on every verdict. It is written so that slice 105
(the Squadron-output parser) and initiative 140 (judgment over findings) can be
designed **without reading the implementation**. If you have to open
`verdicts.py` to answer a design question, that is a gap here — say so.

## What the evidence store is

- **A record of what each review said.** One verdict per review, with where it
  came from, and one observation per finding, in the order the reviewer gave.
- **A content key per finding** that survives formatting changes between
  rounds, so "is this the same finding as last round?" is a store query.
- **"What changed since last round?"** for any review, worked out on request.
- **A trust label** on every verdict, separating a real PASS from one Squadron
  computed, from a review whose findings did not parse, from a provider failure.

## What it is not

- **Not a parser.** The store never reads Squadron's JSON or review files.
  Callers pass already-parsed values (`VerdictInput`). Parsing is slice 105.
- **Not a judge of sameness.** The matching rule removes formatting only. It
  does not decide that a reworded finding is the same issue; that is judgment,
  and belongs to initiative 140. See [What the rule does not match](#what-the-rule-does-not-match).
- **Not a tracker of finding state.** Nothing marks a finding addressed,
  disputed, accepted, or rejected. That is initiatives 120 and 140.
- **Not a discoverer.** Noticing reviews on disk that someone else launched is
  slice 106.

## Recording a review

```python
from amoeba.store import (
    FindingInput,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    Store,
    VerdictDerivation,
    VerdictInput,
)

record = store.record_verdict(
    VerdictInput(
        id="…",  # the caller's id; the retry key
        node_id=node.id,
        verdict=ReviewVerdict.CONCERNS,
        derivation=VerdictDerivation.STATED,
        fallback_used=None,
        findings_parsed=True,
        provider_failure=False,
        review_type="tasks",
        model="z-ai/glm-5.3",
        findings=(
            FindingInput(
                severity=FindingSeverity.CONCERN, summary="…", location="path.md:12-30"
            ),
        ),
        provenance=Provenance(
            upstream="squadron",
            upstream_version="0.14.0",
            source=RecordSource.ARTIFACT_FRONTMATTER,
        ),
    ),
    project_id="demo",
)
```

`record_verdict` is **one transaction**, in this order:

1. **The id is already recorded** → return the existing record and write
   nothing. If the content differs, log a WARNING; the first record wins.
2. **The node exists in `project_id`** → else `NodeNotFoundError`.
3. **The journal entry, if given, is on the same node** → else `ValueError`.
4. **A provider failure has verdict `UNKNOWN` and no findings** → else `ValueError`.
5. **`upstream_version` is not empty** → else `ValueError`.
6. Insert the verdict row. `recorded_seq` is assigned here: arrival order.
7. Insert one observation per finding, in the order given, with the raw text,
   the normalized text, the content key, and the rule version.

A failed check writes nothing.

### The retry rule

Every record carries its own id, so a retry never writes twice. The Runner can
create the id when it journals the Squadron command, so recording again after a
crash is harmless. Through the inbox, the record id is the submission id.

### `VerdictInput`

A frozen, keyword-only dataclass.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `str` | The retry key. |
| `node_id` | `str` | Must be in the project. |
| `verdict` | `ReviewVerdict` | `PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`. |
| `derivation` | `VerdictDerivation` | **Required.** `stated`, `derived`, `imposed`, `not_reported`. |
| `fallback_used` | `bool \| None` | **Required.** Squadron's raw flag, kept as provenance only. |
| `findings_parsed` | `bool \| None` | **Required.** `False` means the findings did not parse. |
| `provider_failure` | `bool` | The review was a provider failure. |
| `review_type` | `str` | Squadron's `reviewType` (its JSON `template_name`). |
| `model` | `str` | The model that answered. |
| `findings` | `tuple[FindingInput, ...]` | In the reviewer's order. |
| `provenance` | `Provenance` | See [Provenance](#provenance). |
| `diff_truncated` | `bool \| None` | Squadron's `diffTruncated` (SQ 927); null when absent. |
| `requested_model` | `str \| None` | Squadron's `requestedModel` (SQ 927); set only on a substitution. |
| `reviewed_sha` | `str \| None` | The commit reviewed. |
| `score` | `float \| None` | Stored; the calibration report summarizes it. |
| `criteria` | `Mapping \| None` | Stored as JSON; no reader yet. |
| `tool_calls_made` | `int \| None` | |
| `sq_run_id` | `str \| None` | Squadron's `runId` (#139), pipeline runs only. |
| `journal_entry_id` | `str \| None` | The journaled Squadron run command, if any. |
| `judge_invocation_id` | `str \| None` | Set: this verdict is a [judge sample](#judge-samples). Default `None`. |

"Not reported" is said explicitly: `derivation`, `fallback_used`, and
`findings_parsed` have no default. A caller passes `not_reported` or `None`.

`FindingInput` has `severity` (`FindingSeverity`: `pass`, `note`, `concern`,
`fail`), `summary`, and optional `position_id` (Squadron's `F001`, kept as data
only — it is a list position and changes every run), `category`, `location`.

`VerdictRecord` is `VerdictInput` plus `project_id`, `recorded_seq`,
`recorded_at`, and the computed `standing` property.

`parse_verdict` and `parse_severity` accept any letter case (Squadron writes
severity lowercase in one place and uppercase in another) and raise
`ValueError` on an unknown word. Nothing is ever mapped to a near match.

### Provenance

Every verdict carries `upstream` (e.g. `squadron`), `upstream_version`
(required, not empty), `source` (`RecordSource`: `stdout_json`,
`artifact_frontmatter`, and, for records that are not Squadron review output
such as checks, `command_output` and `document`; a label of origin, never
logic), and `source_path` (optional). Until Squadron stamps its version on its output, the
caller supplies it, for example from `sq --version`. **No code compares versions
or branches on them.** When Squadron changes its output, the version finds the
affected records; it never changes how they are read.

### Parsing Squadron output

`amoeba.upstream.squadron` turns Squadron's review output into a `VerdictInput`.
It is pure: it reads text, not files, and opens no store. Two readers share one
mapping: `parse_review_json` (the stdout of `sq review … --output json`) and
`parse_review_artifact` (a saved review file). Both return a frozen
`ParsedReview`; `to_verdict_input` adds the node, path, and version label.
`amoeba ingest review` is the command-line caller (see
[`process-contract.md`](process-contract.md), "The CLI").

Squadron's key names are defined once, in `review_fields.py`. Nothing is
defaulted: a missing `verdict`, review type, or model, an unknown verdict or
severity word, a finding without `severity` or `summary`, malformed YAML or
JSON, and a provider failure with a verdict or findings all raise
`SquadronParseError`, naming the key and the source.

**The mapping** (design decision D3 in slice 105):

| `ParsedReview` field | From stdout JSON | From a review file |
| --- | --- | --- |
| `derivation` | `verdictSource`; `not_reported` if null or absent | the same key; `not_reported` if absent (older files) |
| `fallback_used` | `fallback_used`; `None` if absent | `None` (the file does not carry it) |
| `findings_parsed` | `False` when `fallback_used` is true and the derivation is `stated` or `not_reported`; `None` when `fallback_used` is absent; else `True` | `False` when the body has a *Findings Not Parsed* heading; else `True` |
| `provider_failure` | `False` (a failure produces no JSON) | `providerFailure` when the key is present; otherwise a *Provider Failure* heading (files from before Squadron wrote the key) |
| `requested_model` | only when `model_substituted` is true | `requestedModel` |
| `reviewed_sha`, `slice`, `source_document` | `None` | `reviewedSha`, `slice` (absent on PR reviews), `sourceDocument` |
| `sq_run_id`, stamp | `run_id`, `squadron_version` | `runId`, `squadronVersion` |
| `findings` | `structured_findings[]` | `findings:` (absent means none) |

Each finding maps `id` to `position_id`, reads `severity` case-insensitively,
and passes `category`, `summary`, and `location` through as written, including
Squadron's `unverified` literal (the matching rule treats it as empty).
Headings match at any level and in any case, outside fenced code blocks; text that only mentions a heading mid-line is not one. Keys the parser does not know are
ignored, including the `resolution:` and `resolvedBy:` keys added to review
files by hand. Keys dropped on purpose: `location_verified`, `finding_scan`,
`diff_chars`, `diff_chars_injected`, `answering_models`, `stop_reason`,
`tools_given`. `source_document` is read from files only, because JSON's
input path is whatever the caller typed.

**The version rule** (D4). Squadron's own stamp (`squadronVersion` or
`squadron_version`) is the version when present. A review with no stamp takes
the caller's label (`--upstream-version`). With neither, `to_verdict_input`
raises `UpstreamVersionError`; with both and different, it raises, naming both.
The label is never compared beyond that equality.

**The record id** (D5). `review_record_id` is `sq-review-` plus the first 32 hex
characters of the SHA-256 of a canonical JSON encoding of the `ParsedReview`,
tagged `parsed-review-v1`. It covers every `ParsedReview` field and nothing the
caller supplies (node, path, version label, journal entry). So:

- Adding `resolution:` keys or a `## Response` section does not change the id.
  Ingesting the same review from another path is a replay no-op, and the first
  ingest's `source_path` stays on the record.
- The id does not include the node. Ingesting the same review onto a second
  node is a silent replay no-op (the first record wins); pass a new `--id` to
  record it again. `ingest review` prints the id on stderr.
- Changing any covered field changes every id. That is a contract change: it
  needs a new format tag and a CHANGELOG entry.
- A review's file and its stdout capture get **different** ids, because they
  carry different fields (`reviewed_sha` exists only in the file). Ingesting
  both stores the review twice: two verdict rows, every finding key seen twice,
  and `finding_changes` reporting each finding as `recurring` against itself.
  **Ingest the file whenever one exists;** use stdout only for `--no-save` runs.

**Attribution** (D7). `ingest review --node` is the operator's explicit
choice and is not checked against the review's `slice`. The command prints the
node, the parsed slice (`-` when there is none), and the review type on stderr
before submitting, so a wrong node is visible. There is no delete: recover by
ingesting again onto the right node with a new `--id`.

**Dated observation, not a version pin.** Checked 20260928 against squadron
`373217ab` (0.15.0). Squadron moves without semver; the shapes above are what
the parser reads, and the version label only finds the affected records:

- `verdictSource: imposed` appears when Squadron caps a PASS to CONCERNS (the
  diff was truncated and the model made no successful tool calls). The capped
  review carries a synthetic finding with category `review-coverage`.
- `diffTruncated` is written only on reviews that had a diff.
- `requestedModel` appears only on a substitution; `aiModel` is then the model
  that answered.
- Under `--output json`, the "Saved review to" line goes to stderr. The JSON
  reader still decodes only the first object, so a trailing line is harmless.
- A run from the CLI has no `runId`; its JSON `run_id` is null.

## The matching rule

`amoeba.store.finding_identity`, **version 1**. Pure functions over text,
importable without opening a store: `normalize_summary`, `normalize_location`,
`finding_identity`, `RULE_VERSION`.

| Step | Summary | Location |
| --- | --- | --- |
| 1 | Unicode NFKC | Missing, empty, or `unverified` (any case) → empty |
| 2 | Remove backticks | NFKC; `\` → `/`; drop a leading `./` |
| 3 | Casefold | Remove line references anywhere: `:12`, `:12-30`, `:12:4`, comma lists such as `:34-37,55-58`, `#L12`, `#L12-L30`, `, line 12`, `, lines 12-30` |
| 4 | Collapse whitespace runs; trim | Collapse whitespace; trim. **Case is kept** — paths are case-sensitive |
| 5 | Drop trailing `.`, `;`, `:` | — |

Heading anchors such as `slice.md#data-flow` are not line references and are
kept.

`finding_identity(location, summary)` is the hex SHA-256 of `"v1"`, the
normalized location, and the normalized summary, each written as
`{length}:{text}` and concatenated, so no character in a field can move text
across the field boundary. Severity and
category are **not** part of the key: severity is the reviewer's grade of an
issue, not the issue (one captured finding went from `concern` to `note`
between rounds), and category is free text picked fresh each run.

Every observation stores `identity_version`. Keys are compared only within one
version. The raw text is kept, so a version 2 can be computed for old rows by a
migration.

### What the rule catches

Whitespace, backticks, letter case, trailing punctuation, moved line numbers,
and the same finding at a different position in the list.

### What the rule does not match

**A reworded finding.** Between the two captured slice-102 task-review rounds
(`tests/fixtures/sq_reviews/`), Squadron reworded every carried-over finding.
Round 1's *"Every success criterion in the slice design traces to at least one
task"* came back as *"Every LLD success criterion traces to at least one task,
and no task is scope creep"*. The two rounds share **no** keys, and a test pins
that. Loosening the rule to match them is a deliberate decision for initiative
140, not a bug fix.

Two different findings with the same summary in the same file get the same
key. Both are stored; the collision shows as a repeated key within one review.

## The trust label

`VerdictStanding`, computed by `verdict_standing(...)` from stored fields,
checked **top to bottom**. It describes what kind of verdict this is; it does
not decide whether to act on it. It is never stored, so changing the rule
needs no data fix.

| Order | Label | When |
| --- | --- | --- |
| 1 | `provider_failure` | `provider_failure` is true |
| 2 | `unparsed` | `verdict` is `UNKNOWN` |
| 3 | `findings_unparsed` | `findings_parsed` is false |
| 4 | `imposed` | `derivation` is `imposed` (Squadron capped the verdict) |
| 5 | `derived` | `derivation` is `derived` (Squadron computed it from findings) |
| 6 | `unattested` | `derivation` is `not_reported` |
| 7 | `stated` | everything else: the reviewer said it |

"A PASS the reviewer didn't really give" is `verdict == PASS` with label
`derived`.

A real Squadron CONCERNS or FAIL with zero parsed findings always sets
`fallback_used`, so it lands as `findings_unparsed`. The table also labels a
CONCERNS with zero findings and `findings_parsed=True` as `stated`; that row is
covered for completeness, but Squadron cannot produce it today.

## What changed since the last round

`store.finding_changes(verdict_id) -> FindingChanges`, worked out when asked.

- **Comparable** standings: `stated`, `derived`, `imposed`, `unattested`
  (`COMPARABLE_STANDINGS`). A target that is not comparable returns
  `comparable=False`, no previous round, and empty lists.
- **The previous round** is the latest earlier verdict (by `recorded_seq`) on
  the same node, with the same `review_type`, whose standing is comparable. A
  provider failure, an unparsed verdict, or a review whose findings did not
  parse is **never** a baseline — otherwise a failed round would report every
  open finding as fixed. When the target is a judge sample, samples of its own
  invocation are skipped too (see [Judge samples](#judge-samples)).
- Each target finding is `recurring` if its key (within the same rule version)
  is in the previous round, else `new`. No previous round means every finding
  is `new`.
- `gone` holds the previous round's observations whose keys the target lacks,
  one per key.

`FindingChanges` carries `verdict_id`, `comparable`, `previous_verdict_id`,
`findings` (each a `TaggedFinding`: `observation` and `change`), and `gone`.

## Reading

| Method | Returns |
| --- | --- |
| `verdict(verdict_id)` | `VerdictRecord \| None` |
| `verdicts(project_id, *, node_id=None, judge_invocation_id=None)` | In arrival order. `judge_invocation_id` keeps one invocation's samples. |
| `observations(verdict_id)` | `FindingObservation`s in the reviewer's order. Raises `VerdictNotFoundError` for an unknown id. |
| `findings(project_id, *, node_id=None)` | One `FindingSummary` per key per node: latest severity, summary, and location; first and last verdict ids; how many reviews reported it. |
| `finding_changes(verdict_id)` | Above. Raises `VerdictNotFoundError` for an unknown id. |

All of them work through `Store.open_read_only`. `observations` and
`finding_changes` raise rather than return empty for an unknown id, because an
empty result would look like a real review with no findings.

## Through the inbox

The `verdict` submission kind records a review from outside the process — the
path for the out-of-process Judge. The payload is `VerdictInput`'s fields
except `id`, with `provenance` flattened to `upstream`, `upstream_version`,
`source`, and `source_path`. The submission id becomes the record id.

- An unknown word in an enum field (e.g. `derivation: guessed`) fails payload
  validation: the file is quarantined as `invalid_payload`. So does an omitted
  `derivation`, `fallback_used`, or `findings_parsed`.
- A failed check (unknown node, a malformed provider failure, an empty
  `upstream_version`) is recorded as `rejected` with the reason.
- Resubmitting the same id is a no-op, as for every kind.

```bash
amoeba submit verdict --project demo --by judge --node-id "$NODE" \
  --verdict CONCERNS --derivation stated --fallback-used null \
  --findings-parsed true --provider-failure false \
  --review-type tasks --model glm-5.3 \
  --upstream squadron --upstream-version 0.14.0 --source artifact_frontmatter \
  --findings '[{"severity": "concern", "summary": "…", "location": "x.md:12"}]'
```

See [`inbox-contract.md`](inbox-contract.md) for the flag rule.

## Inspection

- `amoeba inspect verdicts --project ID [--node ID] [--judge-invocation-id ID]`
  — columns `recorded_seq, id, node_id, review_type, model, verdict, standing,
  judge_invocation_id, upstream_version`. With
  `--json`, rows also carry `upstream`, `source`, `source_path`, `sq_run_id`,
  `reviewed_sha` (both `null` when the review has none), `recorded_at`.
- `amoeba inspect findings --project ID [--node ID]` — one row per key.
- `amoeba inspect changes --project ID --verdict ID` — that review's findings
  tagged `new`/`recurring`, then the `gone` ones. Columns `change, severity,
  summary, location, key, previous_verdict_id` (`None` for a first round);
  `--json` rows also carry `verdict_id`. An unknown id exits `NOT_FOUND` (10).
  A review that is not comparable exits `NOT_COMPARABLE` (11) with nothing on
  stdout, so neither form can read a failed round as one with no changes.

All three read through a read-only handle, whether the process is running or not.

## Reviews found on disk

*Added by slice 106.* The detection tenant (see
[`process-contract.md`](process-contract.md#review-detection)) records reviews
nobody in Amoeba launched as verdicts, through the same writer and retry rule
as everything else.

### The attribution rule — initiative 120 must use it

A review attaches to **the one node in its project with `kind == slice` and
`cf.slice_name` equal to the review's frontmatter `slice`**. Zero or several
matches attach it nowhere: the ledger records `unattributed` with the
candidate ids, and nothing is written to any node, and no node is created.
The rule is defined once, as the pure function
`amoeba.store.attribute_review(slice_nodes, slice_name) -> Attribution`.

**Initiative 120 must attach the reviews it launches with the same rule**, or
the Runner's rounds and detected rounds of one slice split across two nodes
and "what changed since the last round" compares the wrong things. Slice,
tasks, and code reviews on one slice node stay separate series because
`finding_changes` groups by `review_type`.

### Requirements on initiative 120 (D5)

Detection defers while a project has an unresolved journal entry of a
review-producing kind, and skips any file the ledger already holds. That
ordering depends on two things the Runner must do:

- **Point 3.** The Runner marks the review file it recorded as
  `runner_issued` in the detection ledger **no later than it resolves the
  journal entry, in one transaction**: record the verdict, mark the file,
  resolve the entry. Otherwise the next detection tick takes the file as
  external. The single store method that makes this one call is
  `record_runner_report(entry_id, reviews, *, outcome, result) ->
  list[VerdictRecord]` (in-process only). A run may write several review files
  (the parts of a multi-part review), so `reviews` is a sequence of
  `RunnerReview(verdict, detection)`; it may be empty (a failed run, or one that
  wrote no review), and `outcome` is `completed` or `failed`. One transaction:
  every check, then for each review in order `record_verdict`'s body (its retry
  rule applies) and the `runner_issued` ledger row carrying the verdict's id and
  node, then the entry resolved with `outcome` by `issuer` with `result`. A
  ledger key already present (detection got there first) keeps the existing row
  and inserts nothing; the entry still resolves. It refuses, writing nothing
  even for reviews already processed in the call: any other `outcome`, a
  `detection.outcome` other than `runner_issued` or a `result` without `run_id`
  (`ValueError`); an entry that does not exist, is already resolved, is not a
  review-producing kind, or belongs to another project than a review's detection
  (`InvalidTransitionError`); a verdict already recorded in another project
  (`StoreIntegrityError`).

  The detection row's key must match the one detection would compute, or the
  next scan takes the file as new. `path` is the review file's path as
  detection records it (the registered reviews directory joined with the file
  name), and `digest` is the sha256 hex digest of the bytes of that file (see
  "Review detection" in [`process-contract.md`](process-contract.md)); the
  Runner forms that pair with `amoeba.process.detection_key`, the same function
  detection's files go through. A supplied `journal_entry_id` must be an entry
  on the verdict's own node. The Runner journals a run on the **step node**, the
  work item that carries its attempts, blocks and in-flight state, and records the
  verdict on the **slice node** the review is attributed to, with
  `journal_entry_id=None`. The run is linked to the verdict both ways: the
  verdict carries `sq_run_id`, and the entry's `result` carries the `verdict_ids`
  it recorded.
- **Point 5.** The Runner records its reviews **from the artifact through
  slice 105's parser**, so its record id and detection's are the same
  parsed-content digest. The Runner does not mint verdict ids: each is that
  digest. Any overlap is then a `record_verdict` retry, a no-op, and recording a
  run's reviews twice (a crash, then a repeat) changes nothing.

### The version label on a detected verdict

`upstream_version` is the file's own `squadronVersion` stamp when it carries
one. Otherwise it is the `sq --version` label the process captured **once at
start-up**, or the explicit `unavailable` marker if that failed. It is what
the process observed at start-up, not necessarily what wrote the file.

### Recovering an `unattributed` review by hand

`unattributed` is terminal for detection: retrying later would record old
rounds after newer ones. Once the right slice node exists:

```bash
amoeba inspect detections --project P --outcome unattributed
amoeba ingest review --project P --node ID --by pm --artifact PATH   # oldest round first
```

The ledger row keeps the parsed record id, so `inspect detections` shows
`recorded_since` true once that is done, and ingesting twice is a no-op. An
ingest under an overridden id (`--id`) is not seen by `recorded_since`.

### Accepted limit: multi-part task reviews share a series

Task reviews come in parts (`part-1`, `part-2`, both `reviewType: tasks`, same
slice), and they share one series per node, so part 2's round becomes part
1's "previous round" in `finding_changes`. This affects only that comparison,
not what is recorded. Fixing it (a `source_document` series key) changes this
contract and is tracked as its own follow-up (GitHub issue #3).

## Judge samples

*Added by slice 107.* Three names, used the same way everywhere:

- A **judge invocation** is one request to the Judge for N samples. Its id,
  `judge_invocation_id`, is opaque and supplied by the caller.
- A **judge sample** is a verdict record whose `judge_invocation_id` is set. It
  is recorded through the ordinary `verdict` path: `record_verdict`, the
  `verdict` inbox kind (`--judge-invocation-id` on `amoeba submit verdict`), or
  `amoeba ingest review --judge-invocation-id ID`.
- A verdict without one is an ordinary **review verdict**. Nothing about it
  changes.

Samples of one invocation are recorded one by one and never merged.

**One question (D2).** Every sample of an invocation must be on the same node
and the same `review_type` as the invocation's earliest *recorded* sample. A
mismatch is rejected (`ValueError` from `record_verdict`; `rejected` through the
inbox) with a reason naming both. A rejected sample writes nothing, so it never
defines an invocation. If the first recorded sample was the wrong one, samples
are never edited: **the remedy is a new `judge_invocation_id`.**

**The previous round skips the target's own invocation.** For a judge sample,
`finding_changes` and the previous-round lookup skip samples with the same
`judge_invocation_id`: parallel answers are not successive rounds. Its previous
round can be a sample of an earlier invocation or an ordinary review of the
same type. Ordinary reviews are unaffected.

**Sample ids and retry.** The retry rule is unchanged (first wins). With
`ingest review --judge-invocation-id J` and no `--id`, the record id is the
parsed-review digest, then `.`, then `J`: the same file twice under one
invocation is a no-op, and under a second invocation is a separate sample. The
digest and its format tag do not change; an explicit `--id` is used as given.

**Judge samples are `unattested`.** Squadron omits `verdictSource` on judge
verdicts (the score decides the verdict), so the derivation is `not_reported`
and the trust label is `unattested`. That is accurate, not a defect: it means
"the input did not say how the verdict was reached". Initiative 140 must not
read it as untrustworthy.

**Consensus is not stored.** Turning N samples into a resolution belongs to
initiative 140. The feed's `verdict_recorded` change does not carry
`judge_invocation_id`; read the record by `subject_id`.

### Judge stdout reporting `UNKNOWN` with a score is refused

*An exception to "unknown is a value" (D4; closes GitHub issue #2).* Elsewhere,
unparseable input is recorded as explicitly unknown. `parse_review_json`
instead raises `SquadronParseError` when the stdout JSON has `verdict:
UNKNOWN` **and** a `score`, and `amoeba ingest review --stdout-json` exits
`REVIEW_UNREADABLE` (12) and submits nothing. The stdout verdict may be wrong
(Squadron before 0.21.9 put the real verdict only in the saved file) while a
better source exists. Ingest the saved review file: it records an explicit
unknown (standing `unparsed`) if that is what it says. The rule reads the
JSON's fields, not the template name or the version label. The artifact parser
is unchanged.

## Calibration

`store.calibration(project_id) -> list[CalibrationRow]`, computed on read from
judge samples; also `amoeba inspect calibration --project ID [--json]`. One row
per `(review_type, model)`, ordered by review type, then model, grouped on the
stored values as given.

| Field (listing column) | Meaning |
| --- | --- |
| `samples` | Judge samples in the group. |
| `invocations` | Distinct invocations with a sample in the group. |
| `pass_count` (`pass`), `concerns_count` (`concerns`), `fail_count` (`fail`), `unknown_count` (`unknown`) | Samples by verdict. |
| `provider_failures` | Samples whose trust label is `provider_failure`. |
| `score_min`, `score_mean`, `score_max` | Over samples with a score; `None` when none has one. |

**What it does not do.** It counts and describes each group's samples on their
own. It compares no samples with each other, reports no agreement metric,
recommends no threshold, and reads or writes nothing in Squadron's metrology
store. Per-criterion means are deferred (GitHub issue #6).

**It must not be consumed as agreement evidence.** Squadron's rule is that
verdicts from escalated gates are inadmissible as agreement data, and this
report has no escalated-gate attribute to filter on. Defining that attribute
and computing agreement are initiative 140's (GitHub issue #4).

## Checks

*Added by slice 107.* A mechanical check (a validator, a test run, `cf check`)
is recorded with what it examined. `store.record_check(CheckInput, *,
project_id) -> CheckRecord` is one transaction: retry check (first wins,
WARNING if content differs), then the checks, then the insert. Direct calls
raise `NodeNotFoundError` (node not in the project) or `ValueError`
(`examined_count` negative; empty `upstream_version`); the inbox `check` kind
records the same reasons as `rejected`.

`CheckInput`: `id`, `node_id`, `name` (free data, never logic), `outcome`
(`CheckOutcome`: `passed`, `failed`, `errored`), `examined_count` (`int | None`,
**no default**: pass `None` for "not reported"), `provenance`, optional
`examined` (opaque JSON of what was checked) and `baseline_ref` (opaque, for
example the SHA a result should be compared against; nothing here diffs it).
`CheckRecord` adds `project_id`, `recorded_seq`, `recorded_at`, and `standing`.

**Standing** (`CheckStanding`, `check_standing(outcome, examined_count)`),
checked top to bottom, computed on read and never stored:

| Standing | When |
| --- | --- |
| `errored` | the outcome is `errored` |
| `unattested` | `examined_count` was not reported |
| `vacuous` | `examined_count` is 0, whatever the outcome |
| `passed` / `failed` | the outcome |

**`vacuous` is not `passed`.** A validator that exits 0 having examined zero
files tells you nothing about the code; a failed check that examined nothing
is `vacuous` too. Route on `standing`, not on `outcome`.

Reads: `check(check_id)` (`None` if unknown), `checks(project_id, *,
node_id=None)` in arrival order. `amoeba inspect checks --project ID [--node
ID]` — columns `recorded_seq, id, node_id, name, outcome, examined_count,
standing, baseline_ref, upstream_version`; `--json` rows also carry `upstream`,
`source`, `source_path`, `examined`, `recorded_at`. Through the inbox, see
[`inbox-contract.md`](inbox-contract.md); on the feed,
[`feed-contract.md`](feed-contract.md).

### The Runner's own checks (slice 128; no longer written, slice 132)

Slice 128 had the Runner record three checks on a slice node when a run completed:
`ungate_review_none`, `ungate_effective_date` and `cf_gate_accept_disagreement`, with
provenance upstream `amoeba` and ids `chk-<journal entry id>-<name>`. **Since slice 132
the Runner writes none of them**: they only guarded the Runner's own reads of CF's
review gate, and those reads are gone (each Squadron pipeline owns its gates). Stores
that hold such checks keep them; they are ordinary checks, listed by `amoeba inspect
checks`, and no rule branches on their names. A later user of this contract may record
checks of its own the same way (the retry rule keeps the first record of an id).

## Progress records

SQ 280's four typed artifacts map onto existing records: `review_findings` is a
verdict and its observations; `checkpoint` is a `blocked_on_sq_checkpoint`
node. The other two, `task_progress` and `devlog` (`ProgressKind`), have no
consumer, so they share one table with opaque JSON `content` and the standard
provenance.

`store.record_progress(ProgressInput, *, project_id) -> None` is **write-only**:
a bare insert with no content validation, no retry rule, no feed change, no
inbox kind, no listing. A missing node, a node in another project, or a
repeated id raises `StoreIntegrityError`. The reader and the rest arrive with the first
consumer (GitHub issue #5).

## Storage

Schema version 5 (migration `005`): `verdicts` and `finding_observations`. The
column names are defined once, in `amoeba.store.sql_evidence`. An unknown
vocabulary value in a stored row raises `UnknownVocabularyValueError` on read;
it is never defaulted.

Migration `007` (schema version 7) adds a nullable `verdicts.judge_invocation_id`
and the `check_results` and `progress_records` tables (column names in
`amoeba.store.sql_checks`). Existing verdicts read as `judge_invocation_id` null.

## Future work

- Initiative 140 owns consensus over judge samples, agreement, and the
  escalated-gate attribute (GitHub issue #4).
- Initiative 140 owns deciding that two differently worded findings are the
  same issue.
