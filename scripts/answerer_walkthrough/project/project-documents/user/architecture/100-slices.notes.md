---
docType: slice-plan
layer: project
project: notes
parent: user/architecture/100-arch.notes.md
archIndex: 100
component: notes
audience: [human, ai]
description: Slice plan for the notes tool.
dateCreated: 20261103
dateUpdated: 20261103
status: in_progress
---

# Slice Plan: Notes

## Parent Document

`100-arch.notes.md`

## Foundation Work

1. [ ] **(100) Add a Note** — The `add` command appends one note, with its text, to the notes file. If your instructions do not already say which storage format notes are kept in, write no design and end your reply with one question asking which storage format notes are kept in.
   **Success Criteria:**
   - `notes add "text"` writes one note and prints nothing else.
   **Dependencies:** None
   **Relative Effort:** 1

## Feature Slices

2. [ ] **(101) List Notes** — The `list` command prints every note, one per line, oldest first. If your instructions do not already say whether this slice's branch should merge to `main` once its review passes, write no design and end your reply with one question asking whether this slice's branch should merge to `main` once its review passes.
   **Success Criteria:**
   - `notes list` prints each note on its own line.
   **Dependencies:** 100
   **Relative Effort:** 1

3. [ ] **(102) Show Note Dates** — The `list` command can show when each note was written. If your instructions do not already say which date format user-facing timestamps use, write no design and end your reply with one question asking which date format user-facing timestamps use.
   **Success Criteria:**
   - `notes list --dates` prints each note with its timestamp.
   **Dependencies:** 101
   **Relative Effort:** 1

4. [ ] **(103) Sort by Date** — The `list` command can sort notes by the time they were written. If your instructions do not already say how times shown to the user should be written, write no design and end your reply with one question asking how times shown to the user should be written.
   **Success Criteria:**
   - `notes list --sort date` prints notes in order of writing, newest first.
   **Dependencies:** 102
   **Relative Effort:** 1

5. [ ] **(104) Export Notes** — The `export` command writes all notes to a file. If your instructions do not already say which storage format notes are kept in, write no design and end your reply with one question asking which storage format notes are kept in; once that is answered, if your instructions do not already say whether new source files carry a license header, write no design and end your reply with one question asking whether new source files carry a license header.
   **Success Criteria:**
   - `notes export path` writes every note to `path`.
   **Dependencies:** 103
   **Relative Effort:** 1

6. [ ] **(105) Import Notes** — The `import` command reads notes from a file and adds them. If your instructions do not already say what copyright notice each new file should open with, write no design and end your reply with one question asking what copyright notice each new file should open with.
   **Success Criteria:**
   - `notes import path` adds every note found in `path`.
   **Dependencies:** 104
   **Relative Effort:** 1
