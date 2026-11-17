"""A wake command that records what it was given (slice 244, 9.1).

It writes its own argv, its whole environment and what it reads from stdin to the file
named by its first argument, then exits. The waking live test checks that file for the
message text a request carried: the design's criterion is that none reaches the command.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    output = Path(argv[0])
    record = {
        "argv": argv,
        "environment": dict(os.environ),
        "stdin": sys.stdin.read(),
    }
    output.write_text(json.dumps(record), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
