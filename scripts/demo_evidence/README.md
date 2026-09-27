---
docType: reference
purpose: What each verdict payload beside demo_evidence.py is for, and where its text came from
dateCreated: 20260927
dateUpdated: 20260927
---

# Demo review payloads

`findings` arrays for `amoeba submit verdict --findings "$(cat …)"` in the slice 104 verification walkthrough. Every summary is real Squadron text, copied from the captured 102 task-review rounds in `tests/fixtures/sq_reviews/`. Only the order and the line ranges are arranged.

| File | Findings | Source |
| --- | --- | --- |
| `round1.json` | ExitCode ordering (`:119-163`), no CI wiring | round 1 part 1 (`…part-1.20260921T112529.md`), F001 and F002 |
| `round2.json` | GRACE_EXPIRED (new), ExitCode ordering again at position 2 with the range moved to `:141-185` | GRACE_EXPIRED: round 2 part 1 (`…part-1.md`) F001; ExitCode: as above |
| `one_finding.json` | Task 2.1's wrong cross-reference | round 1 part 1, F004 |

Round 2 against round 1: one `recurring` (ExitCode), one `new` (GRACE_EXPIRED), one `gone` (CI wiring).
