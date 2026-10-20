---
docType: review
layer: project
reviewType: code
slice: network-api
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/109-slice.network-api.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: 6c0d3e113c69646230abf64b9e4f44121a0415f9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
diffTruncated: false
turns: 4
promptTokens: 493631
cachedTokens: 315930
cacheWriteTokens: 177695
completionTokens: 7849
durationSeconds: 79.2
costUsd: 1.699689
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: language-rules
    summary: "The HTTP submission body is validated by hand, though the project already uses Pydantic at this kind of boundary"
    location: "src/amoeba/serve/submissions.py:84-121"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The stream slot leaks if starting the follow thread fails"
    location: "src/amoeba/serve/feed_route.py:79-88"
  - id: F003
    severity: concern
    category: security
    summary: "New serve tests pass the whole parent environment, including any real token, to the child process"
    location: "tests/cli_harness.py:207-226"
  - id: F004
    severity: concern
    category: testing
    summary: "Test case ids are written out twice next to index-based parametrization"
    location: "tests/cli/test_serve.py:97-109"
  - id: F005
    severity: note
    category: design
    summary: "The full option list of a listing is assembled in two places"
    location: "src/amoeba/cli/inspect.py:54-65"
  - id: F006
    severity: note
    category: design
    summary: "The same JSON choice reaches `run_listing` twice"
    location: "src/amoeba/cli/inspect.py:33-65"
  - id: F007
    severity: note
    category: design
    summary: "The request guard imports a constant from a route module"
    location: "src/amoeba/serve/auth.py:16"
  - id: F008
    severity: note
    category: security
    summary: "The token comes from `os.environ`, as documented"
    location: "src/amoeba/serve/settings.py:1-21"
  - id: F009
    severity: pass
    category: design
    summary: "A single error vocabulary, enforced by a test"
    location: "src/amoeba/serve/errors.py"
  - id: F010
    severity: pass
    category: concurrency
    summary: "The event loop is never blocked, and the thread hand-off is documented"
    location: "src/amoeba/serve/stream.py:176-245"
  - id: F011
    severity: pass
    category: design
    summary: "A shared listing registry, with rows and `as_of_seq` read from one snapshot"
    location: "src/amoeba/inspection/__init__.py#read_listing"
  - id: F012
    severity: pass
    category: testing
    summary: "Load tier present, with real bounds asserted"
    location: "tests/load/test_serve_load.py"
---

# Review: code — slice 109

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] The HTTP submission body is validated by hand, though the project already uses Pydantic at this kind of boundary

The Python rules say "Use Pydantic for all external boundaries (API inputs/outputs…)" and "Validate everything entering the system via Pydantic." Pydantic is already a dependency (`pyproject.toml:9`), and the inbox envelope uses it at its own boundary (`src/amoeba/inbox/envelope.py`, `payload_config.py`).

`parse_body` does the same job by hand. It uses a `_BODY_TYPES` table, an unknown-key check, a loop of `isinstance` checks, two `cast(dict[str, object], …)` calls, and `str(...)` on values that were already checked to be strings. A frozen `BaseModel` would replace all of that and drop the casts:
- `extra="forbid"`
- `strict=True`
- `kind: SubmissionKind`
- `payload: dict[str, object]`

The only special case left would be mapping a missing `submission_id` to `SUBMISSION_ID_REQUIRED`, which you can do by checking the `ValidationError` location. As written, the network contract's body shape has a second, hand-rolled validator beside the Pydantic one used everywhere else.

### [CONCERN] The stream slot leaks if starting the follow thread fails

`FeedEndpoint.__call__` takes the slot, then frees it in an `except BaseException` that only covers the preflight. The next line, `await self._stream(project_id, cursor, release)(scope, receive, send)`, has two parts:
- It builds the response, which calls `start_follow_thread`. That can raise `RuntimeError: can't start new thread` under thread exhaustion, which is the condition `max_streams` exists to prevent.
- It then enters `EventStreamResponse.__call__`.

If the first part raises, `on_close` never runs and the slot is never released. The module states that the slot is released "however many exit paths call it," and `_Release` is idempotent. The fix is to put the whole hand-off under the same `try`, so `release()` runs on any failure before the response takes ownership.

### [CONCERN] New serve tests pass the whole parent environment, including any real token, to the child process

The testing rules say "Never inject a whole `.env` into a test process. Pass an explicit list of named variables." `start_serve` defaults to `cli_environment`, which copies all of `os.environ` (`tests/cli_harness.py:45`).

- `tests/cli/test_serve.py` handles this by removing `TOKEN_ENV_VAR` in `_environment`.
- `tests/cli/test_serve_smoke.py:79` calls `start_serve(supervisor, ["--port", …])` with the default environment. A developer or CI runner with `AMOEBA_SERVE_TOKEN` set would hand that credential to the server, and the smoke test would then fail with 401s.
- `test_other_commands_never_load_uvicorn` (`tests/cli/test_serve.py:217`) also passes `{**os.environ, …}`.

The fix is to have `start_serve` always remove `TOKEN_ENV_VAR` unless the caller sets it, or to build the child environment from a short allowlist (PATH, the virtualenv variables, and the store directory).

### [CONCERN] Test case ids are written out twice next to index-based parametrization

`test_an_unsafe_bind_exits_13_naming_the_rule` is parametrized over `range(6)`, with an `ids=[…]` list that repeats the case ids already returned by `_refusal_cases`. If a case is added, removed or reordered in one place and not the other, the reported test names stop matching what actually ran.

`tests/serve/test_policy.py:103-106` does the same with `range(4)` and a separate id list for `_unusable`.

The cases are built per test only because they need the `tls_files` and `tmp_path` fixtures. Two fixes would keep one source for the ids:
- Parametrize on the case-id string and look the case up in a dict built from the fixtures.
- Make the cases fixture-independent and use `pytest.param(..., id=...)`.

### [NOTE] The full option list of a listing is assembled in two places

The CLI's `listing_request` builds `(*listing.flags, *listing.choice_options, *listing.value_options)`. `src/amoeba/serve/reads.py:85-88` builds the same tuple. A `Listing.options` property in `inspection/listing.py` would define it once. The docstring already explains why the three tuples stay separate (for `--help` order), and that reason still holds with a combined property.

### [NOTE] The same JSON choice reaches `run_listing` twice

`run_listing` gets the choice as `use_json=args.json` (from `main.py:239`), and `listing_request` reads `args.json` again to set `compact`. Today the two always agree. Still, the print form and the `compact` flag are separate inputs that could drift apart. Pass `use_json` through to `listing_request`, or drop the keyword.

### [NOTE] The request guard imports a constant from a route module

`auth.py` gets `JSON_MEDIA_TYPE` from `amoeba.serve.reads`, so the middleware depends on one of the route modules. `submissions.py` likewise gets `json_response` from `reads.py`. This works, but the shared HTTP constants and helpers would sit better in a small neutral module. `errors.py` is close to that role already.

### [NOTE] The token comes from `os.environ`, as documented

The rule "go through the settings object" is not broken in substance. `ServeSettings` is a dataclass, not a pydantic-settings object, and its module docstring explains why the credential is read once and kept off the settings: so it can never be logged with them. `cli/serve.py:59` treats an empty value as unset, and says so in a comment. Tests check that the token appears in no log record, response or refusal message.

### [PASS] A single error vocabulary, enforced by a test

- Codes, statuses, `Retry-After` values and the mapping from exceptions to codes are each defined once.
- Rule 5 in `tests/test_import_boundaries.py` checks that no other server module spells a code or an error status, and a test with a deliberate violation (`test_rule_5_reports_a_code_and_a_status`) shows the check works.

This meets the project's "never scatter comparison values" rule.

### [PASS] The event loop is never blocked, and the thread hand-off is documented

The async rules are met:
- Every store and filesystem call runs through `anyio.to_thread.run_sync` (`reads.py`, `submissions.py`, `feed_route._preflight`) or in the dedicated follow thread.
- Changes cross the thread boundary through a 1-slot memory object stream, and the docstring says so.
- The decision to close only from the loop is explained and covered by tests (`test_follow_thread.py`, `test_stream_response.py`).
- Every swallowed exception is a specific type with a comment saying why swallowing is correct.

### [PASS] A shared listing registry, with rows and `as_of_seq` read from one snapshot

- Moving the registry into `amoeba.inspection` removes the `TYPE_CHECKING` circular import the old `cli/inspect_*` modules had.
- Option names are now the one declared label, and both the CLI flag and the query parameter are derived from them.
- `read_transaction` gives the rows and the feed head one WAL snapshot, and `test_a_commit_between_two_queries_does_not_split_the_read` proves it.
- The parity test in `tests/serve/test_reads.py` checks every listing and every option against `inspect --json`.

### [PASS] Load tier present, with real bounds asserted

- 32 followers run over a real uvicorn.
- A 600-change burst crosses a batch boundary, and every follower must receive every change in order.
- The p95 commit-to-arrival latency at a steady rate is asserted to be at most 1 s.
- Idle streams are checked not to starve a read.

This meets the load-test rule for network and concurrency code.

### Run Digest

- Response length: 8310 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 493631 / 315930 / 177695 / 7849 / not computed
- Duration: 79.2 s
- Cost: $1.70 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
