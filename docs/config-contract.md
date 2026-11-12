---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The user config file Amoeba reads from its home, key by key, with one complete example.
dateCreated: 20261109
dateUpdated: 20261112
status: complete
---

# Config contract

Amoeba reads one user-level file, `config.yaml`, from its **config home**: `$AMOEBA_HOME`
when set, otherwise `~/.config/amoeba/`. It is the one file a person edits. Everything
Amoeba writes (the store, answering scratch, logs) lives in the **state home**:
`$AMOEBA_HOME` when set, otherwise `~/.local/state/amoeba/` (see `store-contract.md`).
`XDG_CONFIG_HOME` and `XDG_STATE_HOME` are not consulted. The code has no default for
any key. A missing
file, a missing key, an unknown key or a bad value fails the command with exit 3,
naming the file and the key, and every problem found is listed in one pass.

Later slices add keys; each is required too, so an old file fails naming the new key.

## Keys

| Key | Type | Meaning |
|---|---|---|
| `answer_model` | string, no `,` | Squadron model alias for the answer step |
| `check_model` | string, no `,` | Squadron model alias for the check step |
| `max_cost_usd` | number > 0 | Cost cap of one answering run, in US dollars |
| `answer_limit` | integer >= 1 | Most automatic answers one run may take |
| `passages_max_chars` | integer >= 1 | Most characters of passages an answering run is sent |
| `answering_wait_seconds` | number > 0 | Longest one answering run may take before it is stopped; also the age at which an unfinished claim counts as dead |
| `resume_wait_seconds` | number > 0 | Longest a resumed run may take to start running before the resume is judged refused |
| `prune_after_days` | integer >= 1 | Age in days after which settled answering scratch, logs and calls-log days are deleted; anything tied to an open question is kept |
| `authorize_items` | list, may be empty | Everything answers may be barred from authorizing |

Each `authorize_items` entry has all four fields, and no others:

| Field | Type | Meaning |
|---|---|---|
| `key` | string, unique in the list | What members refer to in `authorize_allow` and `authorize_deny` |
| `description` | string | What the answer and check steps are told. Never matched on |
| `screen_phrases` | list of strings, may be empty | Phrases the deterministic answer screen matches |
| `denied_by_default` | boolean | `true`: on every member's not-authorized list unless the member allows it. `false`: only on lists of members that deny it |

## Example

The five items are the default list: an answer may not authorize a push, a merge to
the main branch, a release, a destructive database statement or a policy change.
Replace the two model aliases with your own Squadron aliases.

```yaml
answer_model: replace-with-answer-alias
check_model: replace-with-check-alias
max_cost_usd: 0.5
answer_limit: 3
passages_max_chars: 60000
answering_wait_seconds: 600
resume_wait_seconds: 60
prune_after_days: 30
authorize_items:
  - key: push
    description: Pushing commits to a remote.
    screen_phrases: ["git push", "push to origin"]
    denied_by_default: true
  - key: merge_to_main
    description: Merging a branch into the main branch.
    screen_phrases: ["merge to main", "merge into main"]
    denied_by_default: true
  - key: release
    description: Cutting a release, tagging a version or publishing a package.
    screen_phrases: ["cut a release", "publish the package"]
    denied_by_default: true
  - key: destructive_database_statement
    description: Running a destructive database statement (DROP, TRUNCATE, DELETE, ALTER).
    screen_phrases: ["drop table", "truncate table"]
    denied_by_default: true
  - key: policy_change
    description: Changing project-wide policy or rules.
    screen_phrases: ["change the policy", "change the rules"]
    denied_by_default: true
```
