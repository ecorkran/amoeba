"""The client part of ``add`` (slice 261, D5).

Kept out of ``add.py`` so the hub's ``add`` never imports ``here`` (the code that runs
``cf`` and ``git``). It first refuses the fields the call's door may not set, then
gathers the checkout when an entry names no member: bare ``add``, ``--attach-to``,
``--new-member``, and a bulk entry with no member. ``--project`` and a bulk file whose
entries all name members need no gathered value and make no ``cf`` call.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from amoeba.operations.add import AddRequest, names_no_member
from amoeba.operations.add_door import refuse_door_fields
from amoeba.operations.here import gather_checkout
from amoeba.operations.here_document import HereCheckout, HereNotAProject
from amoeba.operations.set_up_models import SetUpResult
from amoeba.store.vocabulary import Door
from amoeba.upstream.context_forge.cli_call import CfRun

type Gathered = HereCheckout | HereNotAProject | None


def gather_add(
    document: object, directory: Path, run: CfRun, git: CfRun, door: Door
) -> SetUpResult | Gathered:
    """The door's refusal, or what ``add`` needs gathered from ``directory``.

    A refusal is a rejected result, returned before anything is gathered. A document
    that does not parse gathers nothing: ``add`` rejects it as ``malformed``.

    Raises:
        ContextForgeError: ``cf`` or ``git`` failed to give a usable answer.
    """
    refused = refuse_door_fields(document, door)
    if refused is not None:
        return refused
    try:
        request = AddRequest.model_validate(document)
    except ValidationError:
        # Not a valid request: ``add`` reports it as malformed, and needs no gather.
        return None
    if not names_no_member(request):
        return None
    return gather_checkout(directory, run, git)
