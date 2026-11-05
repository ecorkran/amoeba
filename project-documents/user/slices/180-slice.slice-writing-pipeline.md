---
docType: slice-design
slice: slice-writing-pipeline
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies: [100, 120, 140]
interfaces:
- 183
- 184
dateCreated: 20261103
dateUpdated: 20261104
status: complete
turns: 44
promptTokens: 4403551
cachedTokens: 4256057
cacheWriteTokens: 147412
completionTokens: 38028
durationSeconds: 447.5
costUsd: 2.791729
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.7917289000000007
    completionTokens: 38028
---

# Slice Design: slice-writing-pipeline

## Overview

This is the Squadron pipeline a request run (slice 184) launches. It ships inside Amoeba beside `answering.yaml` and is proven against the installed `sq` and `cf`. It runs in a provider project's checkout, on the target. It takes the index of the provider's requests initiative and a self-contained need, and it does one of two things:

- **New slice.** It writes one new slice entry into the requests initiative's slice plan and commits it to the target. If the initiative does not exist yet, it first adds the initiative to the project's initiative plan and creates the slice plan file. The reply names the new slice's index.
- **Already met.** The provider already meets the need. Nothing is written, and the reply names the commit that meets it.

The pipeline has two steps. A **write step** is a dispatch to an agent with the provider's tools. It reads the provider, decides, edits at most two plan files and replies with one JSON object. A **commit step** then commits exactly those plan files and refuses anything else. A pure reader parses the reply into one of the two shapes, so 184 never parses plan files or agent prose.

Squadron 0.24.17 (checked 20261103 against its source) cannot run this pipeline from a checkout without dirtying it, cannot commit named paths from a dispatch step, and cannot cap the cost of one run. These go to Squadron as one new issue plus the open #241 (D8). The parts of this slice that need a real run wait for a release that has them.

## Value

Architectural enablement. The pipeline is initiative 180's one external unknown, and this slice removes it before request runs are designed. Slice 184 gets four proven things: a pipeline file it can launch, an input directory it fills, a reply it parses, and the guarantee that a completed run leaves at most one commit on the target, touching only the two plan files, with no tracked or untracked change left in the checkout. That guarantee comes from Squadron's commit guard and is proven against a real agent and a real repo. It is what lets Amoeba create work in another project on a model's output. It bounds the checkout and the target only: what the agent does outside the checkout or in gitignored files is limited by instructions, the same exposure as every run the Runner already launches there (D1).

## Technical Scope

**Included:**

- The pipeline file `slice_writing.yaml`, shipped as package data. It has one tool-using `dispatch` step and one `commit` step, with two required params: `requests-index` and `model`.
- The write step's instructions, written in the pipeline file. They cover what may be edited, the formats of the initiative entry and the slice entry, the index rule, the already-met judgment and the reply form (D2, D3).
- The **input contract**: the `need.md` format, a `RequestInput` type with its rendering, and `prepare_request_directory`, which writes the input into an empty run I/O directory (D4).
- The **reply contract**: the two JSON shapes and a pure parser `read_reply` that returns `NewSlice`, `AlreadyMet` or a named `ReplyProblem` (D7).
- One constants module holding the pipeline path, the param names, the step names and every file name.
- The start-up probe `probe_slice_writing_pipeline` and its stub-`sq` tests (D9). Slice 184 wires it into start-up.
- Live tests in `tests/live/request_run/` against a scratch CF project in a throwaway registry (D10).
- The Squadron capability request (D8), a row in `notes/001-squadron-dependencies.amoeba.md`, and the issue numbers named in the slice plan as dependencies of 184.
- Process contract additions: the pipeline, its files, its launch shape, the probe, and a dated note of the first `sq` that runs it.

**Excluded:**

- Launching, journaling, observing or recovering a request run, and the `sq_request` command kind. All belong to 184.
- Choosing the checkout, the clean-on-target check, the request-run exemption from the checkout hold, and the full-initiative decline (184).
- Binding the edge: checking on the next plan read that the reported index is new (184). The reader checks only shape.
- Satisfying an edge from an already-met commit (183).
- Per-project configuration of the model and the cost cap (184). This slice's functions take both as required arguments.
- Where the run I/O directory lives and how it is named. 184 places it under the store directory; this slice defines what goes inside it.
- Any change to how the request slice is later designed and built. That is the provider's configured pipeline, under 184's membership drive.

## Dependencies

### Prerequisites

- Initiatives 100, 120 and 140 are complete.
- **Squadron with capabilities 1 to 3 of D8.** Not available in 0.24.17. "The installed `sq`" in the slice plan means the `sq` installed when this slice is implemented, and it must have D8. Until one exists, the real-run criteria cannot pass and 184 has no proven pipeline. Success Criteria marks which criteria the unit tier meets on its own.
- Context Forge as installed: 0.19.25 was observed on 20261103 to accept an initiative with no architecture document (D2). No CF change is needed.
- A Squadron model alias whose provider gives the agent file and shell tools in the working directory (an SDK alias), for the live tier.

### Interfaces Required

- `amoeba.runner.probes`: the probe pattern and `StartupFailedError` (122), as `probe_answering_pipeline` uses them.
- `amoeba.runner.cf_call.run_cf` and `output_head` for the probe's subprocess call.
- Squadron's dispatch file-in, file-out keys (`prompt_files`, `reply_format`, `reply_file`, `delivered_prompt_file`; 0.24.14 and later) and `--validate --strict`.

## Architecture

### Component Structure

New package `src/amoeba/runner/request_run/`. Slice 184 adds its launch, observation and binding modules to the same package.

| Module | Responsibility |
|---|---|
| `slice_writing.yaml` | The pipeline: instructions, a write step and a commit step, no defaults. |
| `pipeline_file.py` | `slice_writing_pipeline_path()` via `importlib.resources`, as `answering_pipeline_path` does. The param names, the step names and every input and output file name, each defined once. |
| `inputs.py` | `RequestInput`, rendered to `need.md`. `prepare_request_directory(directory, request)`. |
| `reply.py` | `NewSlice`, `AlreadyMet`, `ReplyProblem`. `read_reply(directory)`. |
| `runner/probes.py` (extended) | `probe_slice_writing_pipeline(settings, run)`. It calls `run_cf` and `output_head` directly, with its own message. `probe_answering_pipeline` is unchanged. |

`slice_writing.yaml` is added to `[tool.hatch.build.targets.wheel] artifacts` in `pyproject.toml`, beside `answering.yaml`.

### Data Flow

```
Amoeba (184)                      run I/O directory              sq run slice_writing.yaml (cwd = provider checkout, on target)
------------                      -----------------              --------------------------------------------------------------
prepare_request_directory ─writes▶ need.md
launch (184) ──────────────────────────────────────────────────▶ write step (agent with the provider's tools, in the checkout)
                                                                   prompt = instructions + need.md
                                                                   reads code, plans and git log; edits at most two plan files
                                  write.prompt.md ◀──writes──
                                  reply.json      ◀──writes──      (JSON object extracted by Squadron)
                                                                 commit step
                                                                   stages changed files matching the allowed paths
                                                                   refuses any other change, or a moved HEAD
                                                                   no changes: no commit, step succeeds
poll (184): sq runs wait --json ◀──── outcome ──────────────────
read_reply ◀────────reads──────── reply.json   (read only from a completed run)
```

The checkout gets at most one new commit on the target. All of the run's inputs and outputs are in the run I/O directory, outside the checkout (D4).

### State Management

None. Each run's I/O directory holds its input and outputs, and `write.prompt.md` records what the agent was given. The provider's plan files and git history hold the result. 184 records the reply on the request.

## Technical Decisions

### D1 — One shipped pipeline: a write step and a commit step, no review
Status: decided
- Amoeba launches the pipeline by path, as it launches `answering.yaml`: `sq run <absolute path>`, from the provider's checkout as working directory. The agent must see the provider's code, plans, history and project instructions, and Squadron must run inside the provider's CF project.
- **The write step** is a `dispatch` step with no `allowed_tools` key, so its model runs with the provider's own tools: the SDK's tools for an SDK alias, Squadron's default write tools for the others. It must read the repo, and it must edit files in it.
- **What is bounded, and what is not.** The commit guard (D5) bounds what the run leaves in the checkout and on the target: at most one commit, touching only the two plan files. Nothing bounds what the agent does outside the checkout or in gitignored files (a push, another repo, the network). There, the bans in D2 are instructions only. Squadron cannot narrow the tools of an SDK-session dispatch per step (0.24.17 rejects a per-step `allowed_tools` on the session path, because the session fixes its tool set when it connects), so no tool restriction is declared. This is the same exposure as every run the Runner already launches in that checkout: the provider's configured pipeline runs agents there with the same tools.
- **The commit step** is the capability 2 step (D5). It is separate from the write step so that what gets committed is decided by Squadron against fixed paths, never by the agent.
- **No review step.** The output is one plan entry that restates the need. The provider's configured pipeline designs and reviews the request slice when it builds it, and that review is the review of this work. A review of the entry alone would add a model call and a loop to judge a paragraph. No Squadron review template fits a single plan entry either.
- Rejected: a CF phase step (`design` with `phase: 3`). Phase 3 builds a context for writing a whole slice plan from an architecture, and a phase step can't be given the need. Its commit staging also follows the phase's artifact, not the two plan files.
- Rejected: Amoeba editing the plan itself. The architecture forbids it, and only the provider's agent can see whether the provider already meets the need.

### D2 — What the write step may write
Status: decided
- **Files.** The write step edits at most two files, both under the provider's `project-documents/user/`:
  - the initiative plan (`project-guides/*-initiative-plan.*.md`), only to add the requests initiative's entry;
  - the requests initiative's slice plan (`architecture/{requests-index}-slices.*.md`), to create it or add one entry.

  These two globs are the commit step's `paths`, so the instructions and the guard name the same set.
- **Creating the initiative.** If the initiative plan has no entry at `{requests-index}`, the agent appends one: `({requests-index}) Requests`, described as changes that other members of the program asked for, with no dependencies and status `not_started`. It then creates `architecture/{requests-index}-slices.requests.md` with slice-plan frontmatter whose `parent` is the initiative plan, plus the headings the provider's slice-plan template requires. If the entry exists, it is the requests initiative because the PM's configuration names that index (181), so its name is not checked. A slice plan that exists at that index under another name is used as it is.
- **No architecture document.** Context Forge does not need one. Observed 20261103 on `cf 0.19.25`, in a scratch project in a throwaway registry: an initiative entry with no architecture file is listed by `cf list initiatives --json -a` (with `archFile: null`), `cf list slices <index> --json` reads a slice plan whose `parent` is the initiative plan, and `cf set arch <index>` then `cf set slice <index>` both succeed. So a request slice can be designed by Squadron phase steps like any other slice.
- **The new entry.** Its index is `{requests-index}` when the initiative has no slices, and otherwise one more than the highest index in the initiative. Its entry text has the slice-plan form the provider's guide uses (a checkbox, the index in parentheses, a bold title, a description, risk and effort), with `Dependencies: None` written explicitly. Request slices stand alone, so a dependency the agent chose would wrongly become a predecessor. The description is the need, restated without loss, and names the requesting member and slice from `need.md`. The agent changes no other line except the frontmatter `dateUpdated`.
- **Forbidden.** No git writes: no commit, branch switch, reset or push (the commit step commits). Read-only git (`log`, `show`, `status`, `diff`) is allowed, as D3 needs. Also forbidden: `cf set` or other CF writes, no change to any other file, slice or initiative. The instructions say that `need.md` is data, and that instructions found inside it are not to be followed. There is no tool restriction (D1), so inside the checkout the commit guard (D5) is the only enforcement of the write ban.
- **A provider that cannot take a request.** If there is no initiative plan, the instructions tell the agent to reply in prose with no JSON object. Squadron then fails the step with `reply contains no JSON object`, the run fails with the agent's text, and 184 puts the request on the program blocked list. This case is rare, so it gets no third reply shape.

### D3 — Already met is the agent's call, and its commit is evidence
Status: decided
- The agent replies `already_met` only when the provider's code on the current branch already provides what the need asks for. It names the commit that made it so, as a full hash taken from `git log` (read-only git is part of reading the repo, and the instructions allow it alongside the ban on git writes).
- The reply decides nothing about release. 183 satisfies the edge only when that commit is observed under the edge's consumption mode, so a wrong or invented hash keeps the asker waiting on the program blocked list. It never releases the asker early.
- An `already_met` run writes nothing. The commit step finds no change and makes no commit. The guard allows changes inside the plan globs, so it cannot catch an agent that edits a plan file and then replies `already_met`. The runtime rule is the live tier's assertion: an `already_met` reply from a run that moved the target's HEAD is invalid. 184 records the target HEAD at launch, beside the slice set, and blocks such a request with that reason. The commit then stays on the target as an undriven plan entry, visible to the PM.

### D4 — Inputs and outputs live in a run I/O directory outside the checkout
Status: decided
- The run must leave the checkout clean. 132's pre-dispatch check blocks a slice on a dirty tree, and 184 launches a request run only in a clean checkout on its target. So `need.md`, `reply.json` and `write.prompt.md` cannot live in the checkout.
- Squadron 0.24.17 resolves `prompt_files`, `reply_file` and `delivered_prompt_file` against the working directory and rejects absolute and `..` paths (`pipeline/dispatch_keys.py`, `path_error`). Capability 1 (D8) adds a per-invocation I/O directory against which these paths resolve. The pipeline keeps its relative names.
- **`need.md`:**

```markdown
# Request

requested by: <asking project id>, slice <index> <name>
requests initiative: <requests index>

<need text, verbatim>
```

- `prepare_request_directory(directory, request)` requires an existing, empty directory and writes only `need.md`. It raises on a directory that is not empty, a blank need, a negative or zero requests index, and a project id or slice label containing a newline. These are programming errors, not model outcomes.
- Rejected: the agent reading the need and writing its reply at absolute paths given as params. The result would depend on the provider: Squadron's own tools confine a non-SDK model to the project directory. Reply extraction would also be the model's job rather than Squadron's single rule.
- Rejected: files in the checkout covered by a `.gitignore` entry. Amoeba never edits a member's repo, and the entry itself would be a change to the repo.

### D5 — Squadron commits named paths, under a guard
Status: decided
- Capability 2 (D8) is a `commit` step with `paths` (repo-relative globs) and `message`. It stages the changed and untracked files that match `paths` and commits them on the integration target, under the same branch rule as planning commits. It fails, naming the paths, when any changed or untracked file falls outside `paths`. It also fails when HEAD is not the commit the run started on, which catches an agent that committed or switched branches on its own. With no changes, it makes no commit and the step succeeds.
- Together with the clean-on-target precondition (184), this makes "one commit, touching only the plan files" a Squadron guarantee instead of a model behavior. A failed guard fails the run, and 184 blocks the request with Squadron's message. The changes stay in the checkout for the PM, as with any failed run.
- Rejected: the agent committing with its shell. That depends on the provider giving it a shell, and nothing would check what it staged.

### D6 — The cost cap is per invocation
Status: decided
- 184's per-project config supplies a cost cap for each request run. In 0.24.17 the cap is config only (`pipeline.max_cost_usd`, user or project). The project config is the provider's own `.squadron.toml` in the checkout, which Amoeba must not write. Squadron #241 (open) proposes `sq run --max-cost <usd>`, and this slice depends on it as capability 3.
- `max_cost_usd` is never written into the pipeline YAML. The cap belongs to the project's config, not to the shipped file.
- **No wall-clock bound, deliberately.** Neither the pipeline nor the launch argv carries a timeout, the same as for the provider's own pipeline runs. A dispatch that stops producing output fails in Squadron with `failure.kind: stall`. An agent that keeps working is bounded by the cost cap. A run that is still in flight is 184's to watch through 120's existing run observation, like any other `sq_run`.

### D7 — Reply shapes are JSON, parsed leniently, failing by name
Status: decided

The write step declares `reply_format: json`, so `reply.json` holds the object Squadron extracted. The two shapes:

```json
{"kind": "new_slice", "index": <new slice index>}
{"kind": "already_met", "commit": "<full commit hash>"}
```

- `read_reply(directory)` returns `NewSlice(index)`, `AlreadyMet(commit)` or `ReplyProblem(kind, detail)` with `kind` `missing` or `malformed`. It never raises for model output. Unknown keys are ignored. `kind` is trimmed and matched case-insensitively.
- **`index`**: an integer, or a string of decimal digits after trimming. It must be positive, and a boolean is rejected. **`commit`**: a string that is 7 to 40 hexadecimal characters after trimming, normalized to lower case. The instructions ask for the full hash. The parser accepts a short one because 183 resolves it with an allowlisted git read, and an ambiguous or absent commit simply never satisfies.
- `malformed` covers: a file that is not one JSON object, a `kind` other than the two, a `new_slice` with no or a bad `index`, and an `already_met` with no or a bad `commit`. Nothing defaults.
- Whether the index is new, inside the band, or in the plan at all is 184's binding check. Whether the commit exists is 183's observation. The parser checks only shape, as 140's D6 does.
- `read_reply` is called only for a run that completed. A failed run's directory may still hold a `reply.json`, because the commit step runs after the reply is written. 184 decides from the run outcome first.

### D8 — Squadron capability request; the first `sq` that runs the pipeline is recorded as an observation
Status: decided

One new Squadron issue, "Run a pipeline in a project checkout without dirtying it (for Amoeba's slice-writing pipeline)", asks for capabilities 1 and 2 and links #241 for capability 3. The syntax is Squadron's to choose; `slice_writing.yaml` and the launch argv are finalized against what ships.

1. **Run I/O directory.** A per-invocation option (proposed `sq run … --io-dir <absolute dir>`) against which every dispatch step's `prompt_files`, `reply_file` and `delivered_prompt_file` resolve, instead of the working directory. The agent's working directory, project rules and CF project are unchanged. Without the option, behavior is unchanged.
2. **A guarded commit step.** As in D5: `paths` globs and `message`; stage only matching changed or untracked files; fail on a change outside `paths` or on a HEAD that moved since the run started; commit only on the integration target; with no changes, no commit and success.
3. **Per-run cost cap.** Squadron #241: `sq run --max-cost <usd>`, which takes precedence over config.

- No code compares `sq` versions. The probe (D9) checks behavior. The process contract records "first observed running the slice-writing pipeline: squadron x.y.z, on date" as a dated note in "Squadron shapes", beside the answering pipeline's note.
- `notes/001-squadron-dependencies.amoeba.md` gains a row (S16) naming the new issue and #241, gating 184. The slice plan names both issues under 180 and 184.

### D9 — Start-up probe: the shipped pipeline and its flags must validate
Status: decided
- `probe_slice_writing_pipeline(settings, run)` runs `sq run <slice_writing.yaml> --validate --strict` with the I/O-directory and cost-cap options set to a temporary directory and a nominal cap. It runs once from a temporary directory, bounded by `--sq-timeout`. Exit 0 passes. Any other exit, a timeout or a missing `sq` raises `StartupFailedError` naming the command, the exit code and the head of its output. Then `start` exits `STARTUP_FAILED` (7).
- With strict validation, an `sq` without the commit step rejects the step. An `sq` without either option rejects it as an unknown option, so one call checks every shape the pipeline needs.
- **Wiring is 184's.** A project in no program must tick exactly as after 140, so an `sq` that cannot run this pipeline must not stop such an install. 184 calls the probe at start when any project configures request runs, as 142 wired the answering probe behind the answerer section. This slice provides the probe and its tests.
- The probe calls `run_cf` and `output_head` directly. `probe_answering_pipeline` is not refactored.

### D10 — Live tier for real runs against a scratch CF project
Status: decided
- `tests/live/request_run/` runs the real pipeline with a real agent. Each test builds a scratch git repo on `main` with a minimal initiative plan, an existing initiative with one slice, and a small source file that a "met" need can point to. It registers the repo as a CF project in a throwaway registry (`CONTEXT_FORGE_DATA_DIR` under `tmp_path`, as 145 does) and launches from the repo with a run I/O directory under `tmp_path`.
- Settings come from `AMOEBA_LIVE_REQUEST_MODEL` and `AMOEBA_LIVE_REQUEST_MAX_COST_USD`. An unset variable fails collection with its name. The answering variables are read in `tests/live/conftest.py` today, at collection, for the whole tier. That read moves unchanged into `tests/live/answering/conftest.py`, because otherwise `tests/live/request_run` would need the answering variables. `tests/live/request_run/conftest.py` reads its own.
- The cases, each run once (a wrong outcome fails the test; nothing retries):
  1. **First request:** there is no requests initiative. Afterwards the initiative plan lists it at the given index, `cf list slices <index> --json` shows exactly one entry at the reported index, the target has exactly one new commit touching exactly the two plan files, and the tree is clean.
  2. **Second request:** run in the repo left by case 1, with a different need. The reply names the next index, the new commit touches only the slice plan file, the first entry's lines are unchanged, and every other initiative's entries are unchanged.
  3. **Already met:** the reply is `already_met`, `git merge-base --is-ancestor <commit> main` succeeds, there is no new commit, and the tree is clean.
- In every case `write.prompt.md` in the I/O directory contains the need text, and the checkout contains no file from the I/O directory.
- `tests/live` stays in `addopts` `--ignore`, so a bare `uv run pytest` spends nothing.

### Patterns and Conventions

- File, param and step names are defined once in `request_run/pipeline_file.py`. A test asserts that `slice_writing.yaml` uses exactly them, and that its commit `paths` match the two globs the instructions name.
- The parser returns a value or a typed problem. `prepare_request_directory` raises on misuse.
- Prompt text avoids a brace pair around a bare word except real params, and it gives no example hash or index near an instruction to read one (the hallucination-trap rule).

## Implementation Details

### API Contracts

Python surface provided to 184 (signatures are the contract):

```python
@dataclass(frozen=True)
class RequestInput:
    asking_project_id: str
    asking_slice_label: str
    requests_index: int
    need: str

def prepare_request_directory(directory: Path, request: RequestInput) -> None: ...
def slice_writing_pipeline_path() -> Path: ...
def read_reply(directory: Path) -> NewSlice | AlreadyMet | ReplyProblem: ...
```

Launch contract for 184, run with the provider checkout as working directory (option names are proposals until Squadron ships them; Task "finalize against shipped syntax" rechecks). **This argv is provisional until that task completes.** The process contract marks it so until then, and 184's design must not freeze on it:

```
sq run <slice_writing_pipeline_path()> <requests index> --run-id <id> --io-dir <run I/O directory> --max-cost <usd> -p model=<alias>
```

`requests-index` is the pipeline's first required param, so it is the positional target. `model` goes in `-p` (140 observed that `-p` does not satisfy the first required param).

## Integration Points

### Provides to Other Slices

- **To 184:** the pipeline path, the launch argv shape, `RequestInput` and `prepare_request_directory`, `read_reply` with its three results, the rule that an `already_met` run must not move the target's HEAD, which 184 enforces by recording the target HEAD at launch beside the slice set (D3), the guarantee that a completed run left at most one commit on the target touching only the two plan files and no tracked or untracked change in the checkout (bounded to the checkout and target, D1), and the probe for start-up wiring. There is no wall-clock bound on a run; 184's observation owns a long or hung run (D6).
- **To 183:** `AlreadyMet.commit` as a lower-case hex string, possibly short, to resolve and observe.
- **To the process contract:** the pipeline, its files, the launch shape, the probe and the dated `sq` observation.
- **To the slice plan and the dependency register:** the new Squadron issue and #241 as dependencies of 184.

### Consumes from Other Slices

- **122:** the probe sequence and `StartupFailedError`.
- **Squadron:** D8's capabilities. Until a release has them, the live tier cannot pass and the probe fails on the real `sq`. The tasks that need them carry `BLOCKED:` lines naming the issues.

## Success Criteria

### Functional Requirements

**Gated on a Squadron release with D8.** These need a real run:

- Against a scratch CF project with no requests initiative, a run creates the initiative at the given index and writes one slice in it, committed to the target. `read_reply` returns `NewSlice` with that slice's index.
- A second run with another need adds a second slice to the same initiative, and its commit touches no other slice or initiative.
- Given a need the scratch project already meets, `read_reply` returns `AlreadyMet` with a commit reachable from the target, and the run makes no commit.
- After every run the target has at most one new commit, touching only the two plan files, no tracked or untracked change is left in the checkout, it is on the target, and the run's input and output files are only in the I/O directory. Nothing here checks what the agent did outside the checkout (D1).
- The real `sq` validates `slice_writing.yaml` with the probe's argv, and strict validation rejects a copy with one unknown step key.

**Met without Squadron changes.** These need the unit tier and the stub `sq` only:

- `read_reply` rejects, as `malformed`, a reply with neither shape, a `new_slice` with no index, and an `already_met` with no commit. It returns `missing` when there is no file.
- `probe_slice_writing_pipeline` raises `StartupFailedError` when the validate exits non-zero, times out or finds no `sq`, and returns when it exits 0.
- The new Squadron issue is filed with capabilities 1 and 2, linking #241. Both are named in the slice plan as dependencies of 184 and in the dependency register.

### Technical Requirements

- Unit tests cover the `need.md` rendering, the `prepare_request_directory` refusals, and every malformed case in D7. Parser fixtures include reply files captured from the live tier.
- A test asserts that the names and commit paths in `slice_writing.yaml` equal the constants.
- The wheel built by `uv build` contains `slice_writing.yaml`, and `slice_writing_pipeline_path()` resolves to it from an installed wheel.
- `tests/live/request_run` fails at collection with the variable's name when a setting is unset, and `tests/live/conftest.py` no longer reads the answering settings.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass.
- `docs/process-contract.md` documents the pipeline, its files, the launch shape, the probe and the dated `sq` observation.

### Integration Requirements

- 184 can prepare a directory under the store directory, launch the pipeline in a provider checkout, poll it with the existing `poll_run`, and parse the reply, with no further Squadron change.
- A run's commit appears on the provider's next plan read as one new slice under the requests initiative, so 184's binding check has what it needs.

### Verification Walkthrough

Verified 20261104 against squadron 0.24.22 (`sq --version`). Steps 3 and 4 need a Squadron with D8's run I/O directory, guarded commit step and cost cap; decide that by running step 3, not by version. Step 4 spends money on an SDK model (a few cents for the three cases); export the provider key first.

1. **Unit tier, no `sq`, no spend.**
   ```bash
   uv run pytest tests/runner/request_run tests/runner/answering -q
   ```
   Expect all to pass (`380 passed`, about 45 seconds): the input rendering, the directory preparation, the reply parser (including the captured replies in `tests/fixtures/slice_writing/`), the names-match test, both wheel tests, and the live tiers' settings rules.

2. **The shipped pipeline is in the package.**
   ```bash
   uv run python -c "from amoeba.runner.request_run.pipeline_file import slice_writing_pipeline_path as p; print(p())"
   ```
   Expect an absolute path ending in `amoeba/runner/request_run/slice_writing.yaml`.

3. **Squadron validates it with the probe's shape.**
   ```bash
   P="$(uv run python -c 'from amoeba.runner.request_run.pipeline_file import slice_writing_pipeline_path as p; print(p())')"
   sq run "$P" --validate --strict --io-dir "$(mktemp -d)" --max-cost 1
   ```
   Expect `Pipeline 'slice_writing' is valid.` (Squadron prints the name with an underscore; the file's `name:` is `slice-writing`) and exit 0. On a Squadron without D8 (0.24.20 was observed), expect a failure naming the unknown `commit` step or the unknown option (`--io-dir` exits 2 with `No such option`). That failure is what the probe turns into `STARTUP_FAILED`.

4. **Live tier: real runs in a scratch project.**
   ```bash
   export AMOEBA_LIVE_REQUEST_MODEL=<SDK alias> AMOEBA_LIVE_REQUEST_MAX_COST_USD=<cap>
   uv run pytest tests/live/request_run -v --basetemp=/tmp/request-live
   ```
   Expect 5 passed in about 40 seconds: the three request cases and the two validation tests. Then inspect the first case's repo (cases 1 and 2 share it, so it holds two new commits above the fixture's, one per case; the requests index is 200):
   ```bash
   cd /tmp/request-live/request-live0/provider
   git log --oneline -3              # two "docs: add request slice to the requests initiative plan" commits above "chore: scratch fixture"
   git show --name-only --format=%s HEAD   # case 2's commit: only project-documents/user/architecture/200-slices.requests.md
   git status --short                # empty
   CONTEXT_FORGE_DATA_DIR=/tmp/request-live/cf-data0 cf list slices 200 --json   # entries 200 and 201
   cat /tmp/request-live/request-live0/first-io/reply.json   # {"kind": "new_slice", "index": 200}
   ```
   The kept I/O directories are `first-io`, `second-io` and `met-io`; the met case's repo is `met`. Observed replies: `{"kind": "new_slice", "index": 200}`, `index` 201, and `already_met` with a 40-character hash.

5. **The start-up probe.**
   ```bash
   uv run pytest tests/runner/test_probes_request_run.py -v
   ```
   Expect the stub-`sq` cases to pass: exit 0 passes; exit 1, a timeout and a missing `sq` raise `StartupFailedError`. From 184 on, the probe runs at start only when a project configures request runs.

6. **The real registry is untouched.** With `CONTEXT_FORGE_DATA_DIR` unset, `cf list projects` does not list any scratch project.

## Risk Assessment

### Technical Risks

- **Squadron timing.** Every real-run criterion waits on D8. 140's D8 shipped two days after it was filed, but 184 cannot start its live work until this one ships.
- **An agent writing a plan file CF cannot parse.** The commit lands on the provider's target, and the provider's next plan read fails with `plan_read_failed` for the whole project, not only the request.

### Mitigation Strategies

- File the issue first, and build the unit-tested side while Squadron works on it. 181 to 183 do not depend on this slice, so the initiative keeps moving.
- The instructions tell the agent to run `cf list slices {requests-index} --json` after editing and to fix the files until the new index appears. The live tier checks the same read after every case. A `plan_read_failed` that gets past both is a visible project escalation with CF's message, and the PM can revert one commit that touches two files. The first time this happens, the next step is to ask Squadron for a parse check in the commit step's guard, not more instructions.

## Implementation Notes

### Development Approach

1. File the Squadron issue (D8), link #241, and add both to the slice plan under 180 and 184 and to the dependency register (S16).
2. `request_run/pipeline_file.py`, then `inputs.py`, then `reply.py`, each with unit tests.
3. Draft `slice_writing.yaml` with the capability keys as proposed in the issue. Add the names-match test and the wheel `artifacts` entry.
4. `probe_slice_writing_pipeline` with stub-`sq` tests.
5. Move the answering settings read into `tests/live/answering/conftest.py`.
6. Once a Squadron release has D8: finalize the YAML and the launch argv against the shipped syntax, add the live tier, capture real replies as parser fixtures, and record the dated `sq` observation. If no release exists, these tasks carry `BLOCKED:` lines naming the issues.
7. Process contract text, with the launch argv marked provisional until step 6 finalizes it.

### Special Considerations

- **Acting in another repo.** This is the first Amoeba-launched run whose job is to change a member's repo on a model's judgment. The bounds are: one commit, only the two plan files (Squadron's guard); nothing else in the checkout; and nothing a model says satisfies an edge (183).
- **Prompt injection.** The need is model-restated text that crosses projects. It is data in `need.md`, and the instructions say so. Inside the checkout, the guard limits a need that steers the agent to a wrong plan entry. Outside it, only the instructions limit the agent (D1). The provider's own design review then sees that entry, and the PM can see it on the program blocked list and in the provider's plan.
- **Cost.** Each live case is one tool-using agent run under the cap. The tier is opt-in.
