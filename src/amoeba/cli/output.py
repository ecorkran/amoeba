"""One line of output for the commands that print a text form or a JSON document."""

from __future__ import annotations

import json
import sys


def print_text_or_json(text: str, document: object, as_json: bool) -> None:
    """Write ``document`` as JSON when ``as_json``, otherwise ``text``."""
    sys.stdout.write((json.dumps(document) if as_json else text) + "\n")
