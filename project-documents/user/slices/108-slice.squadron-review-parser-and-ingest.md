---
docType: slice-design
slice: squadron-review-parser-and-ingest
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 103, 104]
interfaces: [105, 106]
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: squadron-review-parser-and-ingest

## Overview

Slice 104 built the store for review results, but it reads nothing from Squadron. Callers have to hand it a ready-made `VerdictInput`. Today that means typing roughly twenty `amoeba submit verdict` flags by hand. This slice adds the missing piece, and nothing more:

1. **A Squadron review parser.** `amoeba.upstream.squadron` turns the stdout of `sq review … --output json`, or a saved review file, into a `ParsedReview`, and composes a `VerdictInput` from it. It is pure: text in, typed value out. It opens no store and reads no files.
2. **`amoeba ingest review`.** The command reads a file, parses it, and submits the result through 103's inbox as a `verdict`. It works with the process running or stopped. Ingesting the same review twice records it once.
3. **A record id taken from the parsed review.** The id is a digest of what the parser read, not of the file's bytes. Slice 105's detection, `amoeba ingest review`, and the Runner (120) therefore all arrive at the same id for the same review. Adding a `resolution:` key to a file by hand leaves its id unchanged.

The first draft of this design sits inside slice 104's draft at commit `c525a63`. This document starts from that draft and brings it up to date against Squadron as it is today.

## Value

Developer value:

- A real review becomes a stored record with one command.
- Slice 105 can ingest reviews it finds on disk before initiative 120 exists, which the sequencing requires.
- 105, 120, and the PM share one parser. Every caller maps a given Squadron review the same way.
- 104 tested its matching rule on finding text taken straight from the fixtures, so its tests never exercised the real input path. This slice re-runs those tests through the parser, so they now read what production reads.

## Technical Scope

**Included**

- The `amoeba.upstream` package, with `amoeba.upstream.squadron` inside it, exporting `parse_review_json`, `parse_review_artifact`, `ParsedReview`, `to_verdict_input`, `review_record_id`, and `SquadronParseError`.
- `amoeba.upstream.squadron.review_fields`, which defines every Squadron key name and literal the parser reads, each exactly once.
- `verdict_to_payload(VerdictInput)` in `amoeba.store.verdict_payload`. It is the inverse of 104's `verdict_from_payload` and uses the same key constants.
- The `amoeba ingest review` command in a new `cli/ingest.py`, registered in `cli/main.py`, with one new `ExitCode` member.
- PyYAML moves from dev to runtime dependencies. `types-pyyaml` stays in dev.
- New real fixtures in `tests/fixtures/sq_reviews/`, recorded in the README (see Technical Requirements).
- 104's fixture reader (`tests/review_fixtures.py`) is replaced by the parser, so 104's matching tests run through production code.
- Documentation: a new "Parsing Squadron output" section in `docs/evidence-contract.md` replaces 104's "Mapping Squadron's flags (for slice 108)" notes. `amoeba ingest review` and its exit code are added to `process-contract.md`. `CHANGELOG.md` gets an entry.

**Excluded**

- **Store schema changes.** There is no migration and no new column or table. The parser fills only the fields `VerdictInput` already has.
- **`source_document`.** The parser exposes `sourceDocument` on `ParsedReview` and includes it in the record id, but it does not pass the value to `VerdictInput`. Slice 105 adds that field (its D7) and the one-line pass-through in `to_verdict_input`.
- **Judge samples** (`judge_invocation_id`), calibration, and check results. These belong to slice 109.
- **Detecting review files on disk.** That is slice 105.
- **Parsing other Squadron output.** Run files stay in `process/observers/sq_runs.py`, and pipeline state and checkpoint prompts belong to 120. Parsing CF MCP results is also 120's.
- **Storing Squadron's newer diagnostics.** The parser reads these keys and drops them: `location_verified`, `finding_scan`, `diff_chars`, `diff_chars_injected`, `answering_models`, `stop_reason`, and `tools_given`. Nothing consumes them yet. Adding one later means adding a `VerdictInput` field.
- **Checking that the node exists before submitting.** `submit()` is fire-and-forget by design (103). An unknown node shows up as a `rejected` submission, which the PM sees in `inspect submissions`.

## Dependencies

### Prerequisites

- **Slice 104:** `VerdictInput`, `FindingInput`, `Provenance`, the vocabularies, `parse_verdict` and `parse_severity`, the `verdict` inbox kind and its payload keys, the "first wins" retry rule, and `docs/evidence-contract.md`.
- **Slice 103:** `submit()` and its D2 rule: a repeated submission id is a no-op. *Added at slice design:* the slice plan lists only 104, but ingest writes through 103's inbox.
- **Slice 101:** `amoeba.store.paths` for the supervisor directory, reached through `submit()`.
- **PyYAML** (already locked as a dev dependency by 104), read with `safe_load` only.

### Interfaces Required

**What Squadron writes today.** This is a dated observation, not a version pin. It was checked on 20260928 against squadron `main` at `373217ab` (package 0.15.0, the version installed as `sq`), in `review/models.py::to_dict`, `review/persistence.py`, and `cli/commands/review.py`. Squadron issue #139 is closed.

- **Stdout JSON** always carries these keys: `verdict`, `verdictSource` (`stated` / `derived` / `imposed`, or null when nothing parsed), `fallback_used`, `structured_findings[]` (`id`, `severity` in lowercase, `category`, `summary`, `location`, `location_verified`), `template_name`, `model`, `requested_model`, `model_substituted`, `diff_truncated`, `score`, `criteria`, `tool_calls_made`, `run_id` (null on the CLI), and `squadron_version`. `findings[]` holds the long form (`title`, `description`, severity in uppercase), which the parser does not read. Under `--output json`, the `Saved review to` line goes to stderr, so stdout is one JSON object.
- **When the provider fails, stdout JSON has no object at all.** The CLI prints a red error line to stdout and saves a failure file. The failure exists only in that file.
- **Review file frontmatter** always carries `reviewType`, `project`, `verdict`, `sourceDocument`, `aiModel`, and `squadronVersion`. `slice` is present for slice reviews; a PR review has a nested `pr:` mapping and no `slice`. The rest appear only when they apply:
  - `providerFailure: true` on a failure
  - `verdictSource`, absent when nothing parsed
  - `requestedModel`, only when the model was substituted
  - `reviewedSha`
  - `toolCallsMade`
  - `diffTruncated`, only when the review had a diff
  - `runId`, only on pipeline runs
  - `findings:`, absent when the list is empty
- **Two body headings carry information the frontmatter does not:** `## Provider Failure` and `## Findings Not Parsed`. Files written before #139 marked a failure with the heading only.
- **Where requested model differs:** frontmatter writes `requestedModel` only when the model was substituted, but JSON always writes `requested_model`. 104's contract field is "set only on a substitution".
- **Judge templates:** stdout JSON still reports `verdict: UNKNOWN` (squadron#140, open). The file carries the verdict derived from the score.
- **Positional ids:** squadron#141 (log-side `F` numbering) is still open. It does not matter here, because positional ids are stored as data only.

From Amoeba:

- `submit()` and `InboxSubmitError` from `amoeba.inbox`.
- 104's `VERDICT_*` and `FINDING_*` key constants.
- The `ExitCode` enum and the boundary handler in `cli/main.py`.

## Architecture

### Component Structure

```
src/amoeba/
  upstream/
    __init__.py
    squadron/
      __init__.py          re-exports the public names below
      review.py            parse_review_json, parse_review_artifact, ParsedReview,
                           to_verdict_input, review_record_id, SquadronParseError
      review_fields.py     Squadron key names, literals, and the two body headings
  store/
    verdict_payload.py     + verdict_to_payload (inverse of verdict_from_payload)
  cli/
    ingest.py              add_ingest_parser, run_ingest
    main.py                registers ingest; ExitCode.REVIEW_UNREADABLE
tests/upstream/            parser tests against every fixture
tests/cli/test_ingest.py   ingest through the real CLI
```

If `review.py` grows past about 300 lines, the two readers split into `review_json.py` and `review_artifact.py`, and `review.py` keeps `ParsedReview` and the composition.

**Dependency direction.**

- `amoeba.upstream.squadron` imports only store vocabularies and dataclasses (`evidence_models`). It never imports `Store`, `amoeba.inbox`, or `amoeba.process`.
- The store never imports `amoeba.upstream`.
- `cli/ingest.py` is the only module that knows both the parser and the inbox. For 105, the equivalent is its detection tenant, which knows both the parser and the store.
- Slice 106 plans a `run_pruning.py` in the same package, as a sibling module. Nothing here depends on it.

### Data Flow

**Parse** (pure, in any process):

```
parse_review_artifact(text)                parse_review_json(text)
  split the leading ---/--- frontmatter      find the first "{" and raw_decode it; ignore the rest
  yaml.safe_load → mapping                   must be an object with a "verdict" key
  scan the body for the two headings
            └────────────── map fields (D3) ──────────────┘
                                ↓
                  ParsedReview (frozen; findings in order)
```

**Compose.** `to_verdict_input(parsed, *, node_id, …)` → `VerdictInput`. The id defaults to `review_record_id(parsed)`. `upstream` is `squadron`. The upstream version comes from the review's own stamp, or from the caller when there is no stamp (D4).

**Ingest** (the CLI; the process may be running or stopped):

```
amoeba ingest review --project P --node N --by B (--artifact F | --stdout-json F)
  read F as UTF-8             → OSError / UnicodeDecodeError: exit REVIEW_UNREADABLE
  parse                       → SquadronParseError: exit REVIEW_UNREADABLE
  to_verdict_input(source_path = F resolved to an absolute path)
                              → a missing version label: exit REVIEW_UNREADABLE
  submit(kind=verdict, payload=verdict_to_payload(input), submission_id=input.id)
                              → InboxSubmitError: exit SUBMISSION_REFUSED
  print the submission id; exit OK
```

At every failing step, nothing reaches `inbox/new/`. When the resident process applies the submission, it records the verdict with the submission id as the record id (104).

**Duplicates.** Ingesting the same review a second time reuses the same submission id, and 103's D2 makes that submission a no-op. If 105's detection already recorded the review directly under the same id, the submission applies, and `record_verdict` returns the existing record (first wins, with a WARNING if the content differs).

### State Management

This slice adds no state of its own. The parser holds none, and ingest writes one inbox file, which becomes one verdict record through 103 and 104.

## Technical Decisions

D1 was set by PM direction at the 104 split. D2 through D6 are pending PM ratification.

### Technology Choices

**D1 — The parser is an adapter package outside the store. (PM directed 20260926, carried from 104's D1.)** It lives in `amoeba.upstream.squadron`, not in the Runner (120), because 105 runs before 120 exists. It is pure, so 105's tenant and 120's Runner call it in-process, and `amoeba ingest` calls it from the command line. It parses Squadron's **review output only**.

**D2 — Frontmatter is read with a real YAML parser.** Review frontmatter contains nested lists (`findings:`), nested mappings (`pr:`), and quoted strings containing colons and backticks. A hand-written reader would be a parser that fails on valid input without saying so. The parser calls `yaml.safe_load`, and nothing else. PyYAML becomes a runtime dependency. It is already locked for 104's tests.

**Leniency, per the project's parsing rules.**

- The frontmatter fence is a line of `---` plus optional trailing whitespace. Leading blank lines are allowed.
- The body headings match at any level (`#` through `######`), in any case, with surrounding whitespace ignored.
- For stdout, decoding starts at the first `{`, and anything after the object is ignored. That tolerates a 0.14.0 capture whose `Saved review to` line is on stdout.
- Keys the parser does not know are ignored. That includes the `resolution:` and `resolvedBy:` keys this repository adds to review files by hand.

### Patterns and Conventions

**D3 — One mapping table, defined in `review_fields.py` and `review.py`.**

| `ParsedReview` field | From stdout JSON | From a review file |
| --- | --- | --- |
| `verdict` | `verdict` (via `parse_verdict`) | `verdict` |
| `derivation` | `verdictSource`; `not_reported` if null or absent | `verdictSource`; `not_reported` if absent |
| `fallback_used` | `fallback_used`; `None` if absent | `None` (the file does not carry it) |
| `findings_parsed` | `False` when `fallback_used` is true and derivation is `stated` or `not_reported`; `None` when `fallback_used` is absent; otherwise `True` | `False` when the body has a *Findings Not Parsed* heading; otherwise `True` |
| `provider_failure` | `False` (a failure produces no JSON) | `True` when `providerFailure: true`, **or** the body has a *Provider Failure* heading |
| `review_type` | `template_name` | `reviewType` |
| `model` | `model` | `aiModel` |
| `requested_model` | `requested_model` only when `model_substituted` is true; otherwise `None` | `requestedModel` |
| `diff_truncated` | `diff_truncated` | `diffTruncated` |
| `reviewed_sha` | `None` (not in JSON) | `reviewedSha` |
| `tool_calls_made` | `tool_calls_made` | `toolCallsMade` |
| `score`, `criteria` | `score`, `criteria` | `score`, `criteria` |
| `sq_run_id` | `run_id` | `runId` |
| `upstream_version` (the stamp) | `squadron_version` | `squadronVersion` |
| `findings` | `structured_findings[]` | `findings:` (absent means an empty list) |
| `slice` | `None` | `slice` (absent on PR reviews) |
| `source_document` | `None` | `sourceDocument` |
| `source` | `stdout_json` | `artifact_frontmatter` |

Each finding maps as follows:

- `id` → `position_id`
- `severity` → `parse_severity`
- `category`, `summary`, `location` pass through as written, including Squadron's `unverified` literal, which 104's matching rule already treats as empty

Four rules apply on top of the table:

- **`requested_model` follows the contract, not the raw key.** 104's contract says the field is set only on a substitution, which is also Squadron's own rule for writing the key to a file. Copying JSON's `requested_model` whenever it is present would make stdout and file disagree about the same review.
- **The zero-findings rule belongs to Squadron, so it lives here.** A CONCERNS or FAIL with `fallback_used` and a stated verdict means the findings failed to parse. The standing function reads only `findings_parsed`, so other submitters are not caught by Squadron's rule.
- **`source_document` is taken from files only.** JSON's `input_files.input` is whatever path the caller typed, which can differ in spelling from the `sourceDocument` a file carries. Using it would split one review series into two once 105 separates series by document.
- **Nothing is defaulted.** Any of the following raises `SquadronParseError`, naming the key and the source:
  - a missing `verdict`, review type, or model
  - an unknown verdict or severity word
  - a finding that is not a mapping, or lacks `severity` or `summary`
  - frontmatter that is not a mapping
  - malformed YAML or JSON (the underlying error is chained)
  - no JSON object in the text
  - a JSON object with no `verdict` key

  A provider's error body printed to stdout is the practical case for the last one.

**D4 — The upstream version is Squadron's stamp when there is one, and the caller's label otherwise. The two may not disagree.** `to_verdict_input(parsed, *, node_id, upstream_version=None, …)` resolves the version this way:

- The stamp is used when present.
- The argument is used when there is no stamp. That covers files written before #139.
- With neither, it raises `ValueError`.
- With both, and different, it raises `ValueError`. A silent choice between two labels would hide a mistake.

As in 104, the label is never compared or branched on beyond that equality check.

**D5 — The record id is a digest of the parsed review. (Required by 105.)** `review_record_id(parsed)` returns `sq-review-` followed by the first 32 hex characters of the SHA-256 of a canonical JSON encoding of the `ParsedReview`. The encoding uses sorted keys and compact separators, puts findings in order, and starts with a digest-format tag, `parsed-review-v1`. The id changes only when the review's parsed content changes.

The digest covers every `ParsedReview` field, including `source`, `slice`, and `source_document`. It excludes everything the caller supplies: node, path, the caller's version label, and journal entry. Consequences:

- A hand edit that adds `resolution:` or `resolvedBy:` does not change the id. The same file ingested by the PM, found by 105, or recorded by 120 from the file gets the same id.
- A file and a stdout capture of the same review get **different** ids, because they carry different fields (for example, `reviewed_sha` exists only in the file). That is accepted: 105's D5 has the Runner record its reviews from the file, so every path to a stored review goes through the file.
- Changing which fields the digest covers changes every id, so any such change is a contract change. It requires a new format tag and a `CHANGELOG` entry. Adding a new field to `ParsedReview` counts, so D3's "drop diagnostics" rule also keeps ids stable.

`to_verdict_input(record_id=…)` and `amoeba ingest review --id` override the default. The Runner, for example, can use an id it created when it journaled the command.

*Rejected:* a digest of the raw bytes, which was the first draft's choice. Every hand edit would then become a second verdict for the same review (105's review of this point).

**D6 — `ingest` submits and does not wait.** Ingest reports the submission id, not the outcome. It works like `submit` and the rest of 103's contract: the process may be stopped, and the outcome is read afterwards with `inspect submissions` or `inspect verdicts`. Waiting for the process to apply the submission would tie a file-parsing command to the process being up.

**Error handling.**

- `SquadronParseError(ValueError)` carries a `source` (`stdout_json` or `artifact_frontmatter`) and a message naming the key.
- `cli/ingest.py` catches `OSError`, `UnicodeDecodeError`, `SquadronParseError`, and the version-label `ValueError` in explicit branches, prints the error to stderr, and returns `ExitCode.REVIEW_UNREADABLE`.
- `InboxSubmitError` is already mapped to `SUBMISSION_REFUSED` by the boundary handler.
- No broad `except` is added.

## Implementation Details

### API Contracts

**`amoeba.upstream.squadron`:**

| Call | Effect |
| --- | --- |
| `parse_review_json(text: str) -> ParsedReview` | Decodes the first JSON object and maps it by D3. |
| `parse_review_artifact(text: str) -> ParsedReview` | Splits and loads the frontmatter, scans the body headings, and maps by D3. |
| `review_record_id(parsed: ParsedReview) -> str` | D5. |
| `to_verdict_input(parsed, *, node_id, record_id=None, upstream_version=None, journal_entry_id=None, source_path=None) -> VerdictInput` | Builds the store input. The id defaults to `review_record_id(parsed)`, `upstream` is `"squadron"`, and the version follows D4. |

`ParsedReview` is a frozen, keyword-only dataclass. It has the `VerdictInput` review fields (`verdict`, `derivation`, `fallback_used`, `findings_parsed`, `provider_failure`, `review_type`, `model`, `requested_model`, `diff_truncated`, `reviewed_sha`, `tool_calls_made`, `score`, `criteria`, `sq_run_id`, and `findings: tuple[FindingInput, ...]`), plus `source: RecordSource`, `upstream_version: str | None` (the stamp), `slice: str | None`, and `source_document: str | None`.

**`amoeba.store.verdict_payload.verdict_to_payload(verdict: VerdictInput) -> dict[str, object]`.** The result has every `VERDICT_PAYLOAD_KEYS` key and none other, and findings are lists of `FINDING_PAYLOAD_KEYS` mappings. It satisfies `verdict_from_payload(v.id, verdict_to_payload(v)) == v`.

**CLI:**

```
amoeba ingest review --project ID --node NODE_ID --by NAME
                     (--artifact PATH | --stdout-json PATH)
                     [--upstream-version LABEL] [--id ID]
```

It prints the submission id on stdout. Exit statuses:

- `OK` on success
- `REVIEW_UNREADABLE` (new, `12`) when the file could not be read or parsed, or has no version label
- `SUBMISSION_REFUSED` when the inbox refused the submission

A failing run prints the error on stderr and leaves nothing in the inbox. The subcommand is `ingest review` rather than a flat `ingest`, so that later ingest sources, if any, have a place to go.

## Integration Points

### Provides to Other Slices

- **105:**
  - `parse_review_artifact`, `to_verdict_input`, and `review_record_id`, called in-process by the detection tenant.
  - `ParsedReview.slice`, for attribution.
  - `ParsedReview.source_document`, which 105 passes on to its new `VerdictInput.source_document` field.
  - The parsed-content id, stored as the ledger's `record_id`.
  - `amoeba ingest review --node`, used to recover unattributed files and to backfill.
  - `SquadronParseError` messages, used as the `unparseable` detail.
- **106:** the parser, used by `ProofRunner` for its own reviews, and `amoeba ingest review`.
- **Initiative 120:** the parser for the reviews the Runner launches, read from the file per 105's D5, with `record_id` and `journal_entry_id` supplied by the Runner.
- **109:** the judge fields (`score`, `criteria`) are already parsed. 109 adds `judge_invocation_id` to `to_verdict_input` and to `ingest`.

### Consumes from Other Slices

- **104:** unchanged. It gains one additive function, `verdict_to_payload`. `evidence-contract.md`'s Squadron-mapping notes move into the new parsing section.
- **103:** `submit()`, unchanged.
- **The `cli/main.py` boundary handler:** unchanged apart from the new exit code and the registered subcommand. `process-contract.md` lists both.

## Success Criteria

### Functional Requirements

- Every review file in `tests/fixtures/sq_reviews/` parses to the verdict, derivation, and findings (count, order, severity, summary, location, positional id) its frontmatter states. A table-driven test pins each file's expected `ParsedReview` standing.
- Both provider-failure files parse with `provider_failure=True`, no findings, and standing `provider_failure`. The 0.14.0 file is marked by its heading only; the 928 file has `providerFailure: true`, a `runId`, and a stamp.
- The *Findings Not Parsed* file parses with `findings_parsed=False`.
- The PR review parses with `slice=None`, and its `pr:` mapping is ignored without error.
- The 0.15.0 file yields `sq_run_id` and `upstream_version` from `runId` and `squadronVersion`.
- Each stdout capture parses. The clean PASS gives `findings_parsed=True` and standing `stated`. The 0.14.0 captures, which have a trailing stdout line, parse the same as a pure-JSON capture.
- JSON with `fallback_used: true` and `verdictSource: stated` gives `findings_parsed=False`. With `verdictSource: derived`, it gives `True` and standing `derived`.
- JSON `requested_model` is kept only when `model_substituted` is true.
- In the captured 0.15.0 file/stdout pair, both sources produce the same verdict, review type, model, and **finding keys** (`finding_identity` over each finding) in the same order.
- `review_record_id` is unchanged by adding `resolution:` and `resolvedBy:` keys, or a `## Response` section, to a fixture's text. It changes when a finding's summary changes.
- Each of these raises `SquadronParseError`, and a test covers each: a missing `verdict`, an unknown severity, frontmatter that is not a mapping, malformed YAML, text with no JSON object, and a JSON object with no `verdict`. `to_verdict_input` raises when there is no version label at all, and when the stamp and the argument disagree.
- `amoeba ingest review` on a real file, with the process running, produces one verdict whose id is the digest id, with `source_path` set to the file's absolute path. Ingesting it a second time produces no second record.
- Ingesting a file that is unparseable, missing, or has no version label exits `REVIEW_UNREADABLE` and leaves `inbox/new/` empty.
- Ingest works with the process stopped. The submission is applied at the next start.

### Technical Requirements

- Squadron key names, literals, and heading texts are defined once, in `review_fields.py`. `upstream` (`"squadron"`) and the digest format tag are constants.
- `amoeba.upstream` imports nothing from `amoeba.inbox`, `amoeba.process`, or `Store`. The store imports nothing from `amoeba.upstream`. A test asserts both.
- `verdict_to_payload` round-trips with `verdict_from_payload`, tested over every field, including nulls and findings.
- 104's matching and `finding_changes` tests read the fixtures through `parse_review_artifact`. `tests/review_fixtures.py` keeps only the fixture paths. Its YAML reader and heading regex are deleted.
- **New fixtures**, copied byte for byte with `cp`, each given a README entry with capture date, origin, and reason. Before copying, each file is checked for hand edits (`resolution`, `resolvedBy`, or an appended `## Response`); any file that has one is left out.
  - `928-review.slice.codex-parity-for-skill-packs-and-provider-access.20260927T212759.md`, from Squadron's `reviews/archive/`: a provider failure with `providerFailure: true` and `runId`.
  - `925-review.code.command-install-target-parity-codex-via-the-agents-skill-layout.20260922T145229.md`, from Squadron's `reviews/archive/`: *Findings Not Parsed*, verdict `UNKNOWN`.
  - `github.com-ecorkran-squadron-116-review.code.md`, from Squadron's `reviews/`: a PR review with a nested `pr:` mapping and no `slice`.
  - `105-review.slice.outbound-change-feed-and-detection-of-external-work.20260928T175751.md`, from this repository's `reviews/archive/`: 0.15.0, with `runId` and `squadronVersion`.
  - **A new 0.15.0 file/stdout pair** from one `sq review … --output json` saved **with** a slice number, with stdout and stderr captured to separate files. It is captured at implementation time with `--model glmflash` in a throwaway copy of this repository, so nothing lands in the real reviews directory. It pins that stdout is pure JSON, that `template_name` equals `reviewType`, and that the finding keys match.
- **A known gap.** No real file with a *Findings Not Parsed* heading **and** a CONCERNS or FAIL verdict has been found. The README records it as missing. That parser branch is tested on a copy of a real file with the heading added, and the README labels the copy as edited.
- `ruff`, `pyright` strict, and the full suite are clean. Source files stay near 300 lines.
- `docs/evidence-contract.md` gains a "Parsing Squadron output" section: the D3 table, D4, D5 (with what changes an id), what is dropped, and the dated observation. `process-contract.md` documents `ingest review` and exit code 12. `CHANGELOG.md` is updated.

### Integration Requirements

- An end-to-end test drives the real CLI as subprocesses: create a project, seed a node, ingest two rounds and a provider failure, ingest round 1 again, then `kill -9` and `start`. Read-only inspection must then show exactly three verdicts with the expected standings, and round 2's changes against round 1.
- Slice 105's design needs no names beyond those listed under Provides to Other Slices.

### Verification Walkthrough

Draft; refined with captured output when Phase 6 completes. It reuses 104's `scripts/demo_evidence.py` to seed a node, because nothing outside the process can create one until 120.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
uv run amoeba start &
uv run amoeba submit create-project --project demo --by pm
uv run amoeba stop
NODE=$(uv run python scripts/demo_evidence.py)
uv run amoeba start &
F=tests/fixtures/sq_reviews
```

**1. A real review with one command.**

```bash
uv run amoeba ingest review --project demo --node "$NODE" --by pm \
  --artifact "$F/102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md" \
  --upstream-version 0.14.0
```

Expected:

- The command prints `sq-review-` followed by 32 hex characters.
- `uv run amoeba inspect verdicts --project demo` shows one `tasks` verdict, `CONCERNS`, standing `stated`.
- `inspect verdicts --json` shows `source: artifact_frontmatter`, `source_path` as the absolute fixture path, and `upstream_version: 0.14.0`.

**2. The stamp supplies the version.** Ingest the 0.15.0 fixture (`105-review.slice…20260928T175751.md`) without `--upstream-version`. Expected: its row shows `upstream_version: 0.15.0`, and `--json` shows `sq_run_id: run-20260928-slices-plan-a04bdb07`. Running it again with `--upstream-version 0.14.0` exits `12`, with a message naming both labels.

**3. Provider failures and degraded reviews.** Ingest the two provider-failure fixtures (the 102 part-2 round-2 file and the 928 file) and the 925 *Findings Not Parsed* file. Expected standings: `provider_failure`, `provider_failure`, `unparsed`.

**4. Round 2 compares against round 1.** Ingest `102-review…part-1.md` (round 2). Then run `uv run amoeba inspect changes --project demo --verdict <round-2 id>`. Expected: round 1 is named as the previous round, no finding is `recurring`, and every round-1 finding is `gone`. This is 104's rewording limit, now shown through the parser.

**5. Ingesting twice records once.** Repeat step 1's command. It prints the same id. Then:

```bash
cp "$F/102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md" /tmp/r1.md
printf '\n## Response\nhand-added note\n' >> /tmp/r1.md
perl -pi -e 's/^(verdictSource: stated)$/$1\nresolution: addressed/' /tmp/r1.md
uv run amoeba ingest review --project demo --node "$NODE" --by pm --artifact /tmp/r1.md --upstream-version 0.14.0
```

Expected: the same id as step 1 again. `inspect verdicts` still shows one row for that review, and `inspect submissions` shows the repeats as no-ops.

**6. Unparseable input submits nothing.**

```bash
echo '# not a review' > /tmp/bad.md
uv run amoeba ingest review --project demo --node "$NODE" --by pm --artifact /tmp/bad.md --upstream-version x; echo "exit $?"
ls "$AMOEBA_STORE_DIR/inbox/new"
```

Expected: `SquadronParseError: … no frontmatter`, `exit 12`, and an empty `new/`.

**7. Stdout JSON.** Ingest the new 0.15.0 stdout capture with `--stdout-json`. Expected: `source: stdout_json`, `reviewed_sha` null, and a different id from its paired file (D5). `uv run amoeba inspect findings --project demo --node "$NODE"` shows its finding keys shared with the paired file, each seen twice.

**8. Survives a crash.** `kill -9` the process, then run `uv run amoeba start &`. Expected: `inspect verdicts` lists the same rows, and nothing is applied twice.

**9. The parser against every fixture.**

```bash
uv run pytest tests/upstream tests/store/test_finding_identity.py tests/store/test_finding_changes.py -v
```

Expected: every fixture parses to its stated fields, and 104's matching tests pass reading through the parser.

## Risk Assessment

### Technical Risks

- **Squadron's output shape changes without semver.** It changed twice while this slice and 104 were being designed (SQ 927, #139). A parser that failed quietly on a new shape would record wrong verdicts. That failure is worse than not recording them.

### Mitigation Strategies

- Required keys raise; they are never defaulted. Optional keys map to null when absent. Unknown keys are ignored. So Squadron adding a key breaks nothing, and Squadron removing or renaming a required key fails loudly: 105 lists the file as `unparseable`, and ingest exits 12.
- Every record carries Squadron's version label, so the records a shape change touched can be found.
- Every fixture has a capture date, and a real 0.15.0 pair is captured at implementation. A stale fixture shows up as a reason to recapture.

## Implementation Notes

### Development Approach

1. **Fixtures.** Copy the new files, check each for hand edits, update the README, and capture the 0.15.0 file/stdout pair.
2. **Keys and the review-file reader.** Write `review_fields.py`, `ParsedReview`, `SquadronParseError`, and `parse_review_artifact`, tested against every file fixture, including the error cases.
3. **The stdout reader.** Write `parse_review_json`, tested against the three stdout captures. Pin the file/stdout finding-key equality and the `template_name`/`reviewType` equality on the new pair.
4. **Composition.** Write `review_record_id` and `to_verdict_input`, including the hand-edit invariance test and the D4 cases.
5. **The payload inverse.** Write `verdict_to_payload` and its round-trip test.
6. **Test migration.** Switch 104's fixture-reading tests to the parser and delete the old reader.
7. **The command.** Write `cli/ingest.py`, `ExitCode.REVIEW_UNREADABLE`, and the registration, then the end-to-end CLI test.
8. **Docs and dependencies.** Update `evidence-contract.md`, `process-contract.md`, and the `CHANGELOG`, and move PyYAML to runtime.

Test each step as soon as it is built, and commit after each step.

### Special Considerations

- **Fixtures come from another repository.** Four new review files are copied from Squadron's reviews directory. They contain review text about Squadron code, and no secrets. The README scan note is extended to cover them.
- **Tests must not read `project-documents/user/reviews/` directly.** The parser's tests read only `tests/fixtures/`, so a new review round in this repository cannot change the test results.
