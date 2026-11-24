"""The hub side of every store transaction a client-run command makes (slice 262, D3).

A step is a plain function on a store, a config, a clock and a request model. It runs
in process on the local store (``LocalSteps``) or as one door call (``DoorSteps``).
"""
