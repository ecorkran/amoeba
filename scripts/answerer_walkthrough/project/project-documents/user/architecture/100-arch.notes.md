---
docType: architecture
layer: project
project: notes
archIndex: 100
component: notes
initiative: notes
parent: ../project-guides/001-initiative-plan.notes.md
dependencies: []
relatedSlices: []
riskLevel: low
audience: [human, ai]
description: Architecture for the notes tool.
dateCreated: 20261103
dateUpdated: 20261103
status: in_progress
---

# Architecture: Notes

## Components

- **Store:** reads and writes the notes file.
- **Commands:** add, list, show, sort, export and import, each a thin layer over the store.
- **Command line:** parses arguments and calls a command.

## Delivery

Slice branches merge to `main` automatically once their review passes; agents do not need to ask.
