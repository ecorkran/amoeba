---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The user config file Amoeba reads from its home, key by key, with one complete example.
dateCreated: 20261109
dateUpdated: 20261117
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

Later slices add keys; each is required too, so an old file fails naming the new key. `request_open_ttl_hours` and `max_chain_depth` (slice 240) are two such keys, and `notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds` (slice 241) three more, and `wake_timeout_seconds` and `max_wakes_per_day` (slice 244) two more: a config without one fails, naming it. The suggested values are in the example below and nowhere else.

## Keys

| Key | Type | Meaning |
|---|---|---|
| `answer_model` | string, no `,` | Squadron model alias for the answer step |
| `check_model` | string, no `,` | Squadron model alias for the check step |
| `max_cost_usd` | number > 0 | Cost cap of one answering run, in US dollars |
| `answer_limit` | integer >= 1 | Most automatic answers one run may take |
| `passages_max_chars` | integer >= 1 | Most characters of passages an answering run is sent. Rules and plan passages are never trimmed, so it must cover all of them: the rules (after duplicates are dropped), the slice's plan files, the program concept, and room for precedent. The example, 250000, suits a repo whose slice plan files run to about 150 KB; see `rules.md` |
| `answering_wait_seconds` | number > 0 | Longest one answering run may take before it is stopped; also the age at which an unfinished claim counts as dead, and the least time between two starts of `handle-pause` for one held question (slice 242) |
| `resume_wait_seconds` | number > 0 | Longest a resumed run may take to start running before the resume is judged refused |
| `prune_after_days` | integer >= 1 | Age in days after which settled answering scratch, logs and calls-log days are deleted; anything tied to an open question is kept |
| `request_open_ttl_hours` | integer, 1 to 87600 (ten years) | Hours an open request waits for an answer before it reads `expired`. Fixed into each request when it is sent, so changing the key never moves an existing request's expiry. An accepted request never expires |
| `max_chain_depth` | integer >= 1 | Deepest a chain of requests may go. A root request has depth 1; a `send` whose parent is already this deep is rejected `chain_too_deep` |
| `notify_poll_seconds` | number > 0 | How often a serving `amoeba-mcp` checks its member's deliveries and pushes a channel event when one is new (`mcp-server.md`) |
| `session_heartbeat_seconds` | number > 0, at least `notify_poll_seconds` | How often a serving `amoeba-mcp` writes its session row, and prunes stale rows of every member (`store-contract.md`) |
| `session_stale_seconds` | number > 0, at least twice `session_heartbeat_seconds` | Age of a session's last heartbeat past which `list` and waking treat it as gone, so one missed beat never reads as gone |
| `wake_timeout_seconds` | number > 0 | Longest a woken agent's command may run. The wake's wrapper stops the command and its process group at this deadline, fixed when the wake is claimed, and the wake is recorded `timed_out`. If the wrapper itself is killed, the command's own cap is the bound (`cli-contract.md`, "The wake command") |
| `max_wakes_per_day` | integer >= 1 | Most wakes started for one member in any rolling 24 hours, failed starts included. When it is hit no wake starts, the request stays `open` for the next agent until its TTL, and `list` says waking is stopped; the next `send` after the oldest counted wake is 24 hours old wakes again. Zero is not a way to turn waking off: clear the member's wake command (`amoeba add --no-wake-command`) |
| `default_rules_paths` | list of repo-relative paths, not empty | The rules files a member that names none reads. Each entry that matches no file at the pinned commit is skipped; when none is found the question waits (`rules.md`). A `*` is allowed in the last segment. Read when a question is answered, so an edit changes every default member |
| `default_consumed` | `from_source` or `from_release` | Which of a provider's reports a `--depends-on` without `:MODE` consumes |
| `authorize_items` | list, may be empty | Everything answers may be barred from authorizing |

Each `authorize_items` entry has all four fields, and no others:

| Field | Type | Meaning |
|---|---|---|
| `key` | string, unique in the list | What members refer to in `authorize_allow` and `authorize_deny` |
| `description` | string | What the answer and check steps are told. Never matched on |
| `screen_phrases` | list of strings, may be empty | Phrases the deterministic answer screen matches |
| `denied_by_default` | boolean | `true`: on every member's not-authorized list unless the member allows it. `false`: only on lists of members that deny it |

## Example

The five items are the default list. Four are denied by default: an answer may not
authorize a push, a release, a destructive database statement or a policy change. A
merge to the main branch is allowed by default, because merging a finished slice into
its target is the normal end of a run; a member that wants the extra protection denies
it with `amoeba add --deny merge_to_main`.
Replace the two model aliases with your own Squadron aliases.

`amoeba init` writes exactly this file on a machine that has none, and adds any of
these keys that an older file lacks (`docs/cli-contract.md`).

```yaml
answer_model: replace-with-answer-alias
check_model: replace-with-check-alias
max_cost_usd: 0.5
answer_limit: 3
passages_max_chars: 250000
answering_wait_seconds: 600
resume_wait_seconds: 60
prune_after_days: 30
request_open_ttl_hours: 72
max_chain_depth: 3
notify_poll_seconds: 5
session_heartbeat_seconds: 30
session_stale_seconds: 90
wake_timeout_seconds: 1800
max_wakes_per_day: 6
default_rules_paths: [CLAUDE.md, AGENTS.md]
default_consumed: from_source
authorize_items:
  - key: push
    description: Pushing commits to a remote.
    screen_phrases: ["git push", "push to origin"]
    denied_by_default: true
  - key: merge_to_main
    description: Merging a branch into the main branch.
    screen_phrases: ["merge to main", "merge into main"]
    denied_by_default: false
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
