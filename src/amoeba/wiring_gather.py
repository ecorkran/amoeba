"""Placing the served operations: the client part first, then the hub part (261 D5).

One rule for every served operation, with a client file or without. The client part
runs here, on this machine: ``add``'s door refusal, ``cf`` (and ``git``) in the
caller's directory, ``sq`` and the run files. What a call needs gathered is decided
by ``operations.served.gather_needed``, the function the hub asks too, so the two never
differ. A ``ContextForgeError`` is raised before any hub part runs. Then with no client
file the hub part runs in process (``place_served``), and with one the values travel
beside the document in one door call (``wiring_door.route``).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from amoeba.config.user_config import UserConfig
from amoeba.operations.add_gather import gather_add
from amoeba.operations.deps import Deps
from amoeba.operations.here import gather_caller
from amoeba.operations.here_document import here_to_document
from amoeba.operations.list_view import ListResult
from amoeba.operations.message_results import SendResult
from amoeba.operations.names import OperationName
from amoeba.operations.run_gather import gather_machine_runs
from amoeba.operations.runs_document import runs_to_document
from amoeba.operations.served import (
    ClientValues,
    HereKind,
    ServedEdges,
    ServedResult,
    gather_needed,
    run_served,
)
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.status import StatusResult
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.steps.models import OPEN_RUNS
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.operations.wake_start import start_woken_wake
from amoeba.store.store import Store
from amoeba.store.vocabulary import Door
from amoeba.wire.protocol import HERE_BODY_KEY, RUNS_BODY_KEY


def _required(name: OperationName, directory: Path | None) -> Path:
    if directory is None:
        raise ValueError(f"{name.value} needs the caller's directory")
    return directory


def gather_values(
    name: OperationName,
    document: object,
    directory: Path | None,
    door: Door,
    deps: Deps,
    steps: Steps | None,
) -> ClientValues | SetUpResult:
    """What the client part gathers for ``name`` on ``document``, or the door's refusal
    of ``add`` (a rejected result, returned before anything is gathered).

    ``steps`` asks the hub which runs this machine's open questions name
    (``open_runs``), for the runs document's ``absent_runs`` (262 D9); ``None`` is a
    call through the door, which cannot ask until 7.3 and so reports none absent.

    Raises:
        ContextForgeError: ``cf`` or ``git`` gave no usable answer.
        ValueError: The operation needs the caller's directory and none was given.
        HubUnreachableError, HubRefusedError: ``open_runs`` got no reply or was
            refused.
    """
    needed = gather_needed(name.value, document)
    if name is OperationName.ADD:
        # The door's refusal comes first, whether or not the request needs a checkout.
        gathered = gather_add(
            document, _required(name, directory), deps.cf_run, deps.git_run, door
        )
        if isinstance(gathered, SetUpResult):
            return gathered
        return ClientValues(here=gathered)
    here = None
    if needed.here is HereKind.CALLER:
        here = gather_caller(_required(name, directory), deps.cf_run)
    runs = None
    open_runs = None
    if needed.runs:
        open_runs = None if steps is None else steps.run(OPEN_RUNS, OpenRunsRequest())
        runs = gather_machine_runs(deps, () if open_runs is None else open_runs.run_ids)
    return ClientValues(here=here, runs=runs, open_runs=open_runs)


def place_served(  # noqa: PLR0913 - invoke's arguments and what the gather needs
    name: OperationName,
    store: Store,
    document: object,
    directory: Path | None,
    door: Door,
    deps: Deps,
    load_config: Callable[[], UserConfig],
) -> ServedResult | SetUpResult:
    """The gather, then the hub part in process with this machine's own edges."""
    steps = LocalSteps(store, StepEdges(deps.clock, load_config))
    values = gather_values(name, document, directory, door, deps, steps)
    if isinstance(values, SetUpResult):
        return values
    edges = ServedEdges(clock=deps.clock, load_config=load_config, local=deps)
    result = run_served(name.value, store, document, edges, values)
    if isinstance(result, SendResult):
        # The hub part claimed any wake; this machine's client part starts it (262 D8).
        return start_woken_wake(steps, deps, result)
    if values.open_runs is not None:
        if isinstance(result, StatusResult):
            return pruned_status(result, deps, values.open_runs)
        if isinstance(result, ListResult):
            return pruned_list(result, deps, values.open_runs)
    return result


def pruned_status(
    result: StatusResult, deps: Deps, open_runs: OpenRunsReply
) -> StatusResult:
    """``result`` after the client's file clean-up, whose problems join its
    ``file_problems`` (262 D12). It reuses the ``open_runs`` reply the gather made."""
    report = deps.prune(lambda: open_runs, now=deps.clock())
    return _with_problems(result, report.problems)


def pruned_list(result: ListResult, deps: Deps, open_runs: OpenRunsReply) -> ListResult:
    """``pruned_status`` for the default ``list`` view, which is ``status``'s result."""
    return result.model_copy(
        update={"status": pruned_status(result.status, deps, open_runs)}
    )


def _with_problems(result: StatusResult, problems: tuple[str, ...]) -> StatusResult:
    if not problems:
        return result
    return result.model_copy(
        update={"file_problems": (*result.file_problems, *problems)}
    )


def body_keys(values: ClientValues) -> dict[str, object]:
    """The body keys that carry ``values`` beside the document (D5)."""
    keys: dict[str, object] = {}
    if values.here is not None:
        keys[HERE_BODY_KEY] = here_to_document(values.here)
    if values.runs is not None:
        keys[RUNS_BODY_KEY] = runs_to_document(values.runs)
    return keys
