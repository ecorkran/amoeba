---
docType: slice-design
slice: live-walkthrough
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 180
- 181
- 182
- 183
- 184
- 185
- 145
- 144
interfaces: []
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 23
promptTokens: 1939060
cachedTokens: 1821113
cacheWriteTokens: 117903
completionTokens: 25779
durationSeconds: 328.3
costUsd: 1.823534
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.823534
    completionTokens: 25779
---

# Slice Design: live-walkthrough

## Overview

Slice 186 runs program coordination end to end against real Squadron runs, real agents and real repos, as 145 did for the answerer. A throwaway program of three scratch CF projects is built in a throwaway registry, with scratch checkouts and a throwaway supervisor directory. The real registry and the real supervisor directory are never written.

It covers the slice plan's three cases:

1. **New slice, from source.** A design run in the asking project stops on a question that needs a change in a provider. The answerer turns it into a request. The provider's request run writes a slice into its requests initiative, the provider's pipeline builds it, the PM merges it, and the asker resumes with instructions naming the slice and commit.
2. **Already met, from source.** A second question asks a provider for something it already has. The request run reports it met with a commit, and the asker is released through the same reachability observation.
3. **From release.** A request to a provider consumed from a release is built, and the edge waits for the PM's edge resolution before the asker is released.

The slice ships the three scratch project trees, a setup script, `docs/program-walkthrough.md`, one deterministic fixture test, and the fixtures captured from the live run. It changes no product code.

## Value

Verification of milestone 5. Slices 180–185 are each proven against stub `sq` scenarios and rows written by tests; 180's live tier runs the slice-writing pipeline alone. 186 is the first run where every hop is real: a real design agent's question, a real answering run deciding to request, a real request run editing a real plan, a real provider pipeline building the slice, and a real resume of the paused asker. It shows the PM what coordination does on real repos (program-store rows, journal entries, question records, the program blocked list) and gives a demonstration that can be repeated after any change to Amoeba, Squadron or Context Forge. It also turns the shapes met live into fixtures for the stub tiers.

## Technical Scope

Included:

- Three scratch project trees under `scripts/program_walkthrough/` (D1, D2, Implementation Details).
- `scripts/program_walkthrough.py setup`, which builds the throwaway registry, checkouts, supervisor directory, project config and program registration (D5, D6).
- A project parameter on three per-project helpers in 145's `answerer_walkthrough.py`, so the program script can call them (D6).
- `docs/program-walkthrough.md`: the steps, the PM actions, and the rows to check after each case (D6).
- A deterministic test that the asker's source assembly over the scratch trees includes the program passages each case depends on (D6).
- Running the three cases live and writing what was observed under the task file (D7).
- Adding every captured question tail, answer-step request reply and request-run reply to the fixtures (D8).
- A link to the walkthrough doc from the program stage section of `docs/process-contract.md`.

Excluded:

- Any change to product code. A defect found in 180–185 is filed as an issue (D7). The one interface gap known now, the edge id on the program blocked list, is closed in 183, D13 (D9).
- Supersession, gate refusals (request limit, reverse request, full band), crash points and recovery. 183–185's scenario tests cover them with stubs.
- Unreadable members against real CF (`snapshot_missing`, `checkout_unresolved`). The walkthrough shows all three members `readable`; the other reasons stay test-covered (181).
- Chains across three members, separate request checkouts, and anything else the architecture defers.

## Dependencies

### Prerequisites

- **180–185 implemented and merged**, including the edge id on 183, D13's edge rows (D9).
- **A Squadron release with 180's D8 capabilities** (run I/O directory, guarded commit step, per-run cost cap #241) and 140's D8. On 20261103 the installed `sq` was 0.24.17, which lacks 180's. Whether a release has them is decided by 180's start-up probe, not by its version number. Until one exists, the live tasks carry `BLOCKED:` lines naming 180's Squadron issues. The trees, the setup script, the doc draft and the fixture test can be built before that.
- Provider keys for the agents, in a `.env` file the user supplies, copied into each scratch checkout (145).
- Five live variables, already defined by earlier live tiers: `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL`, `AMOEBA_LIVE_MAX_COST_USD` (140, 144) and `AMOEBA_LIVE_REQUEST_MODEL`, `AMOEBA_LIVE_REQUEST_MAX_COST_USD` (180).

### Interfaces Required

The CLI commands, listings, config sections and reply shapes 181–185 define, as their designs specify, and 145's setup and inspection commands. The one gap, the edge id for `resolve-edge`, is D9.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Scratch trees | `scripts/program_walkthrough/{notes-store,notes-export,notes-cli}/` | Each committed as its checkout's first commit |
| Setup script | `scripts/program_walkthrough.py` | `setup --dir D --env-file F`: builds three projects, submits the program registration, writes the config, prints exports |
| Fixture test | `tests/runner/program/test_walkthrough_fixture.py` | The asker's assembly over the trees has the concept and member passages |
| Walkthrough doc | `docs/program-walkthrough.md` | The repeatable steps and the expected rows per case |
| Fixtures | 144's `question_tails.json`, 180's reply parser fixtures, 185's answer reader fixtures | Gain the walkthrough's captures (D8) |

Nothing is added under `src/`.

### Data Flow

```
program_walkthrough.py setup --dir D --env-file F
  per project P in (notes-store, notes-export, notes-cli):
    D/checkouts/P  ← copy of tree, git init, first commit on main, .env copied (gitignored)
    cf init --no-ide, cf set …   (CONTEXT_FORGE_DATA_DIR=D/cf)
    amoeba submit create-project / link-cf-project   (AMOEBA_STORE_DIR=D/store)
  amoeba submit register-program  (program notes, concept in notes-store)
  D/projects.yaml  ← D5

case N:  PM drives a notes-cli slice → forced question (D3) → 185's request
  → 184's request run and binding in the provider → 183's observation and release
  → notes-cli run resumes → done.  PM steps per case: D4.
```

### State Management

All state lives under `D`: three checkouts and their git history, the throwaway registry `D/cf`, the supervisor directory `D/store` (three project stores, `programs/programs.sqlite3`, both inboxes, answering and request run directories) and the config. Nothing persists outside `D`. The last step checks that the real registry does not list any scratch project.

## Technical Decisions

### D1 — Three projects: one asker, a from-source provider, a from-release provider

Status: decided

- A program member has one default consumption mode, and an override is per dependent. With two projects there is one dependent pair, so one edge mode. Case 3 needs a from-release edge and cases 1 and 2 a from-source one, both waited on by the same asker. Three projects is the smallest program that has both.
- `notes-cli` asks. `notes-store` is consumed `from_source` (the CLI builds against its sibling checkout). `notes-export` is consumed `from_release` (the CLI installs it as a package).
- `notes-store` holds the program concept, so the asker's concept passage is read from another member's checkout (182, D3), the path real programs take.
- Every member gets `requests_initiative: 700`, a required field (181, D4). It is clear of each tree's initiative 100.
- **Rejected:** two projects with case 3 using a reverse edge (store asking CLI). It mixes the reverse-request refusal into the run and needs the CLI to serve requests.

### D2 — Pipelines: `p4` for the asker, `p456` for the providers

Status: decided

- **Asker `p4`**, as in 145 (D1 there). Each forced question is asked at the design step; the resume after release completes the design and the slice goes `done`. Building the CLI would test nothing more of coordination.
- **Providers `p456`.** A from-source edge is satisfied only by the providing slice's branch head reaching the provider's target (183, D3), and release names that head on both modes (183, D10 `branch_head_missing`). So the provider's pipeline must produce the slice branch `{index}-slice.{name}`. `p456` does, and stops before the merge. The merge is the PM's, the cost the architecture accepts for a provider that does not merge. The walkthrough's PM merge is what moves case 1 from `not_on_target` to satisfied.
- **Ordering.** The asker's slices are driven one at a time, the next only after the previous is `done`: a slice is ready only when the next lower index is `done` (145's correction), and one checkout runs one pipeline. Case 2 starts only after case 1's merge has left `notes-store` clean on `main`, which the request run's checkout rule requires (184, D5).
- **Rejected:** `p4` for providers. Design commits land on the target with no slice branch, so every edge would wait `branch_head_missing`.

### D3 — The asker's slice entries force a question that needs another member's change

Status: decided

- The forcing pattern is 145's revised form: *Before you design anything, write no design and end your reply with one question asking for {member} to provide {capability}, which this slice uses; if your prompt already begins with an answer to that question, write the design instead.* Release instructions open "The change this run was waiting on has landed" (183, D7), which the condition treats as the answer, so the resumed run designs.
- The wording names the member and the capability and never says "ask the PM", or reserves the question, or says documents do not count (145's corrections: the entry is a passage).
- **The concept places each capability in its provider's part**, and nothing in the asker's sources says the capability exists. So the answer step has no answer and the concept tells it whose part the need is in (185, D2). Case 2's capability does exist in `notes-store`'s source, but no passage the asker sees says so; only the request run, which sees `notes-store`, can find it (architecture: "only they can see whether the provider already has it").

| Slice | Case | Asks for |
| --- | --- | --- |
| 100 Filter by tag | 1 | `notes-store` to provide a function returning the notes that carry a given tag |
| 101 Import a notes file | 2 | `notes-store` to provide a function that reads every note from a JSON Lines file |
| 102 Export to Markdown | 3 | `notes-export` to provide Markdown export of a list of notes |

- `notes-store`'s tree has `read_notes(path)` in `src/notes_store/jsonl.py` and no tag function. `notes-export`'s tree has a plain-text exporter and no Markdown one.

### D4 — PM actions are exactly the ones the architecture reserves

Status: decided

The PM does three things, and no others unless a case goes wrong (D7):

1. Drives each asker slice with `submit intent ... '{"intent": "drive"}'`, one at a time.
2. Merges `notes-store`'s request slice branch into its `main` in case 1 (`git checkout main && git merge --no-ff <branch>` in the scratch checkout). This is "a merge the provider's pipeline does not make".
3. Submits `amoeba submit resolve-edge --by pm --edge-id <id>` in case 3, after `notes-export`'s request slice is `done`. This is "a release".

The PM never drives a provider slice: request slices run by membership drive (184, D12), which the walkthrough proves by their running undriven. Each provider's own initiative-100 slice is never driven and never runs.

### D5 — The walkthrough configuration

Status: decided

The setup script writes literal values, failing with the variable's name when any of the five live variables is unset:

```yaml
projects:
  notes-cli:
    pipeline: p4
    answerer:
      answer_limit: 1
      request_limit: 1                       # one live request per provider
      reserved_terms: [push, merge, release, DROP]
      rules_paths: [CLAUDE.md]
      passages_max_chars: 100000
      answer_model: ${AMOEBA_LIVE_ANSWER_MODEL}
      check_model: ${AMOEBA_LIVE_CHECK_MODEL}
      max_concurrent_runs: 1
      max_cost_usd: ${AMOEBA_LIVE_MAX_COST_USD}
  notes-store:
    pipeline: p456
    requests:
      model: ${AMOEBA_LIVE_REQUEST_MODEL}
      max_cost_usd: ${AMOEBA_LIVE_REQUEST_MAX_COST_USD}
  notes-export:
    pipeline: p456
    requests:
      model: ${AMOEBA_LIVE_REQUEST_MODEL}
      max_cost_usd: ${AMOEBA_LIVE_REQUEST_MAX_COST_USD}
```

- `request_limit: 1` is enough: each provider has at most one live request at a time, because the cases run in order and each edge is released before the next case.
- The providers have no `answerer` section. A question their `p456` agents ask goes to the PM as an ordinary block, is answered by resolution, and is recorded under the task (Special Considerations).
- The reserved terms are 145's, unchanged, so the walkthrough runs the screen a real program would. Case 3's need is for a provider consumed as a released package, so its wording may say "release". A `reserved_term: release` decline of that need is a product finding under D7, not a config to tune.

The program registration the script submits:

```
amoeba submit register-program --by operator --program-id notes \
    --concept-member notes-store --concept-path docs/program-concept.md \
    --members '[{"project_id":"notes-store","requests_initiative":700,"consumed":"from_source","overrides":{}},
                {"project_id":"notes-export","requests_initiative":700,"consumed":"from_release","overrides":{}},
                {"project_id":"notes-cli","requests_initiative":700,"consumed":"from_source","overrides":{}}]'
```

The script submits the registration and does not read its outcome: a submission is applied only by the resident process, which is not running during setup. After start, `inspect program-submissions` shows the outcome, and the walkthrough stops unless it is `applied`.

### D6 — Repeatable from the repository: trees, script, doc, one deterministic test

Status: decided

- **Trees.** Committed in Amoeba's repository at their CF paths, so a later run uses the same plans and forcing wording. They hold no real project names, credentials or model aliases.
- **Per-project steps.** 145's `build_checkout`, `read_cf_project_id` and `submit_project` already do every per-project step 186 needs (copy, `git init` and first commit, `.env` copy, `cf init --no-ide`, `cf set`, the CF project id read, `create-project` and `link-cf-project`). They read the module constants `TREE`, `PROJECT_ID` and `CF_ARTIFACTS` and the one-checkout `Layout`, so they cannot set up three projects as written. They gain one parameter carrying the project id, tree, plan-file pairs and checkout path, in place in `answerer_walkthrough.py`. 145's `setup` passes its constants, so its behavior and its test are unchanged. `program_walkthrough.py` imports them with `run_step`. No module is added. Copying them would duplicate the steps and their failure rules.
- **Script.** `program_walkthrough.py setup --dir D --env-file F` refuses an existing `D`, builds the three projects with those helpers, submits the registration (D5), writes `D/projects.yaml`, and prints the `export` lines, the `amoeba start` command. The asker slices' node ids are read after start from `inspect nodes`. Script failures follow 145: any non-zero subprocess stops it, reporting the step, the command and its stderr, and leaving `D` in place.
- **Registry isolation.** `CONTEXT_FORGE_DATA_DIR=D/cf` exported for every spawned `cf` and `sq`, and `--cf-data-dir D/cf` for Amoeba. The doc's last step runs `cf project list` with the variable unset and confirms that no scratch project is listed.
- **Doc.** `docs/program-walkthrough.md` is the only full walkthrough: commands, PM actions and the rows to check per case. It is updated to what was run in Phase 6. The Verification Walkthrough below points to it.
- **Fixture test.** Using 182's fixture-repository helpers, it assembles sources for `notes-cli` slices 100–102 with a program context built from the three trees. It checks that the member list names all three members, that a `program_concept` passage from `notes-store` is present, and that it places tag lookup and file reading in `notes-store`'s part and Markdown export in `notes-export`'s part. A concept edit that dropped one would otherwise surface only as a live decline. No LLM, no `sq`.
- **Rejected:** a script that drives the cases. The PM's actions and the checks between them are what the walkthrough demonstrates.

### D7 — Each case runs once; a wrong outcome is a recorded finding

Status: decided

145's D7 rules apply (fixture cause, product cause, model judgement, environment), with a rerun going on a new asker slice appended at the end of the plan. Additions for this slice:

- **Product cause** includes case 3 declined `reserved_term: release` on a legitimate need: filed as an issue against 185's request screen.
- **Model judgement** includes a request run that writes a slice for a need already met (case 2) or reports met for one that is not (cases 1, 3).
- **A failed request** is left for the PM's resolution of the asker's block, which withdraws it (184, D10).
- **Completion.** The slice is complete with a case closed as shown in part under 145's model-judgement rule. The task Result and `docs/program-walkthrough.md` mark that case not demonstrated, and milestone 5's end-to-end claim is stated only for the cases shown.

### D8 — Every captured shape becomes a fixture

Status: decided

The slice plan's "any request or reply shape the walkthrough meets that the fixtures lacked becomes a fixture" is met by taking all of them, so nobody judges which are new (145, D8):

- Every `checkpoint.question` tail, from `inspect questions --json`, into 144's `tests/live/answering/fixtures/question_tails.json` with run id, capture date and `source: 186-walkthrough`.
- Every answer-step reply artifact with `kind: request`, from the answering run directories, into 185's `read_answer` fixtures.
- Every request run's `reply.json`, from `D/store/requests/<run_id>/`, into 180's reply parser fixtures.

Each fixture keeps its run id and `source: 186-walkthrough`. If a capture shows a deterministic defect, the D7 issue includes a stub-tier case built from it.

### D9 — The edge id is on the program blocked list (183, D13)

Status: decided

- Case 3 needs the PM to name an edge in `resolve-edge`. 183, D13's edge row carried the waiting node and the question block but not the edge id, and no other listing shows open edges.
- 183, D13 now says an edge row's `context` column holds the edge id. No column is added, so 181's column tuple is unchanged. It is implemented with 183, not in 186. The walkthrough reads the id from `program-blocked --json`.

### Technology Choices

- Nothing new. The scripts are stdlib Python (`subprocess`, `shutil`, `pathlib`), as in 145, calling the installed `git`, `cf` and `amoeba`.

### Patterns and Conventions

- The script prints what it created. A value read from another tool's output stops the script when missing; it is never filled in.
- Project ids and the program id are constants at the top of `program_walkthrough.py`, used by the script, the fixture test and nowhere else.

## Implementation Details

### Scratch Project Contents

A small notes tool split into three repos. Each tree follows `file-naming-conventions.md`, so CF and 143 find the plan files, and has a `.gitignore` holding `.env`.

| Tree | Holds |
| --- | --- |
| `notes-store` | `CLAUDE.md` (two short rules). Concept, initiative plan (initiative 100), architecture and a one-slice plan for itself. `src/notes_store/jsonl.py` with `read_notes(path)` and `write_note(path, note)`. `docs/program-concept.md`: the program concept |
| `notes-export` | `CLAUDE.md`, concept, initiative plan (100), architecture, one-slice plan. `src/notes_export/text.py`, a plain-text exporter |
| `notes-cli` | `CLAUDE.md`, concept, initiative plan (100), architecture, and a slice plan with slices 100–102 (D3), each ending with its forcing sentence |

`docs/program-concept.md` names the three projects and each one's part: `notes-store` owns note files, reading, writing and querying notes (tags included); `notes-export` owns every output format and is released as a package; `notes-cli` owns commands and depends on the other two. It says nothing about which functions exist today.

No provider tree has an initiative in 700–709, so each provider's requests band starts open at 700 (184, D4).

## Integration Points

### Provides to Other Slices

- **Stub tiers of 144, 180, 185:** real captures as fixtures (D8).
- **160 (notification bridge):** a repeatable live program with real edge and request rows on the program blocked list to deliver.
- **200 (program conversation):** a three-member scratch program to anchor a conversation on.
- **The PM:** `docs/program-walkthrough.md`, repeatable after any change to Amoeba, Squadron or Context Forge.

### Consumes from Other Slices

- **180:** the shipped pipeline and its start-up probe. An `sq` without 180's D8 fails the probe at start, before any case runs, because two projects have a `requests` section (184, D14).
- **181–185:** the interfaces their designs specify. Where a listing's column names differ from this design when those slices land, the doc uses the implemented names.

## Success Criteria

### Functional Requirements

- **Case 1.** A real design question in `notes-cli` slice 100 becomes a `requested` record, a request and an unbound edge to `notes-store`. `notes-store`'s request run adds slice 700 in a new requests initiative 700, committed to `main`, and the edge binds to it. The slice runs undriven under `p456` and goes `done` with its branch head recorded. The edge waits `not_on_target` until the PM merges the branch, then the asker's run resumes with instructions naming `notes-store`, the slice and the commit, and slice 100 goes `done`.
- **Case 2.** Slice 101's request to `notes-store` ends `met` with a commit reachable from `main`, no new slice in `notes-store`, and the asker released with instructions naming that commit.
- **Case 3.** Slice 102's request to `notes-export` is built as slice 700 in its requests initiative. After `done` the edge waits `awaiting_release`; after the PM's `resolve-edge` the asker is released naming the slice and commit.
- A case closed as shown in part under D7 meets its requirement as recorded, marked not demonstrated.
- `amoeba inspect program` shows all three members `readable` with the real `cf`, in the throwaway registry `D/cf` (the user's own registry is never read or written).
- At the end, the real registry lists no scratch project, and nothing is written outside `D`.

### Technical Requirements

- The fixture test passes without `sq` or a model.
- The setup script refuses an existing `D`, and a missing live variable, each with a message naming it, and stops on any non-zero subprocess, reporting the step and leaving `D`.
- `answerer_walkthrough.py` behaves as before with the project parameter; its test passes.
- `ruff`, `pyright` strict and the existing suites pass.

### Integration Requirements

- `docs/program-walkthrough.md` holds the steps as run, and `docs/process-contract.md`'s program stage section links it.
- Every capture is in its fixture file with run id, date and `source: 186-walkthrough`, and the tiers that read them still pass.
- Any defect found is an open issue, linked from the task notes.

### Verification Walkthrough

Draft; refined after Phase 6. The steps, PM actions and rows to check per case are `docs/program-walkthrough.md` (D6).

1. **Fixture test, no `sq`, no model.**
   ```bash
   uv run pytest tests/runner/program/test_walkthrough_fixture.py tests/test_answerer_walkthrough_script.py -v
   ```
2. **Setup.** Needs a Squadron release with 180's and 140's D8, provider keys and the five live variables.
   ```bash
   uv run python scripts/program_walkthrough.py setup --dir <D> --env-file <path to your .env>
   ```
3. **The cases.** Follow `docs/program-walkthrough.md` from `amoeba start`.

## Risk Assessment

### Technical Risks

- **Squadron dependency.** The live cases need a release with 180's D8, which does not exist on 20261103.
- **Agent variance across five model-driven hops** (design question, answer, check, request run, provider build) makes a clean single pass less likely than in 145.

### Mitigation Strategies

- The non-live work is built first, and live tasks carry `BLOCKED:` on the named Squadron issues until a release exists (145's approach).
- Forcing sentences fix the questions; the concept fixes whose part each need is; the fixture test pins the passages; D7 bounds reruns and separates safe misses from defects.

## Implementation Notes

### Development Approach

1. The project parameter on 145's three helpers; its test still passes.
2. The three trees and the fixture test.
3. `program_walkthrough.py` and step 2 up to `amoeba start`. Without a 180 D8 release the probe fails; record that.
4. The doc draft.
5. The three cases live (`BLOCKED:` until a release exists).
6. Captures into fixtures, issues for findings, and the doc updated to what was run.

Relative effort: 3 (three projects and two provider builds, against 145's one project).

### Special Considerations

- **Spend.** Three asker `p4` runs and their resumes, three answering runs, three request runs and two provider `p456` runs, each capped by its configured `max_cost_usd`. The provider builds are kept small by the trees (one function each).
- **Unplanned questions.** An asker question goes through the answerer and may itself become a request; a provider question goes to the PM. Each is recorded and its tail captured (D8).
- **A provider review loop that never passes** ends in a `paused` block on the request slice, which holds `notes-store`'s checkout. The PM resolves it; the outcome is recorded under the task.
- **Secrets.** The `.env` is copied into each scratch checkout, ignored by git, and never committed or printed.
