---
docType: review
layer: project
reviewType: tasks
slice: store-config-and-set-up
project: amoeba
verdict: FAIL
verdictSource: imposed
sourceDocument: project-documents/user/tasks/222-tasks.store-config-and-set-up.md
aiModel: squadron-task-gate
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 2893f0b01876008e9148c81b780d53906124ea29
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: fail
    category: merge-step
    summary: "Merge step at line 140: - [ ] Write `docs/config-contract.md` (with YAML frontmatter per `file-naming-conventions.md`): each key, its type and meaning, and one complete example whose `authorize_items` are push, merge to the main branch, release, destructive database statement and policy change, all `denied_by_default: true`"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:140"
---

# Review: tasks — slice 222

**Verdict:** FAIL
**Model:** squadron-task-gate

## Findings

### [FAIL] Merge step at line 140: - [ ] Write `docs/config-contract.md` (with YAML frontmatter per `file-naming-conventions.md`): each key, its type and meaning, and one complete example whose `authorize_items` are push, merge to the main branch, release, destructive database statement and policy change, all `denied_by_default: true`

Line 140 schedules a merge: `- [ ] Write `docs/config-contract.md` (with YAML frontmatter per `file-naming-conventions.md`): each key, its type and meaning, and one complete example whose `authorize_items` are push, merge to the main branch, release, destructive database statement and policy change, all `denied_by_default: true``. Merging happens in Phase 7 after code review passes; a task file must not contain it. Matched rule: git_object_window.

-> project-documents/user/tasks/222-tasks.store-config-and-set-up.md

### Run Digest

- Response length: 132 chars
- Response is newline-free: yes
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: not computed
- Settings sources: not computed
- Reasoning characters: not computed
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / cache write / completion / reasoning: not computed / not computed / not computed / not computed / not computed
- Duration: not computed
- Cost: not reported
- `## Summary` located: not computed
- `## Findings` located: not computed
- Finding-shaped matches — whole response: not computed
- Finding-shaped matches — inside fences: not computed
- Finding-shaped matches — in findings section: not computed
- Finding-shaped matches — surviving validation: not computed
