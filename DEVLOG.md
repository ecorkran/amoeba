---
docType: devlog
project: amoeba
layer: project
dateCreated: 20261009
dateUpdated: 20261127
---

# Development Log

---

## 20261127

### Release 0.2.10
Slice 263 (sessions across machines, migration 014), separate homes for development builds, message-only errors at a terminal, slice 263 review fixes.

## 20261125

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261123

### Release 0.2.9

0.2.8 was tagged, but CI failed (tests needed `cf`), so nothing published. Slices 260 (hub and door) and 261 (members by name): store schema 12, and `update_live` installs the release from PyPI.

---

## 20261122


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: FAIL)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

### Release 0.2.7
- Replaces 0.2.6, tagged but never published (a test needed Context Forge on the CI machine).
- `amoeba init` sets up a new machine (starter config and store, safe to repeat), and a missing config is one line with no traceback (#47).

### Release 0.2.5
- The stand-in never starts work the PM did not ask for (#46), and `answer-first install` writes the bare command so hooks always run the tool install.

### Release 0.2.4
- Answer-first hooks (`amoeba answer-first install/uninstall`), stand-in settles asking another session, and slice 230 standing answers (store migration 010).

---

## 20261120

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261119

### Release 0.2.3
Collapsed unplaced runs in `list`; colored section headings in `list` and `status`.

## 20261118

### Release 0.2.2
Schema-too-new error says to restart the amoeba MCP server.

### Release 0.2.1
`amoeba --version`.

## 20261117

### Release 0.2.0
Agent messaging: push and presence, hold and release, notes and release notes, waking (slices 241–244; store schema 9).

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: FAIL)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: FAIL)
- revise-code:commit-5: PASS

## 20261116


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261115

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261114


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261112


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: PASS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS

## 20261111

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: FAIL)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261110

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261104

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261023


**p56: devlog-9**
- tasks-0:cf-op-0: PASS
- tasks-0:cf-op-1: PASS
- tasks-0:cf-op-2: PASS
- tasks-0:dispatch-3: PASS
- tasks-0:review-4: PASS (verdict: CONCERNS)
- tasks-0:checkpoint-5: PASS
- tasks-0:commit-6: PASS
- revise-tasks:dispatch-0: PASS
- revise-tasks:review-1: PASS (verdict: CONCERNS)
- revise-tasks:commit-2: PASS
- revise-tasks:dispatch-3: PASS
- revise-tasks:review-4: PASS (verdict: CONCERNS)
- revise-tasks:commit-5: PASS
- summary-2:summary-0: PASS
- compact-3:compact-0: PASS
- summary-4:summary-0: PASS
- branch-5:branch-0: PASS
- implement-6:cf-op-0: PASS
- implement-6:cf-op-1: PASS
- implement-6:cf-op-2: PASS
- implement-6:dispatch-3: PASS
- implement-6:review-4: PASS (verdict: CONCERNS)
- implement-6:checkpoint-5: PASS
- implement-6:commit-6: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: PASS)
- revise-code:commit-2: PASS


**p56: devlog-9**
- tasks-0:cf-op-0: PASS
- tasks-0:cf-op-1: PASS
- tasks-0:cf-op-2: PASS
- tasks-0:dispatch-3: PASS
- tasks-0:review-4: PASS (verdict: CONCERNS)
- tasks-0:checkpoint-5: PASS
- tasks-0:commit-6: PASS
- revise-tasks:dispatch-0: PASS
- revise-tasks:review-1: PASS (verdict: CONCERNS)
- revise-tasks:commit-2: PASS
- revise-tasks:dispatch-3: PASS
- revise-tasks:review-4: PASS (verdict: CONCERNS)
- revise-tasks:commit-5: PASS
- summary-2:summary-0: PASS
- compact-3:compact-0: PASS
- summary-4:summary-0: PASS
- branch-5:branch-0: PASS
- implement-6:cf-op-0: PASS
- implement-6:cf-op-1: PASS
- implement-6:cf-op-2: PASS
- implement-6:dispatch-3: PASS
- implement-6:review-4: PASS (verdict: CONCERNS)
- implement-6:checkpoint-5: PASS
- implement-6:commit-6: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

**p56: devlog-9**
- tasks-0:cf-op-0: PASS
- tasks-0:cf-op-1: PASS
- tasks-0:cf-op-2: PASS
- tasks-0:dispatch-3: PASS
- tasks-0:review-4: PASS (verdict: FAIL)
- tasks-0:checkpoint-5: PASS
- tasks-0:commit-6: PASS
- revise-tasks:dispatch-0: PASS
- revise-tasks:review-1: PASS (verdict: CONCERNS)
- revise-tasks:commit-2: PASS
- revise-tasks:dispatch-3: PASS
- revise-tasks:review-4: PASS (verdict: CONCERNS)
- revise-tasks:commit-5: PASS
- summary-2:summary-0: PASS
- compact-3:compact-0: PASS
- summary-4:summary-0: PASS
- branch-5:branch-0: PASS
- implement-6:cf-op-0: PASS
- implement-6:cf-op-1: PASS
- implement-6:cf-op-2: PASS
- implement-6:dispatch-3: PASS
- implement-6:review-4: PASS (verdict: CONCERNS)
- implement-6:checkpoint-5: PASS
- implement-6:commit-6: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261022

**p56: devlog-9**
- tasks-0:cf-op-0: PASS
- tasks-0:cf-op-1: PASS
- tasks-0:cf-op-2: PASS
- tasks-0:dispatch-3: PASS
- tasks-0:review-4: PASS (verdict: CONCERNS)
- tasks-0:checkpoint-5: PASS
- tasks-0:commit-6: PASS
- revise-tasks:dispatch-0: PASS
- revise-tasks:review-1: PASS (verdict: CONCERNS)
- revise-tasks:commit-2: PASS
- revise-tasks:dispatch-3: PASS
- revise-tasks:review-4: PASS (verdict: CONCERNS)
- revise-tasks:commit-5: PASS
- summary-2:summary-0: PASS
- compact-3:compact-0: PASS
- summary-4:summary-0: PASS
- branch-5:branch-0: PASS
- implement-6:cf-op-0: PASS
- implement-6:cf-op-1: PASS
- implement-6:cf-op-2: PASS
- implement-6:dispatch-3: PASS
- implement-6:review-4: PASS (verdict: CONCERNS)
- implement-6:checkpoint-5: PASS
- implement-6:commit-6: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: PASS)
- revise-code:commit-5: PASS

## 20261015

**p56: devlog-9**
- tasks-0:cf-op-0: PASS
- tasks-0:cf-op-1: PASS
- tasks-0:cf-op-2: PASS
- tasks-0:dispatch-3: PASS
- tasks-0:review-4: PASS (verdict: CONCERNS)
- tasks-0:checkpoint-5: PASS
- tasks-0:commit-6: PASS
- revise-tasks:dispatch-0: PASS
- revise-tasks:review-1: PASS (verdict: CONCERNS)
- revise-tasks:commit-2: PASS
- revise-tasks:dispatch-3: PASS
- revise-tasks:review-4: PASS (verdict: CONCERNS)
- revise-tasks:commit-5: PASS
- summary-2:summary-0: PASS
- compact-3:compact-0: PASS
- summary-4:summary-0: PASS
- branch-5:branch-0: PASS
- implement-6:cf-op-0: PASS
- implement-6:cf-op-1: PASS
- implement-6:cf-op-2: PASS
- implement-6:dispatch-3: PASS
- implement-6:review-4: PASS (verdict: PASS)
- implement-6:checkpoint-5: PASS
- implement-6:commit-6: PASS
- close-out:dispatch-0: PASS

## 20261014

**Slice 105 closed.** Task 1.2 unblocked: the throwaway copy is now a git worktree registered with `cf worktree init` (the earlier PROJECT_NOT_FOUND), with the repo's `.env` linked in for the provider key. Captured the file/stdout pair with `sq review slice 105 --model sonnet` (Squadron 0.21.9; the `glmflash` alias is gone and `glm-flash` stalled). Added the four pair tests; walkthrough run by hand and recorded. Two walkthrough claims don't hold: `inspect verdicts --json` has no `sq_run_id` or `reviewed_sha` key (the data is stored; only the listing omits it).

---

## 20261009

**p6: devlog-3**
- branch-0: PASS
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: CONCERNS)
- checkpoint-5: PASS
- commit-6: PASS
- dispatch-0: PASS
- review-1: PASS (verdict: CONCERNS)
- commit-2: PASS