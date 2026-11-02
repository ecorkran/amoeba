---
docType: slice-design
slice: standing-fixes
project: amoeba
parent: null
dependencies: []
interfaces: []
review: none
dateCreated: 20261102
dateUpdated: 20261102
status: in_progress
---

# Slice Design: standing-fixes

The permanent container for fixes that need more than one step. It is never
complete. Unrelated fixes belong together here, and a closed item may be reopened.
Each fix is a `## #{issue} {title}` group in
`user/tasks/990-tasks.standing-fixes.md`, worked on the target branch and committed
at the group's `**Commit**:` markers.
