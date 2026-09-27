---
docType: reference
purpose: Provenance of the real upstream fixtures the observers are tested against
dateCreated: 20260921
dateUpdated: 20260927
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

### Stdout captures

Captured **20260926**.

| File | Command | Why it is here |
| --- | --- | --- |
| `stdout-slice-927-clean-pass.json` | `sq review slice 927 --output json --no-save` in the Squadron repo (captured by the Squadron session, squadron c88e2587, minimax-m3) | A clean PASS: `verdictSource: stated`, zero findings, `fallback_used: false`. Must parse as findings parsed, not as a parse failure. |
| `stdout-slice-104-concerns-glmflash.json` | `sq review slice <104 design path> --against <100-arch path> --model glmflash --output json` against a throwaway copy of this repo (squadron 0.14.0, z-ai/glm-5.3-flash) | A CONCERNS with ten findings, mixed PASS/CONCERN/NOTE severities, and 48 tool calls. The review was not saved (a path input carries no slice number), so stdout holds no trailing `Saved review to` line. |
