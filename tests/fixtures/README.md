---
docType: reference
purpose: Provenance of the real upstream fixtures the observers are tested against
dateCreated: 20260921
dateUpdated: 20261014
---

# Upstream fixtures

Every file here is **byte-real upstream output**, copied unmodified from a live
system. None is a hand-written approximation. A parser tested only against
invented data provides false confidence, so the Squadron and Context Forge
observers are tested against these.

Each entry records **the date the fixture was captured**. No upstream version
number is recorded or pinned, deliberately: Squadron and Context Forge both move
without semver, this slice depends on *shapes* rather than versions, and no code
compares an upstream version number. A fixture whose shape stops matching
reality is a reason to recapture it and revisit the observer — a version bump on
its own is not.

**No secrets are present.** The files were scanned before being committed. Two
Squadron runs contain the error text `No API key found. Set OPENROUTER_API_KEY
environment variable.` — that is an upstream error *message* naming an
environment variable, not a credential. Nothing was redacted, so every file has
the exact shape the parser meets in production.

## `sq_runs/` — Squadron run-state files

Captured **20260921** from `~/.config/squadron/runs/`.

| File | `status` | `pipeline` | `schema_version` | Why it is here |
| --- | --- | --- | --- | --- |
| `run-20260411-p5-93bf1c90.json` | `completed` | `p5` | 3 | The ordinary case, and an older schema version |
| `run-20260411-test-review-a50207b1.json` | `failed` | `test-review` | 3 | The `failed` status the LLD requires |
| `run-20260505-review-a697ad3d.json` | `paused` | `review` | 4 | The `paused` status the LLD requires; paused runs are never pruned |
| `run-20260801-loop-smoke-b095fb0d.json` | `completed` | `loop-smoke` | 4 | Empty `params`, which the subset matcher must handle |

The spread is deliberate: two schema versions, both required statuses, and a run
whose `params` are empty. The observer reads only the six header fields
(`schema_version`, `run_id`, `pipeline`, `params`, `started_at`, `status`) and
ignores everything else these files carry, which is most of their bulk.

## `cf/` — Context Forge project records

Captured **20260921** from `cf get --json` run against this repository.

| File | Why it is here |
| --- | --- |
| `cf_get_amoeba.json` | A real project record, carrying `updatedAt` — the field the CF observer records as provenance |
| `projects.json` | A real CF data file reduced to three entries, for the `projects.json` parser (slice 108) |

`projects.json` was captured 2026-10-16 from `~/.config/context-forge/projects.json`
(observed on CF 0.19.13, a dated observation, not a pin). Reduction: the 29 entries
were cut to three, unedited and in original order: `hydrology-dashboard` and
`ai-project-guide` (neither has `worktrees`), and `amoeba` (has `worktrees`, with a
`default` worktree holding `developmentPhase`, `activeSlice`, `activeTaskFile`). The only edit
is re-serialization at 2-space indent. No `customData` was edited (all three are empty
objects). The entries hold local paths and nothing secret.

Note what this fixture does **not** contain: any version field. That absence is
why the CF observer captures an opaque `cf --version` label separately, once per
recovery pass, rather than reading a version out of this output.

## `sq_reviews/` — Squadron review output

### Review files

Copied **20260927** from `project-documents/user/reviews/archive/` with `cp`, byte for byte. They were written by Squadron on **20260921** during slice 102's two task-review rounds. Slice 104's matching-rule and `finding_changes` tests read them.

| File | `verdict` | `reviewedSha` | Why it is here |
| --- | --- | --- | --- |
| `102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md` | CONCERNS | `bf6d292` | Round 1, part 1: nine findings. The baseline for the rewording test. |
| `102-review.tasks.resident-process-and-recovery.part-2.20260921T112635.md` | PASS | `bf6d292` | Round 1, part 2: a real PASS that carries findings. |
| `102-review.tasks.resident-process-and-recovery.part-1.md` | CONCERNS | `20b3d70` | Round 2, part 1: seven findings, every carried-over one reworded. It shares no key with round 1, which pins the rewording limit. |
| `102-review.tasks.resident-process-and-recovery.part-2.md` | `UNKNOWN` | `20b3d70` | Round 2, part 2: a real provider failure (a *Provider Failure* heading, no findings, no `verdictSource`). |

Both part-1 files say `verdictSource: stated`.

**Left out on purpose.** The matching tests are only as honest as their input, so no hand-edited review is copied here:

- Files carrying `resolution:` or `resolvedBy:` keys, which Squadron never writes: every `103-review.*` file, including the archived task review.
- `103-review.code.durable-inbox-and-message-queue.md`, which was also written by hand from terminal output after Squadron did not save the run.
- Any review with a `## Response` section appended after the run (the 103 and 104 reviews).

The other Squadron review files in `project-documents/user/reviews/` are unedited but have no test that needs them, so they are not copied.

### Review files from other runs (slice 105)

Copied **20261009** with `cp`, byte for byte, for the slice 105 parser tests. Four files come from other repositories or other runs: three from the Squadron repository (`../squadron`) and one from this repository. They contain review text about Squadron code and about this project's design. They were checked for secrets and for `resolution:`, `resolvedBy:` and `## Response` markers; none has any.

| File | `verdict` | Written | Origin | Why it is here |
| --- | --- | --- | --- | --- |
| `928-review.slice.codex-parity-for-skill-packs-and-provider-access.20260927T212759.md` | `UNKNOWN` | 20260927 | Squadron `reviews/archive/` | A current-format provider failure: `providerFailure: true`, a *Provider Failure* heading, `runId`, `squadronVersion: 0.14.0`. |
| `925-review.code.command-install-target-parity-codex-via-the-agents-skill-layout.20260922T145229.md` | `UNKNOWN` | 20260922 | Squadron `reviews/archive/` | A *Findings Not Parsed* heading with verdict `UNKNOWN`. |
| `github.com-ecorkran-squadron-116-review.code.md` | `UNKNOWN` | 20260918 | Squadron `reviews/` | A PR review: nested `pr:` mapping and no `slice` key. |
| `106-review.slice.outbound-change-feed-and-detection-of-external-work.20260928T175751.md` | CONCERNS | 20260928 | this repo's `reviews/archive/` | A stamped review with `runId` and `squadronVersion: 0.15.0`. |

### Known gap, and the one edited file

No real review file has a *Findings Not Parsed* heading together with a CONCERNS or FAIL verdict. The parser still has to handle that combination, so one fixture stands in for it. It is **edited**, unlike every other file here, and the gap stays recorded as missing real data.

| File | `verdict` | Why it is here |
| --- | --- | --- |
| `102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.findings-not-parsed-edited.md` | CONCERNS | **Edited.** A copy of the round 1, part 1 file (`102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md`) with one added line, the body heading `## Findings Not Parsed`. Nothing else differs. Replace it when a real file shows the combination. |

### Stdout captures

Captured **20260926**.

| File | Command | Why it is here |
| --- | --- | --- |
| `stdout-slice-927-clean-pass.json` | `sq review slice 927 --output json --no-save` in the Squadron repo (captured by the Squadron session, squadron c88e2587, minimax-m3) | A clean PASS: `verdictSource: stated`, zero findings, `fallback_used: false`. Must parse as findings parsed, not as a parse failure. |
| `stdout-slice-104-concerns-glmflash.json` | `sq review slice <104 design path> --against <100-arch path> --model glmflash --output json` against a throwaway copy of this repo (squadron 0.14.0, z-ai/glm-5.3-flash) | A CONCERNS with eleven findings, mixed PASS/CONCERN/NOTE severities, and 48 tool calls. The review was not saved (a path input carries no slice number), so stdout holds no trailing `Saved review to` line. |

### Edited stdout capture

| File | `verdict` | Why it is here |
| --- | --- | --- |
| `105-review.slice.squadron-review-parser-and-ingest.20261015T041112.stdout-unknown-with-score-edited.json` | UNKNOWN | **Edited.** A copy of the file-and-stdout pair's stdout capture (`105-review.slice.squadron-review-parser-and-ingest.20261015T041112.stdout.json`) with `verdict` set to `UNKNOWN` and `score` set to `7.5` (the real capture has a null score). Nothing else differs. It pins the 107 D4 refusal. Replace it when a real stdout capture shows the combination. |

### File and stdout pair

Captured **20261014** (the archive stamp is UTC 20261015T041112). One real review, saved by Squadron as a file and also printed as JSON on stdout, so the parser's file/stdout agreement is tested on real output.

Command, run in a throwaway git worktree of this repo registered with `cf worktree init` (never the real checkout): `sq review slice 105 --model sonnet --output json > <stdout file> 2> <stderr file>`. Squadron 0.21.9, sdk profile, `claude-sonnet-5-5`. The stdout file is a single JSON object; the `Saved review to` line went to stderr.

| File | `verdict` | Why it is here |
| --- | --- | --- |
| `105-review.slice.squadron-review-parser-and-ingest.20261015T041112.md` | CONCERNS | The saved file: `squadronVersion: 0.21.9`, `reviewedSha`, no `runId` (a CLI run carries none), six findings. |
| `105-review.slice.squadron-review-parser-and-ingest.20261015T041112.stdout.json` | CONCERNS | The same review's stdout: `template_name` equals the file's `reviewType` (`slice`), `run_id` null, and the same finding keys in the same order. |

The stdout carries keys the 105 design does not list (`cached_tokens`, `effort`, `failed_tool_calls`, `input_files`, `max_output_tokens`, `output_budget_exhausted`, `provenance`, `reasoning_chars`, `recovery_turn_used`, `setting_sources`, `structured_findings`, `system_prompt_mode`, `turns`, `timestamp`, `profile`). The parser ignores unknown keys.

### Judge-template review

Captured **20261015** (Squadron 0.22.0, sdk profile, `claude-sonnet-5-5`). One real judge review, saved by Squadron as a file, from the first step of the `judge-cycle` pipeline.

Command, run in a throwaway clone of this repo registered with `cf init --lite --no-ide` and `cf set arch 100-arch.substrate-run-state-store` (never the real checkout): `sq run judge-cycle 107 -p max-revisions=0,review-model=sonnet`. Only `review-0` ran; the pipeline then stopped on `loop.max must be a positive integer`, which does not affect the saved file. The file is unmodified.

| File | `verdict` | Why it is here |
| --- | --- | --- |
| `107-review.judge.slice-vs-arch.judge-samples-checks-and-calibration.20261015.md` | PASS | A `judge.slice-vs-arch` review: `score: 86.0`, seven `criteria` scores, a `runId` and `squadronVersion: 0.22.0` stamp, and no `verdictSource`, so its trust label is `unattested`. |
