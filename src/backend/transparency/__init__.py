"""The three transparency signals the demo's surfaces are claims about (issue #23).

Each surface is an assertion, and each assertion needs a signal the backend
emits rather than one the frontend infers:

- the **Grounding panel** (R6) claims *which platform* answered — ``source``
- the **Token meter** (R7) claims what each agent cost — ``tokens``
- the **Presenter alert** (R8) is a message that did not answer anything —
  ``alert``

The payload dataclasses live with every other WebSocket payload in
``models/messages.py``. What lives here is the part with a decision in it: what
may be claimed, and when nothing may be.
"""
