---
docType: slice-design
slice: the-cut
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 220-slice.code-audit
interfaces:
- 222-slice.store-config-and-set-up
- 223-slice.pause-handling
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
turns: 17
promptTokens: 900289
cachedTokens: 819839
cacheWriteTokens: 80422
completionTokens: 19351
durationSeconds: 201.6
costUsd: 1.194807
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.1948069000000001
    completionTokens: 19351
---

# Slice Design: The Cut

## Overview

The program-tool architecture (`220-arch.program-tool.md`) replaces the resident supervisor with a tool that agents and pipelines call. Slice 220 produces `user/analysis/220-analysis.code-audit.md`, which gives every unit of `src/amoeba`, `tests`, `scripts` and `docs` a verdict. This slice carries out those verdicts. It deletes every `delete` row. It moves the kept answering pieces and the upstream readers into a small library that does not depend on anything deleted. It rewrites the README to say what Amoeba is now.

After this slice Amoeba is a library with no store, no tick, no resident process and no command. Slices 222 to 224 build the new store, config and operations on top of it.

## Value

Architectural value. About 34k lines of source and 69k of tests come down to the answering pieces and the readers the scenarios use. Slices 222 to 224 are written against a base that holds nothing they have to work around. Every reader of the repo, human or agent, sees only code that has a scenario behind it.

## Technical Scope

**Included:**

- Deleting every unit the audit marks `delete`, with its tests, harnesses, scripts, docs and packaged resources.
- Removing every unit the audit marks `squadron` from Amoeba in the same way. The audit has already filed its Squadron issue, so nothing is ported here.
- Moving the kept units into the layout in D3. This includes the value types the kept code takes from the old store (D4).
- Reworking kept units only as far as needed to cut them off from deleted code: a value passed in by the caller in place of a read from deleted state, or a small helper moved next to its user (D2).
- Reworking or deleting the tests of kept units, as the audit says.
- Rewriting `tests/test_import_boundaries.py` for the new layout (D6).
- Updating `pyproject.toml` and `uv.lock`: dependencies, the console entry point, wheel artifacts and pytest options (D7).
- Rewriting the README and updating the package description (D9).

**Excluded:**

- Deciding verdicts. The audit decides them. A verdict that turns out to be wrong during the cut is corrected in the audit, never only in the code (D1).
- The new store, the user config file, the `AMOEBA_*` store-location variable and `set_up`. All of these are 222.
- Launching and waiting on an answering run, the resume, and the new question record. All of these are 223.
- `status`, `decisions` and their read views. These are 224.
- Editing old slice designs, task files, architecture documents or slice plans. Their files stay as they are.
- Deleting branches, including the slice 182 branch.
- Merging anything from the slice 182 branch. The audit's take and rewrite groups stay on the branch for 223, whose context step uses them.

## Dependencies

### Prerequisites

- **Slice 220 complete.** The audit document exists with its verdict tables (sections 2 to 4), the import-coupling list and the non-import coupling list (5a, 5b), the live-test verdicts (section 8) and the scan command (section 11). This slice cannot start without it.
- No external services. The live tier (`tests/live/answering`) needs `sq` and model credentials, as it does today.

### Interfaces Required

From the audit (`220-analysis.code-audit.md`):

- **The delete list**: every row in sections 2 to 4 with the verdict `delete` or `squadron`. By the audit's longest-prefix rule, a file's verdict is the verdict of the longest row path that starts its path.
- **The kept list**: every `keep` and `rework` row. For a `rework` row, the reason says what changes.
- **Replacements**: each row in 5a and 5b names a replacement. 221 carries out the ones marked **Parameter** or **Dropped**. Rows whose replacement is **New store (222)** or **Operation (223 or 224)** mean that the kept code's use goes away in 221, and the later slice builds the replacement (D2).
- **The scan command** (section 11). After the cut it must print nothing.
- **Live-test verdicts** (section 8): `stays`, `waits on 223` or `delete`. For each `waits on 223` file, the entry names the scenario A claim it covers (D8).

## Architecture

### Component Structure

After the cut `src/amoeba` holds two packages: `answering/`, the answering library, and `upstream/`, the readers of other tools' state. The audit's `keep` and `rework` rows say which units are in them. D3 says where each unit goes.

Dependency direction after the cut:

```
amoeba.answering  ──►  amoeba.upstream  ──►  stdlib, pydantic, pyyaml
```

`amoeba.upstream` imports nothing from `amoeba.answering`.

### Data Flow

There is no runtime flow to add. The library's flow is the one slices 143 and 144 built, with the store reads removed:

1. The caller passes the question, the slice reference, the PM's earlier answers and `AnswererSettings`.
2. `sources` reads the rules and plan files at the target commit through `source_reads` and `upstream`, and assembles the passage set with `passages`.
3. `inputs` writes `question.md` and `passages.md` into a scratch directory. The pipeline is `answering.yaml`.
4. *(223: launch the run and wait.)*
5. `artifacts` reads the replies. `decide` turns the run result and replies into a confirmed answer or a decline with a `DeclineReason`. `gate` screens the answer and composes the resume instructions.

Steps 1 to 3 and 5 are what 221 keeps and tests. Step 4 and the persisting of the result are 223.

### State Management

The slice adds no state and leaves none behind. The old store, its schema, its migrations and the per-project store files go. Nobody has run Amoeba, so no data is migrated. The slice's document state moves from `not_started` to `complete`.

## Technical Decisions

### D1 — The audit is the delete list
Status: decided

221 deletes from the audit's tables and decides nothing new. During the cut a verdict can prove wrong. The likely case is a kept module that needs something marked `delete`, with no Parameter or Dropped replacement possible. When that happens, the implementer changes the audit row and its 5a or 5b entry in the same commit as the code, with a one-line reason, and records it in the slice's task notes. The audit stays the record of what was kept and why. 222 to 224 read it after the cut.

Rejected: treating the audit as advisory and deciding during the cut. That loses the record, and the later slices would read a list that no longer matches the code.

### D2 — Sever, don't rebuild
Status: decided

This is how 221 carries out the audit's `rework` rows. A `rework` unit is changed only as far as needed to cut it off from deleted code. Three moves are allowed:

- **Parameter**: a value the code read from deleted state is passed in by the caller. For example, `assemble_sources` would take a slice reference and a tuple of `PmAnswer` in place of a `Store` and a `Node`.
- **Move**: a small helper a kept module takes from a deleted module moves next to its only kept user. If two kept modules use it, it moves to the lower layer (`upstream` before `answering`).
- **Drop**: a use with no scenario behind it goes, along with any field that only that use read.

A `rework` unit that can only work with a replacement built later (the new question record, launching through `sq`, the store's submit) is deleted, not stubbed. Under D1, its audit row is changed to `delete` in the same commit, with the reason and the slice that rebuilds it. The audit's section 10 records why each one differs from the architecture's "kept and reworked". The audit should mark these `delete` to begin with. The predicted cases are `answering/launch.py`, `stage.py` and `settle.py`, the store-writing half of `finish.py`, and `program/members.py`. A stub, or an interface kept open for a later slice, would be dead code that 222 or 223 would have to fit around.

Rejected: building the new store or launcher here so that more of the old code could stay. That is 222 and 223's design work, done without their designs.

### D3 — Layout
Status: decided

- The answering library moves from `amoeba/runner/answering/` to `amoeba/answering/`. `runner/` holds nothing else that is kept, and a package named for the tick-driven runner would mislabel what is left.
- Readers of other tools' state live under `amoeba/upstream/`. This covers Context Forge (existing, plus `cf_call.py` as `context_forge/cli_call.py`), Squadron's run output (`process/sq_outcome.py` as `squadron/run_outcome.py`, with the `RunEnded`, `RunVanished` and `LaunchFailed` types from `runner/observed.py` that `decide` uses), and git (`git_read.py`).
- Files move with `git mv`, so history follows them.
- Imports name the defining module. Package `__init__` files re-export nothing, apart from `upstream/context_forge/__init__.py`, which keeps its existing exports. That keeps the audit's re-export-resolving scan simple.

### D4 — Value types leave the old store
Status: decided

The kept code imports value types from `amoeba.store`: `DeclineReason`, `GateRefusal`, `AnsweringEvidence`, `PassageRef`, `AnsweredBy`, `GLOB_WILDCARD`, and the parameter-name constants it uses. Each type the kept code still uses after D2 moves to `amoeba/answering/values.py`, unchanged in name and members. `CFSnapshot`, used by `upstream/context_forge/checkout.py`, moves into `upstream/context_forge/`. Types that only deleted code used, such as `QuestionRecord`, `QuestionState`, `BlockedState` and `JournalEntry`, go with the store.

The library owns these types. 222's store persists them and imports them from `amoeba.answering.values`. The vocabulary of answers and declines belongs to answering. The store is the place they are kept. Types that only a record uses, such as question states, belong to 222's store and never move into `answering`.

Rejected: a shared `amoeba/types` package. It would be one more package with no owner, holding one module's worth of types.

### D5 — Answerer settings
Status: decided

`AnswererSettings` moves from `runner/project_config.py` to `answering/settings.py` as the library's input type. It keeps its rule of no defaults. `max_concurrent_runs` is dropped, because the architecture removes the concurrent-run limit and its only reader, the answering stage, is deleted. The rest of `project_config.py` (the per-project YAML file naming pipelines) goes. 222 adds the loader that builds `AnswererSettings` from the user config file and member settings, and decides where `rules_paths` and the authorize list come from.

### D6 — Import boundaries
Status: decided

`tests/test_import_boundaries.py` is rewritten. Its rules about deleted packages go. It enforces the D3 direction: `amoeba.upstream` imports nothing from `amoeba.answering`.

Imports of deleted code are checked by the audit's section 11 scan, which is run once at the end and must print nothing. It is not committed, as the audit specifies.

### D7 — Packaging
Status: decided

- Remove the `[project.scripts] amoeba` entry. The old CLI is deleted, and the first new command comes in 222. A placeholder command would be a silent fallback.
- Remove `starlette` and `uvicorn` from `dependencies`, and `httpx2` from the dev group, if no kept code or test uses them. Regenerate `uv.lock` with `uv lock`.
- Wheel `artifacts`: remove the two schema globs and `slice_writing.yaml`, and point the answering pipeline at `src/amoeba/answering/answering.yaml`. `tests/runner/answering/test_wheel_contents.py` moves with the library and checks the new path.
- pytest `addopts`: remove `--ignore=tests/load` once `tests/load` is gone. Keep `--ignore=tests/live`.
- Ruff and pyright settings are unchanged.

### D8 — Tests
Status: decided

- A test of deleted code goes with the code. A shared harness or fixture goes when all of its users are gone. `conftest.py` files lose the fixtures for deleted things.
- A kept test is `rework` only if its claim still holds without nodes, journal entries, blocked states or a tick. It then builds its inputs directly. Otherwise it is deleted (the audit's rule), and 223 or 224 writes the replacement.
- Kept tests move with their code: `tests/runner/answering/` to `tests/answering/`, and the tests of moved upstream modules into `tests/upstream/`.
- Live answering tests follow the audit's section 8. A `stays` file has its imports updated and must pass. A `waits on 223` file imports the answering stage or the store (expected: `test_answering_run.py` and `stage_harness.py`). It is deleted now, because it cannot import deleted code. Before the deletion, the file's audit section 8 entry must name the scenario A claim the file covers and the commit to restore it from (the `main` commit the slice branch forks from). If the entry lacks either, it is completed in the same commit as the deletion. 223 restores each of these claims as part of the scenario A check. Fixtures and `question_tails.py` stay if a `stays` file uses them.
- `tests/load/` goes with the inbox. This removes the failing test in `amoeba#32`.

### D9 — README and docs
Status: decided

The README drops the hero image and the old pitch and says, briefly:

- What Amoeba is: a tool that agents and pipelines call to answer a paused run's first-level questions and keep the record, across a program of repos. It runs no process of its own and is optional for Squadron.
- What exists now: the answering library and the upstream readers, with no command yet.
- Where the design lives: the concept, `220-arch.program-tool.md` and the slice plan.
- How to run the checks: format, lint, typecheck, tests, and the live tier with its `AMOEBA_LIVE_*` variables.

It makes no claim the code does not back. The image file under `assets/` is deleted if nothing else uses it.

`pyproject.toml`'s `description` changes to match the README's first line. Files under `docs/` follow the audit. The contracts for deleted subsystems are expected to go. `answerer-walkthrough.md` and `scripts/answerer_walkthrough*` go if the audit marks them `delete`, which is expected because they drive the stage through the store.

### Patterns and Conventions

- One commit per task-file `**Commit**:` marker, typed `refactor:` for moves and severs and `chore:` for deletions and packaging. The README is `docs:`.
- Every commit leaves format, lint, typecheck and the default test suite passing (Migration Plan).
- No new behavior. Where a sever changes a signature (D2), the existing tests of that function are updated to the new signature and keep their assertions.

## Implementation Details

### Migration Plan

**What moves** (expected, subject to the audit):

| Source | Destination |
|---|---|
| `src/amoeba/runner/answering/{answering.yaml, pipeline_file, inputs, passages, source_reads, sources, artifacts, decide, gate}` | `src/amoeba/answering/` |
| `src/amoeba/runner/pipeline_resource.py` | `src/amoeba/answering/pipeline_resource.py` |
| `AnswererSettings` from `src/amoeba/runner/project_config.py` | `src/amoeba/answering/settings.py` |
| Value types from `src/amoeba/store/` | `src/amoeba/answering/values.py`; `CFSnapshot` to `src/amoeba/upstream/context_forge/` |
| `src/amoeba/process/sq_outcome.py`, ended-run types from `src/amoeba/runner/observed.py` | `src/amoeba/upstream/squadron/run_outcome.py` |
| `src/amoeba/runner/{budget, git_read}.py` | `src/amoeba/upstream/{budget, git_read}.py` |
| `src/amoeba/runner/cf_call.py` | `src/amoeba/upstream/context_forge/cli_call.py` |
| `tests/runner/answering/` and tests of the moved modules | `tests/answering/`, `tests/upstream/` |

**Consumers.** Only kept code consumes moved code, because everything else is deleted. Consumers change their imports to the new module. No compatibility re-exports are left at the old paths (D3), because the old packages are deleted.

**Keeping the system working throughout.** The cut runs in steps, and each ends with format, lint, typecheck and the default suite passing:

1. **Leaf deletions.** Delete the units that no kept unit depends on, either by import or by 5b coupling: `serve/`, `inbox/`, `feed/`, `cli/`, `inspection/`, `runner/request_run/`, `tests/load/`, the demo scripts, their tests and their docs. Old code that imports one of these is cut off from it by removing those imports and uses, nothing more, because that code goes in step 2.
2. **Move, sever and delete.** Create the D3 layout and move the kept modules and the D4 value types. Apply the D2 severs. Delete the remaining `delete` and `squadron` rows (predicted: the rest of `runner/`, `process/`, `store/` and `program/`, and the upstream review parsers), with their tests. Rework or delete the remaining tests (D8). The checks run once, at the end of the step, so old code is never re-pointed to keep it compiling.
3. **Boundaries and docs.** Rewrite the import-boundaries test (D6), rewrite the README (D9), and run the audit scan.

Each D7 packaging edit lands in the step that deletes or moves what it names. Removing the console entry point and `slice_writing.yaml` goes in step 1, with `cli/` and `runner/request_run/`, and so does the `--ignore=tests/load` option. The new `answering.yaml` path, the schema globs and the unused dependencies go in step 2.

**Data.** None to migrate (State Management).

**Behavior preserved.** The kept functions keep their tests. A test changes only where a D2 sever changes a signature. The live answering tests marked `stays` pass on the moved code.

## Integration Points

### Provides to Other Slices

- **222**: `amoeba.answering.values` (the vocabulary its new store persists) and `amoeba.answering.settings.AnswererSettings` (what its config loader builds). No kept module resolves a directory to its Context Forge project (`resolve_checkout` maps a slice to a checkout, the other way), so 222 builds that for `set_up`. Also: no console entry point and no old migrations.
- **223**: the answering library. It takes the question, the slice reference, the precedent and the settings, and gives a scratch directory, the passage set and, once the run is done, a confirmed answer or a decline. It also gets `upstream/squadron/run_outcome.py` (`poll_run`, checkpoint kinds) for reading the paused run, the `waits on 223` live tests, each with its claim and restore commit in audit section 8, and the deleted launch and stage code, which it can read in git history through the audit's reuse list.
- **224**: nothing new beyond the base.

### Consumes from Other Slices

- **220**: the audit document, which is required (Prerequisites). If it is missing or incomplete, 221 does not start.
- **Slices 140 to 144** (complete): the answering code being kept.

## Success Criteria

### Functional Requirements

- Every path the audit marks `delete` or `squadron` is gone: no file in the repo maps to such a row by the longest-prefix rule.
- Every `keep` and `rework` unit exists at the location D3 gives it, or at the location the audit row records.
- The answering library assembles passages, prepares a scratch directory, reads replies, decides and screens, in its tests. It does this with no store, no tick and no resident process, because none of those packages exists.
- The README describes Amoeba as the program tool, names what exists now, and has none of the old pitch.

### Technical Requirements

- `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` pass.
- `uv run pytest tests/live/answering` passes with the `AMOEBA_LIVE_*` variables set. Any file not present is one the audit's section 8 marks `waits on 223` or `delete`.
- The audit's section 11 scan prints nothing.
- `tests/test_import_boundaries.py` enforces the D6 rule and passes.
- The built wheel contains `amoeba/answering/answering.yaml` and no `.sql` files.
- Any audit row changed during the cut (D1, D2) has a reason and is in the same commit as the code change.
- Every live answering file deleted as `waits on 223` has an audit section 8 entry naming its claim and restore commit (D8).

### Integration Requirements

- 222's design can add `amoeba.store` and a console entry point without removing anything left over from the old code.
- 223's design can call the library's entry points without touching a store type.
- `amoeba#32` is closed at merge with a pointer to this slice, since its test is deleted.

### Verification Walkthrough

Run from the repo root on the slice branch after the cut. `AUDIT=project-documents/user/analysis/220-analysis.code-audit.md`.

1. **Checks pass.**
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   ```
   Expected: all four succeed.

2. **The delete list is gone.** List every file and pick out those that map to a `delete` or `squadron` row by the longest-prefix rule. The command should print nothing. It finds each row's verdict by the cell whose whole text is one of the four verdict words, so it does not depend on the column order.
   ```bash
   grep -E '^\| *`(src|tests|scripts|docs)/' "$AUDIT" |
     awk -F'|' '{ p = $2; gsub(/[` ]/, "", p); v = ""
          for (i = 3; i <= NF; i++) { c = $i; gsub(/[` ]/, "", c)
            if (c ~ /^(keep|rework|squadron|delete)$/) { v = c; break } }
          print p "\t" v }' > /tmp/verdicts
   cut -f2 /tmp/verdicts | grep -qx keep && cut -f2 /tmp/verdicts | grep -qx delete ||
     echo "AUDIT TABLES NOT PARSED: no keep or no delete row; the check below proves nothing"
   git ls-files src tests scripts docs |
   awk -F'\t' 'NR == FNR { v[$1] = $2; next }
        { best = ""; for (p in v) if (index($0, p) == 1 && length(p) > length(best)) best = p
          if (v[best] == "delete" || v[best] == "squadron") print "still here: " $0 }' /tmp/verdicts -
   ```

3. **No kept module reaches deleted code.** Run the audit's section 11 scan as written. Expected: no output.

4. **The library stands alone.**
   ```bash
   uv run pytest tests/answering tests/upstream -q
   ls src/amoeba
   ```
   Expected: tests pass. `src/amoeba` lists only `__init__.py`, `answering` and `upstream`, plus anything the audit kept under another name.

5. **The live answering tests.** With `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL`, `AMOEBA_LIVE_SDK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD` set:
   ```bash
   uv run pytest tests/live/answering
   ```
   Expected: passes. Compare `ls tests/live/answering` with the audit's section 8. Every file it lists as `stays` is present.

6. **Packaging.**
   ```bash
   uv build && unzip -l dist/amoeba-*.whl | grep -E 'answering\.yaml|\.sql$'
   ```
   Expected: one line for `amoeba/answering/answering.yaml` and no `.sql` lines. `grep -n 'scripts\|starlette\|uvicorn' pyproject.toml` shows no console entry point and no server dependencies.

7. **Size.** `find src tests -name '*.py' | xargs wc -l | tail -1`, compared with the same command on `main`. Record both in the task notes. There is no target figure. This is a record of the cut.

8. **README.** Read it. It says what Amoeba is now and what exists, and it has nothing from the old pitch.

## Risk Assessment

### Technical Risks

- **Hidden coupling.** Kept code can depend on deleted code without importing it, for example through SQL columns or YAML references (the audit's 5b). An import scan won't show it, and a test can still pass on fixtures that encode the old shape.

### Mitigation Strategies

- Work through 5b row by row during step 2 of the Migration Plan, not only 5a. Where a kept test's fixture carries old-shape fields (`node_id`, journal ids), the test is rework or delete under D8, never left passing on an old-shape fixture. If an audit row turns out to be wrong, D1 applies.

## Implementation Notes

### Development Approach

1. Confirm the audit is `complete` and create branch `221-slice.the-cut` from `main`. Check D3, D4 and the D2 predictions against the audit's verdicts and section 10. Where they differ, the audit wins (D1).
2. Follow the three steps in the Migration Plan, with a commit marker at the end of each.
3. Run the full checks after each step, and the live tier after step 2 and step 3.
4. Run the Verification Walkthrough, and record the step 7 sizes and any D1 audit changes in the task notes.

The slice follows the normal route: tasks, implementation on the branch, code review, then merge in Phase 7.

### Special Considerations

- **Smaller wins.** When a kept test or helper is in doubt, and it has no scenario behind it, it goes. The later slices can recover it from git history.
- **Don't fix while cutting.** A bug found in kept code is filed as an issue under the project's Fixes rule, not fixed in this slice. That way the cut's diff is only moves, severs and deletes.
