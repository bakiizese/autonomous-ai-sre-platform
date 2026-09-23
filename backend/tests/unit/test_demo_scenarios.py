import pytest

from app.services.demo_scenarios import DEMO_SCENARIOS, get_scenario


def test_get_scenario_by_id():
    scenario = get_scenario("off-by-one")
    assert scenario.id == "off-by-one"


def test_get_scenario_unknown_id_raises():
    with pytest.raises(ValueError, match="Unknown demo scenario"):
        get_scenario("does-not-exist")


def test_get_scenario_random_when_no_id():
    scenario = get_scenario()
    assert scenario in DEMO_SCENARIOS


def test_scenario_ids_are_unique():
    ids = [s.id for s in DEMO_SCENARIOS]
    assert len(ids) == len(set(ids))
