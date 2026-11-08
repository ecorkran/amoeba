---
docType: reference
purpose: Provenance of the real upstream fixtures the readers are tested against
dateCreated: 20260921
dateUpdated: 20261108
---

# Upstream fixtures

Every file here is **byte-real upstream output**, copied unmodified from a live
system. None is a hand-written approximation. A parser tested only against
invented data provides false confidence, so the Squadron and Context Forge
readers are tested against these.

Each entry records **the date the fixture was captured**. No upstream version
number is recorded or pinned, deliberately: Squadron and Context Forge both move
without semver, this slice depends on *shapes* rather than versions, and no code
compares an upstream version number. A fixture whose shape stops matching
reality is a reason to recapture it and revisit the reader — a version bump on
its own is not.

**No secrets are present.** The files were scanned before being committed. Nothing was
redacted, so every file has the exact shape the reader meets in production.

## `cf/` — Context Forge plan reads and config

Captured **20261023** from `cf` 0.19.17 (a dated observation, not a pin) against
this repository's CF project, unedited. Each is the output of one command with
`-p <this repository's CF project id>`:

| File | Command | Stream |
| --- | --- | --- |
| `list_initiatives_a.json` | `cf list initiatives --json -a` | stdout, exit 0 |
| `list_slices_120.json` | `cf list slices 120 --json` | stdout, exit 0 |
| `list_slices_100.json` | `cf list slices 100 --json` | stdout, exit 0 |
| `list_slices_error.json` | `cf list slices 140 --json` | **stderr**, exit 1; stdout is empty |

The error document for an initiative with no slice plan is written to **stderr**,
not stdout. The slice 123 design says only "exits 1 with `{"error": true, …}`".
`list_slices_error.json` holds that stderr text. Initiative 120 reports
`status: complete` with `isChecked: false` in `list_initiatives_a.json`.


`config/` holds the captured `cf config get <key> --json` documents the target read and the gate stub use.

## `sq_outcomes/` — `sq runs wait --json` documents

Captured **2026-10-24** with `sq runs wait --timeout 0 --json <run id>` (read-only)
on local runs, each file byte-for-byte as printed (stdout only). Squadron 0.23.7, a
dated observation, not a pin. The run ids were chosen by inspecting the documents,
not by name. Nothing was edited; the documents hold repository-relative paths and
run text, no credentials. The exit code is the outcome's (`completed` 0, `failed` 1,
`paused` 3).

| File | Run | What it shows |
| --- | --- | --- |
| `failed_artifact_missing.json` | `run-20261017-p4-256e7396` | A failed run with `failure` (`artifact_missing`, step `design-0`, a long `message`) |
| `paused_awaits_human.json` | `run-20261016-p56-6f6dfbbb` | A paused run with `checkpoint` (`awaits_human`, step `branch-10`, null `round` and `review_file`) |

### Composed `sq_outcomes/` fixtures (not captures)

The three `composed_*` files are **not** byte-real. They carry the shapes added in
Squadron 0.24.9 (`checkpoint.question`, `checkpoint.resets_at`, `failure.agent_text`),
and no run that produced them could be captured without a paid run. Composed
**2026-10-29** from the producer, `src/squadron/pipeline/run_outcome.py`
(`_checkpoint`, `_agent_question`, `_usage_limit_resets_at`, `_failure`), on top of
the real `paused_awaits_human.json` and `failed_artifact_missing.json`. Recapture
them from a real run when one pauses or fails this way.

| File | What it shows |
| --- | --- |
| `composed_paused_agent_question.json` | `checkpoint.kind` `agent_question` with a `question` |
| `composed_paused_usage_limit.json` | `checkpoint.kind` `usage_limit` with a UTC-offset `resets_at` |
| `composed_failed_agent_text.json` | `failure` `artifact_missing` with `agent_text` |
