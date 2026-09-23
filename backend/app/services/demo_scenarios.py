"""Canned 'inject a bug' scenarios for the sandbox demo repo.

These reference specific pre-planted buggy files that need to actually exist
in whichever repo(s) end up in settings.SANDBOX_REPOS — this module only
describes the scenarios, it doesn't create the files itself. See the sandbox
demo repo setup work for the matching demo/*.py implementations.
"""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScenario:
    id: str
    title: str
    body: str


DEMO_SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        id="off-by-one",
        title="Off-by-one error in demo/off_by_one.py",
        body=(
            "`calculate_running_total()` in `demo/off_by_one.py` drops the last item "
            "in the input list — looks like an off-by-one in the loop range.\n\n"
            "Reproduced with `calculate_running_total([1, 2, 3])` returning `3` "
            "instead of the expected `6`."
        ),
    ),
    DemoScenario(
        id="null-deref",
        title="Unhandled None causes a crash in demo/null_deref.py",
        body=(
            "`get_user_display_name()` in `demo/null_deref.py` raises "
            "`AttributeError: 'NoneType' object has no attribute 'strip'` whenever a "
            "user record has no `nickname` set."
        ),
    ),
    DemoScenario(
        id="bare-except",
        title="Silent failure from a bare except in demo/bare_except.py",
        body=(
            "`parse_config_value()` in `demo/bare_except.py` swallows every exception "
            "and just returns `None`, so a malformed config value fails silently "
            "instead of surfacing the real parsing error."
        ),
    ),
    DemoScenario(
        id="type-coercion",
        title="Type coercion bug in demo/type_coercion.py",
        body=(
            "`apply_discount()` in `demo/type_coercion.py` treats the discount "
            "percentage as a string and concatenates instead of computing a "
            "percentage — `apply_discount(100, '10')` returns `'10010'` instead of `90`."
        ),
    ),
]

_SCENARIOS_BY_ID = {s.id: s for s in DEMO_SCENARIOS}


def get_scenario(scenario_id: str | None = None) -> DemoScenario:
    """Returns a specific scenario by id, or picks one at random if none given."""
    if scenario_id is None:
        return random.choice(DEMO_SCENARIOS)
    try:
        return _SCENARIOS_BY_ID[scenario_id]
    except KeyError:
        raise ValueError(f"Unknown demo scenario id: {scenario_id}") from None
