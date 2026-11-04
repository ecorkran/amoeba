---
docType: review
layer: project
reviewType: tasks
slice: program-concept-as-a-source
project: amoeba
verdict: FAIL
verdictSource: imposed
sourceDocument: project-documents/user/tasks/182-tasks.program-concept-as-a-source.md
aiModel: squadron-task-gate
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 8c5bfa67dbdd1421d9406cec9ef976667e3e9265
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: fail
    category: merge-step
    summary: "Merge step at line 62: - [ ] Create the branch (see Branch above). Then check that 181 is merged on the target: `ProgramStore` with `members(program_id)` and `program_of`; `Program` (with `concept_member`, `concept_path`, `updated_at`) and `Member` (with `project_id`, `updated_at`); `read_member`, `Readable`, `Unreadable`, `MemberUnreadableReason`; `RunnerHost.program_store`; `ProgramStage.run(project_id) -> Program | None` called in `ProjectTick.run`; `resolve_checkout` exported from `amoeba.upstream.context_forge`."
    location: "project-documents/user/tasks/182-tasks.program-concept-as-a-source.md:62"
---

# Review: tasks — slice 182

**Verdict:** FAIL
**Model:** squadron-task-gate

## Findings

### [FAIL] Merge step at line 62: - [ ] Create the branch (see Branch above). Then check that 181 is merged on the target: `ProgramStore` with `members(program_id)` and `program_of`; `Program` (with `concept_member`, `concept_path`, `updated_at`) and `Member` (with `project_id`, `updated_at`); `read_member`, `Readable`, `Unreadable`, `MemberUnreadableReason`; `RunnerHost.program_store`; `ProgramStage.run(project_id) -> Program | None` called in `ProjectTick.run`; `resolve_checkout` exported from `amoeba.upstream.context_forge`.

Line 62 schedules a merge: `- [ ] Create the branch (see Branch above). Then check that 181 is merged on the target: `ProgramStore` with `members(program_id)` and `program_of`; `Program` (with `concept_member`, `concept_path`, `updated_at`) and `Member` (with `project_id`, `updated_at`); `read_member`, `Readable`, `Unreadable`, `MemberUnreadableReason`; `RunnerHost.program_store`; `ProgramStage.run(project_id) -> Program | None` called in `ProjectTick.run`; `resolve_checkout` exported from `amoeba.upstream.context_forge`.`. Merging happens in Phase 7 after code review passes; a task file must not contain it. Matched rule: git_object_window.

-> project-documents/user/tasks/182-tasks.program-concept-as-a-source.md

### Run Digest

- Response length: 135 chars
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
