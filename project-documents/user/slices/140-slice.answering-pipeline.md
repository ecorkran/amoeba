---
docType: slice-design
slice: answering-pipeline
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies: []
interfaces:
- 144
dateCreated: 20261101
dateUpdated: 20261101
status: in_progress
turns: 75
promptTokens: 6625803
cachedTokens: 6474040
cacheWriteTokens: 151639
completionTokens: 55200
durationSeconds: 587.4
costUsd: 3.612748
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.612747399999999
    completionTokens: 55200
revision_number: 2
---

# Slice Design: answering-pipeline

## Overview

The Squadron pipeline the answering run (slice 144) launches, shipped inside Amoeba and proven against a real `sq`. It has two steps. The **answer step** gets the question and a set of numbered, dated passages, and replies with an answer that cites passage ids or with a decline and a reason. The **check step** gets the question, the same passages and the answer step's reply, and nothing else from the answer step. It replies yes or no under the precedence rule: the later-dated passage wins. Both steps run with no tools, from a scratch directory Amoeba prepares. The run puts each step's reply, and the prompt each step was given, in files in that directory. Amoeba reads those files and never reads Squadron's run state.

The slice also fixes the files the pipeline reads and the files it writes, and adds a start-up probe that refuses an `sq` that cannot run the pipeline.

The installed Squadron (0.24.11, checked 20261101 against its source) cannot run this pipeline yet. Five capabilities are missing (D8). They go to Squadron as one issue. The parts of this slice that need a real run wait for a Squadron release that has them.

## Value

Architectural enablement. It removes the one external unknown in initiative 140 before the answering run is designed against it. Slice 144 gets a pipeline file it can launch, input files it fills, and reply files it parses, all already proven. The two properties the architecture's trust model rests on are proven here against real models: the answering run cannot touch files, and the check is independent of the answer step.

## Technical Scope

**Included:**

- The answering pipeline file, `answering.yaml`, shipped as package data. It has two `dispatch` steps and two required params: `answer-model` and `check-model`.
- The instructions for both steps, written in the pipeline file. That includes the citation rule, the decline form, the precedence rule, the check step's refusal of reserved actions, and PM-precedent matching (D3).
- The **input contract**: the `question.md` and `passages.md` file formats (D3), a `QuestionInput` type and its rendering to `question.md`, and the function that prepares a scratch directory (input files, an empty rules directory, and `.squadron.toml` with the cost cap and rules directory).
- The **artifact contract**: the JSON shape of the answer reply and the check reply, with pure parsers that return a typed result or a named error.
- One module of constants holding the pipeline path, the param names and every file name.
- A start-up probe, `sq run <answering.yaml> --validate`, that runs only when a project has an answerer section (D9).
- A live test tier, `tests/live/`, that runs the real pipeline with real models. It is never collected by a bare `uv run pytest`.
- The Squadron capability request (D8), filed as one issue.
- Process contract additions: the pipeline, its files, the probe, and a dated note of the first `sq` that runs it.

**Excluded:**

- Launching, journaling, observing or recovering an answering run: the `sq_answer` kind and the launch site belong to 144.
- Deciding anything from the replies: the citation check against the supplied set (143), the decide function (144), the gate (142).
- Assembling passages, numbering them and rendering them to `passages.md` (143). This slice fixes the `passages.md` format as a written contract. The two slices share no code, so 143 does not wait on this slice.
- Per-project configuration of models, cost cap or pipeline (144). This slice's functions take those values as required arguments.
- Where the scratch directory lives and how it is named: 144 places it under the store directory. This slice defines what goes inside it.

## Dependencies

### Prerequisites

- Initiatives 100 and 120 are complete.
- **Squadron with the D8 capabilities.** Not available in 0.24.11. "The installed `sq`" in the slice plan means the `sq` installed when this slice is implemented, and it must be a release with D8. Until one exists, this slice cannot complete, and 144 has no proven pipeline to build on. The slice plan names this external dependency on entry 140. Success Criteria marks which criteria the unit tier meets on its own and which are gated on Squadron.
- Model aliases on a provider that offers no native file access (OpenAI-compatible or OpenRouter profiles), for the live tier.

### Interfaces Required

- `amoeba.runner.probes.probe_sq` and the start-up path in `amoeba.process` that runs it (slice 122). The answering probe sits beside it.
- `ProcessSettings.sq_timeout_seconds` bounds the probe, as it does the existing one.
- Squadron's documented surfaces: `sq run <path> --validate`, `sq run <path> --run-id <id> -p k=v`, `sq runs wait <id> --json`, the project config file `.squadron.toml` in the working directory (`pipeline.max_cost_usd`, `rules_dir`), and the D8 additions.

## Architecture

### Component Structure

New package `src/amoeba/runner/answering/`. Slice 144 adds its stage modules to the same package.

| Module | Responsibility |
|---|---|
| `answering.yaml` | The pipeline. Instructions, two steps, no defaults. |
| `pipeline_file.py` | `answering_pipeline_path()` via `importlib.resources`. The param names and every input and output file name, defined once. |
| `inputs.py` | `QuestionInput`. Renders `question.md`. `prepare_scratch(directory, question, passages_markdown, max_cost_usd)`. |
| `artifacts.py` | `AnswerReply` (`ProposedAnswer` or `AnswererDecline`) and `CheckReply`. `read_answer(directory)` and `read_check(directory)` return a reply or an `ArtifactProblem` (`missing`, `malformed`). |
| `runner/probes.py` (extended) | `probe_answering_pipeline(settings, run)`. Raises `StartupFailedError`, like `probe_sq`. |

`answering.yaml` is added to `[tool.hatch.build.targets.wheel] artifacts` in `pyproject.toml`, beside the schema SQL, so it ships in the wheel.

### Data Flow

```
Amoeba (144)                       scratch directory                  sq run answering.yaml
------------                       -----------------                  ---------------------
prepare_scratch(...)   ──writes──▶ question.md
                                   passages.md
                                   rules/          (empty)
                                   .squadron.toml  (max_cost_usd, rules_dir)
launch (144)  ─────────────────────────────────────────────────────▶ answer step
                                                                       prompt = instructions
                                                                              + question.md + passages.md
                                   answer.prompt.md ◀──writes──
                                   answer.json      ◀──writes──      (extracted JSON object)
                                                                     check step
                                                                       prompt = check instructions
                                                                              + question.md + passages.md
                                                                              + answer step's reply
                                   check.prompt.md  ◀──writes──
                                   check.json       ◀──writes──
poll (144): sq runs wait --json  ◀──── outcome ──────────────────────
read_answer / read_check ◀─reads── answer.json, check.json
```

The check step never sees the answer step's prompt or conversation. Squadron gives it the answer step's reply text and nothing else (D4). Both steps go through Squadron's one-shot agent path, which builds a new agent per dispatch, so no session carries over between them (D2).

### State Management

None. Each run's scratch directory holds its inputs and outputs. The prompt files are the record of what each step was given. Amoeba keeps no state in this slice; 144 records the reply on the question record.

## Technical Decisions

### D1 — One shipped pipeline, two dispatch steps, launched by path
Status: decided
- The pipeline is a file in Amoeba's package, launched as `sq run <absolute path>`. Squadron accepts a pipeline path, so nothing is installed in Squadron's user pipeline directory, and the file Amoeba launches is always the one Amoeba shipped and tested.
- Both steps are `dispatch` steps. Phase steps (`design`, `tasks`) pull in Context Forge and commits, and `review` steps carry review templates. A bare dispatch is the only step type that sends exactly the prompt it is given.
- There is no step after the check. Deciding from the replies is Amoeba's pure function (144), not a Squadron `gate`, because the decision must come from recorded inputs that Amoeba reads.
- The check step runs even when the answer step declined. Squadron has no conditional steps, and a decline costs one extra short call. The check instructions say to reply no to a decline. 144 declines on the answer step's decline whatever the check says.
- Rejected: two separate `sq` runs with Amoeba writing the check input. That would make the check step's prompt trivially Amoeba's, but it doubles 144's journal entries, recovery cases and launch waits, and the architecture fixes one `sq_answer` entry per question.

### D2 — No tools and no shared session, guaranteed by Squadron
Status: decided
- Both steps declare that they use no tools, and Squadron must fail the step before it dispatches if its model would run with tools anyway. In 0.24.11, a non-SDK, non-Codex model given `allowed_tools: []` runs with no tools and with a fresh one-shot agent per dispatch. That path is what this pipeline needs.
- Two holes stay open in 0.24.11. On the SDK session path, `allowed_tools: []` is falsy, so the guard that rejects per-step tools lets the step through, and the step runs in the persistent session: with that session's tools, `bypassPermissions` and the earlier step's conversation. Codex-backed providers read files natively. A mistyped model in a project's configuration would therefore silently break both properties. The guarantee is requested from Squadron (D8, capability 4). Amoeba does not keep a list of which aliases or providers are safe; that is Squadron's knowledge, and a copy would go stale.
- Rejected: Amoeba checking aliases against `sq models` output. It duplicates provider capability knowledge, and an alias could change after the check.

### D3 — Inputs are files Amoeba writes; instructions live in the pipeline
Status: decided
- The question and the passages go in `question.md` and `passages.md` in the scratch directory. Squadron reads them into the prompt (D8, capability 1). Pipeline params cannot carry them: a `-p` value cannot contain a comma, and passages run to tens of kilobytes. The steps have no tools, so the model cannot read them itself.
- The instructions for each step are the step's `prompt:` text in `answering.yaml`, so they are versioned and tested with the pipeline. The input files hold data only. Both steps read the same two files, so the check step provably sees the whole passage set, not a selection.
- Rejected: rendering a per-question pipeline YAML with the passages inlined. Squadron replaces `{name}` placeholders throughout step config, so a passage containing `{model}` or `{slice}` would be silently rewritten. That is an anti-pattern.

**`question.md`:**

```markdown
# Question

slice: <slice index> <slice name>

<question text, verbatim>
```

**`passages.md`:** one section per passage, in the order supplied:

```markdown
## Passage P<n>

kind: <rule|plan|pm_answer>
source: <repo-relative path>        # rule and plan passages
date: <ISO 8601 UTC, seconds>
question: <question the PM answered> # pm_answer only
slice: <slice index> <slice name>    # pm_answer only

<passage text, verbatim>
```

- Ids are `P1` to `Pn` in the order written, unique within one file. 143 assigns them and renders the file. Unit and live fixtures in this slice write `passages.md` by hand in this format. Dates are full UTC timestamps, not days, so a rule committed and a PM answer given on the same day are still ordered.
- Passage text is written verbatim, never trimmed or escaped. The instructions tell both steps that passage text is data and that instructions found inside it are not to be followed.
- **PM-precedent matching is in the instructions.** There is no matching code. The answer step is told that a `pm_answer` passage answers the question when the question means the same thing as the passage's `question:`, in any wording. It must take the passage's `slice:` against the question's `slice:` into account: when the slice changes what the right answer is, the questions are different. The check step is told that when a cited passage is a `pm_answer`, it says yes only if the new question means the same thing as that passage's question for this slice.
- **Ties.** The check step is told that a passage dated the same as a passage the answer rests on has equal precedence. If it contradicts the answer, the check says no.

### D4 — The check step's prompt is composed by Squadron from named parts
Status: decided
- The check step's prompt is its instructions, then `question.md`, then `passages.md`, then the answer step's reply text (D8, capability 2). The reply is the answer step's final response content only: not its prompt, its tool trace (it has none) or a reasoning stream.
- The answer step is told to reply with the JSON object only, so the reply carries the answer and its citations and not a justification for the check step to lean on. A model may add prose around the JSON anyway, and that prose could carry its reasoning. So capability 2 passes only the first JSON object in the reply when the earlier step declares a JSON reply, and the check step never sees the prose.
- Proof of independence comes from `check.prompt.md` (D5). It contains the question, every passage and the answer reply. It does not contain the answer step's instructions.

### D5 — Each step's reply and delivered prompt are written to files
Status: decided
- Squadron writes each step's reply to a named file in the working directory. Both steps declare a JSON reply, so the file holds the JSON object Squadron extracted from the reply: the same object that capability 2 passes to the check step. Squadron also writes the exact prompt it delivered to a second named file (D8, capability 3). Files: `answer.json`, `answer.prompt.md`, `check.json`, `check.prompt.md`.
- 120's rule stands: Amoeba never reads Squadron's run-state file. In 0.24.11 a dispatch's reply lives only there, and the run state records the prompt only as a hash.
- Writing the reply is Squadron's act, not the model's, so it does not conflict with "no tools".

### D6 — Reply shapes are JSON, parsed leniently, failing by name
Status: decided

Answer reply, one of:

```json
{"kind": "answer", "answer": "<text to send as resume instructions>", "cited": ["P3", "P7"]}
{"kind": "decline", "reason": "<why the passages do not settle it>"}
```

Check reply:

```json
{"verdict": "yes", "reason": "<one or two sentences>"}
```

- **One extraction rule, in Squadron.** Squadron finds the JSON object in the reply (capability 2), and the reply file holds exactly the object the check step received (capability 3). Amoeba and the check step therefore cannot read different objects. Amoeba parses the file as JSON and does no extraction of its own. Unknown keys are ignored. `kind` and `verdict` are matched case-insensitively after trimming whitespace.
- It rejects with `ArtifactProblem(malformed, detail)`: a file that is not one JSON object; a `kind` other than `answer` or `decline`; an answer with empty text; a `cited` value that is not a list of strings; a decline with no reason; a `verdict` other than `yes` or `no`. A missing file is `ArtifactProblem(missing)`. Nothing defaults: an absent `verdict` is malformed, never `no`.
- Whether the cited ids exist in the supplied set, and whether `cited` is non-empty, is 143's citation check, so that rule stays in one place. The parser only checks the shape.
- Tests include reply files captured from the live tier, beside hand-written edge cases.

### D7 — Scratch directory contents and Squadron config isolation
Status: decided
- `prepare_scratch(directory, question, passages_markdown, max_cost_usd)` requires an existing, empty directory and refuses one that is not empty. It writes `question.md`, `passages.md`, an empty `rules/` directory and `.squadron.toml`:

```toml
"pipeline.max_cost_usd" = <max_cost_usd>
rules_dir = "<absolute path of directory>/rules"
```

- `.squadron.toml` is Squadron's documented project config, read from the working directory, and it overrides user config. The cost cap therefore applies to this run alone, which is what 144 needs ("`max_cost_usd` is set on every answering run").
- `rules_dir` matters for a dispatch on a non-SDK provider. Squadron appends project rules to the prompt from the first rules directory it finds: configured, then `./rules`, then `./.claude/rules`, then `~/.config/squadron/rules`, then `~/.config/squadron/templates`. On this machine the last one exists, so without the override, text Amoeba did not supply would enter the answering prompt unnumbered and uncitable. Pointing `rules_dir` at an empty directory means no rule files are sent. The scratch directory has no `AGENTS.md` or `CLAUDE.md`, so no conventions file is sent either. Each `*.prompt.md` shows the result.
- `max_cost_usd` is a required argument with no default, and must be positive.

### D8 — Squadron capability request; the first `sq` that runs the pipeline is recorded as an observation
Status: decided

One Squadron issue, "Isolated file-in, file-out dispatch steps (for Amoeba's answering pipeline)", lists these capabilities as requirements. The syntax is Squadron's to choose; `answering.yaml` is finalized against what ships.

1. **File content in a dispatch prompt.** A dispatch step names files in the working directory whose content is added to its prompt, after the step's `prompt` text, in the order listed, with no placeholder replacement inside the file content.
2. **An earlier step's reply in a later step's prompt.** A dispatch step names an earlier step in the same run, and that step's final reply text is added to the prompt. The earlier step's prompt and conversation are not added. When the earlier step declares a JSON reply, only one JSON object from its reply is added. That object is found by a single rule, which Squadron documents: the first `{` that opens a span parsing as a JSON object, inside a code fence or not. A reply with no such object fails the earlier step.
3. **Reply and delivered prompt to files.** A dispatch step names a file for its reply and a file for its delivered prompt, both written in the working directory. For a step that declares a JSON reply, the reply file holds the object extracted under capability 2, byte for byte what a later step receives. A failed step writes neither file, or leaves one already written as it is; it never writes partial reply text.
4. **A hard no-tools guarantee.** A step that declares no tools fails before dispatch, with a named error, when its model would run with any tool, file access or persistent session (the SDK session path, a provider that reads files natively). Today `allowed_tools: []` passes the SDK-path guard because the guard tests truthiness.
5. **Strict step validation.** `sq run <pipeline> --validate` fails on a step key that the step type does not know. Today any key is accepted (checked 20261101: `prompt_file:` on a dispatch step validates), so `--validate` cannot tell an `sq` that has capabilities 1 to 4 from one that lacks them.

- Following the project rule that no code compares upstream versions, Amoeba never checks `sq --version` for this. The probe (D9) checks behavior. The process contract records "first observed running the answering pipeline: squadron x.y.z, on date" as a dated note beside the existing 0.24.9 note. That note is the plan's "pin": it lives in `docs/process-contract.md`, "Squadron shapes", and only people read it. 144 relies on the probe, not the note.
- The issue number is added to the slice plan as a dependency of 140 and 144 when it is filed.

### D9 — Start-up probe: the shipped pipeline must validate
Status: decided
- `probe_answering_pipeline(settings, run)` runs `sq run <answering.yaml> --validate` once, bounded by `--sq-timeout`, from a temporary directory. Exit 0 passes. Any other exit, a timeout or a missing `sq` raises `StartupFailedError` naming the command, the exit code and the head of its output, and `start` exits `STARTUP_FAILED` (7), as the existing probe does.
- **It runs at start, after `probe_sq`, only when at least one project has an answerer section.** The architecture says a project with no answerer section behaves as 132 does, so an `sq` that can't run the pipeline must not stop such an install. The answerer section is first loaded in 142, so 142 wires the call into start-up behind that condition (slice plan, entry 142). This slice provides the probe and its tests.
- With capability 5, validation is a real shape check: an `sq` without capabilities 1 to 4 rejects the pipeline's keys. On 0.24.11, which accepts any step key, the probe passes even though the pipeline cannot run. The stub-`sq` tests are what prove the failure paths. Nothing in this slice claims the probe protects against 0.24.11.

### D10 — Live tier for real-pipeline tests
Status: decided
- `tests/live/` holds tests that run the real `sq` and real models. Like `tests/load`, it is added to `addopts` `--ignore`, so a bare `uv run pytest` never spends money. It runs only when named: `uv run pytest tests/live`.
- Models come from `AMOEBA_LIVE_ANSWER_MODEL` and `AMOEBA_LIVE_CHECK_MODEL`, and the cost cap from `AMOEBA_LIVE_MAX_COST_USD`. If any is unset, the tier fails at collection with the variable's name. It does not skip silently and does not fall back to a default.
- Each live test runs in its own `tmp_path` scratch directory with a minted run id. It waits with `sq runs wait <id> --json` and a bounded timeout, then asserts on the files.
- The precedence tests use fixed passage sets: one where a PM answer is dated after the rule it contradicts, and one where the rule is dated after. The matching tests use a PM answer passage plus two questions. One repeats the PM's question in different wording for the same slice; the other uses the same wording for another slice, where the slice changes the answer. Every case runs once against the real pipeline. A wrong verdict fails the test; nothing retries.
- **Scope against the plan entry.** The input contract and this tier are what running and proving the pipeline needs. The matching cases test this slice's own instructions. Each is one run under `AMOEBA_LIVE_MAX_COST_USD`, so they stay here. 144 repeats the criterion with question tails from real runs.

### Patterns and Conventions

- File names, param names and step names are defined once in `pipeline_file.py`. A test asserts that `answering.yaml` uses exactly those names, so the YAML and the code cannot drift apart.
- Parsers return a value or a typed problem and never raise for bad model output. Bad model output is a normal outcome, and 144 turns it into a decline reason.
- `prepare_scratch` raises on misuse (a directory that is not empty, a cost cap that is not positive, an empty `passages_markdown`). That is a programming error, not a model outcome.

## Implementation Details

### API Contracts

Python surface provided to 144 (signatures are the contract; bodies are implementation):

```python
@dataclass(frozen=True)
class QuestionInput:
    slice_label: str
    question: str

def prepare_scratch(directory: Path, question: QuestionInput, passages_markdown: str, max_cost_usd: float) -> None: ...
def answering_pipeline_path() -> Path: ...
def read_answer(directory: Path) -> AnswerReply | ArtifactProblem: ...
def read_check(directory: Path) -> CheckReply | ArtifactProblem: ...
```

`prepare_scratch` writes `passages_markdown` as given. It does not parse, renumber or trim it.

Launch contract for 144, run from the scratch directory as its working directory:

```
sq run <answering_pipeline_path()> <answer-model alias> --run-id <id> -p check-model=<alias>
```

`sq` binds the positional target to the pipeline's first `required` param, and `-p` does not satisfy a `required` param (observed 20261101 on `sq run <file> --dry-run -p answer-model=a,check-model=b`: "requires a 'answer-model' argument"). So `answer-model` is the positional target and `check-model` goes in `-p`. Squadron's shipped syntax may change this; Task 9.1 rechecks it.

## Integration Points

### Provides to Other Slices

- **To 144:** the pipeline path, the launch argv shape, `prepare_scratch`, `read_answer` and `read_check`, and the list of files a finished run leaves. 144 maps each `ArtifactProblem` and each reply to its decline reasons.
- **To 143:** the `passages.md` format in D3, as a written contract. 143 renders to it and owns the passage types, the ids and the citation check. No code is shared.
- **To the process contract:** the answering pipeline, its files, the probe, and the dated `sq` observation.
- **To the slice plan:** the Squadron issue number as a dependency of 140 and 144.

### Consumes from Other Slices

- **122:** the start-up probe sequence and `StartupFailedError`. A failing answering probe stops start-up exactly as a failing `sq` probe does.
- **Squadron:** D8's capabilities. Until a release has them, the live tier cannot pass and the probe cannot detect a missing capability, and the tasks that need them carry `BLOCKED:` lines.

## Success Criteria

### Functional Requirements

**Gated on a Squadron release with D8.** These need a real run:

- Run from a prepared scratch directory with a fixed question and passages, the pipeline leaves `answer.json`, `answer.prompt.md`, `check.json` and `check.prompt.md`. `read_answer` and `read_check` parse both replies without a problem.
- A passage that tells the agent to create `pwned.txt` leaves the scratch directory holding exactly the prepared files and the four output files.
- `check.prompt.md` contains the question, every passage id with its text, and the answer reply, and that embedded reply equals the object in `answer.json` that `read_answer` parses. It does not contain the answer step's instruction text. Neither prompt file contains a project rules block.
- With a PM answer dated after a rule it contradicts, the check replies `yes`. With the rule dated after the PM answer, it replies `no`. Both are real runs.
- A question that repeats a PM answer's question in different wording, for the same slice, gets an answer citing that PM passage, and the check replies `yes`. The same wording for another slice, where the slice changes the answer, ends in a decline or a check `no`.
- A pipeline step whose model would run with tools fails before dispatch, shown by a live test that sets `check-model` to an SDK alias.
- The real, installed `sq` validates `answering.yaml`, and an `sq` without capability 5 or capabilities 1 to 4 rejects it.

**Met without Squadron changes.** These need the unit tier and the stub `sq` only:

- `probe_answering_pipeline` raises `StartupFailedError` when `sq run <answering.yaml> --validate` exits non-zero, times out or finds no `sq`, and returns when it exits 0. All cases are shown with the stub `sq`.
- The Squadron issue is filed with D8's five capabilities, and its number is named in the slice plan as a dependency of 140 and 144.

### Technical Requirements

- Unit tests (no `sq`) cover the rendering of `question.md`, `prepare_scratch` refusals, and the parsers on every malformed case in D6. Parser fixtures include reply files captured from the live tier.
- A test asserts that the param, step and file names in `answering.yaml` equal the constants in `pipeline_file.py`.
- The wheel built by `uv build` contains `answering.yaml`, and `answering_pipeline_path()` resolves to it from an installed wheel.
- `tests/live` is excluded from the default run, and fails with the variable's name when a model or cost variable is unset.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass.
- `docs/process-contract.md` documents the pipeline, the input and output files, the probe, and the dated `sq` observation.

### Integration Requirements

- 144 can pass 143's rendered `passages.md` to `prepare_scratch` unchanged.
- 144 can launch the pipeline from a scratch directory under the store directory, poll it with the existing `poll_run`, and read both replies with no further Squadron change.

### Verification Walkthrough

Verified 20261101 on `squadron 0.24.12` for steps 1, 2, 3 (caveat below) and 5. Step 4 has not run: it needs an `sq` with D8's capabilities (ecorkran/squadron#284). On the `sq` checked, step 3 passes without proving anything, because that `sq` accepts any step key.

1. **Unit tier, no `sq`, no spend.**
   ```bash
   uv run pytest tests/runner/answering -q
   ```
   Expect every test to pass (69 passed on 20261101): the input rendering, the scratch preparation, the reply parsers, the pipeline names-match test, the wheel contents, and the live tier's settings rules. The wheel test runs `uv build`, so it needs `uv` on `PATH` and takes a few seconds.

2. **The shipped pipeline is in the package.**
   ```bash
   uv run python -c "from amoeba.runner.answering.pipeline_file import answering_pipeline_path as p; print(p())"
   ```
   Expect an absolute path ending in `amoeba/runner/answering/answering.yaml`. Output on 20261101: `/Users/manta/source/repos/manta/amoeba/src/amoeba/runner/answering/answering.yaml`.

3. **Squadron validates it.**
   ```bash
   sq run "$(uv run python -c 'from amoeba.runner.answering.pipeline_file import answering_pipeline_path as p; print(p())')" --validate
   ```
   Expect `Pipeline 'answering' is valid.` and exit 0 (observed on 0.24.12, which accepts the proposed keys because it validates no step keys). On an `sq` with capability 5, or without capabilities 1 to 4 once 5 exists, expect a validation error naming the unknown keys.

4. **Live tier: real runs, real spend.**
   ```bash
   export AMOEBA_LIVE_ANSWER_MODEL=<non-SDK alias> AMOEBA_LIVE_CHECK_MODEL=<non-SDK alias> AMOEBA_LIVE_MAX_COST_USD=<cap>
   export AMOEBA_LIVE_SDK_MODEL=<SDK alias>   # read only by the SDK-alias refusal test
   uv run pytest tests/live/answering -v --basetemp=/tmp/answering-live
   ```
   Expect tests for the answered case, the no-files case, the check input, both precedence cases, both matching cases and the SDK-alias refusal to pass. Then look at one run's files:
   ```bash
   ls -a /tmp/answering-live/<test>/            # prepared files plus the four outputs, nothing else
   cat /tmp/answering-live/<test>/check.json    # {"verdict": "yes", ...}
   grep -c "## Passage P" /tmp/answering-live/<test>/check.prompt.md   # equals the number of passages supplied
   ```
   Then confirm that `check.prompt.md` holds the answer reply and none of the answer step's instructions.

5. **The start-up probe.**
   ```bash
   uv run pytest tests/runner/test_probes_answering.py -v
   ```
   Expect 6 passed (20261101). The stub-`sq` cases pass: a validate that exits 0 passes, and a validate that exits 1, times out or finds no `sq` raises `StartupFailedError`. These stub cases are the proof of the failure paths. On 0.24.11 the real `sq` validates the pipeline even though it cannot run it, so a real-`sq` pass proves nothing until capability 5 ships. From 142 on, the probe runs at start only when a project has an answerer section.

## Risk Assessment

### Technical Risks

- **Squadron timing.** Every real-run criterion waits on D8. The architecture already rules out an Amoeba workaround.
- **Models and the precedence rule.** The check step might not apply "later date wins" reliably, especially with several conflicting passages.

### Mitigation Strategies

- The issue is filed first, and the unit-tested Amoeba side is built while Squadron works on it. 141 to 143 do not depend on this slice, so the initiative keeps moving.
- The precedence rule is stated in the check instructions with the dates in every passage header, and both directions are tested live. If the live tests show the rule is unreliable, that is a finding for 144's model choice and for future work item 3 (agreement across answering runs). It is not a reason to loosen the test.

## Implementation Notes

### Development Approach

1. File the Squadron issue (D8) and add its number to the slice plan under 140 and 144.
2. `pipeline_file.py`, then `inputs.py` with rendering and `prepare_scratch`, then `artifacts.py`, each with unit tests.
3. Draft `answering.yaml`: instructions, steps and params, with the capability keys as proposed in the issue. Add the names-match test and the wheel `artifacts` entry.
4. The probe in `probes.py` and its stub-`sq` tests. 142 wires it into start-up (D9).
5. Once a Squadron release has D8: adjust `answering.yaml` to the shipped syntax, add the live tier, capture real replies as parser fixtures, and record the dated `sq` observation in the process contract. If no such release exists, these tasks carry `BLOCKED:` lines naming the Squadron issue.
6. Process contract text for the pipeline, its files and the probe.

### Special Considerations

- **Prompt injection.** Passages come from committed project files and PM answers. They are data, and both steps are told so. With no tools, a passage that succeeds in steering the model can at worst produce a wrong reply. That reply still has to pass the check step, the citation check and 142's gate.
- **Cost.** Each live test is a real two-call run under the cost cap in `.squadron.toml`. The tier is opt-in for that reason.
