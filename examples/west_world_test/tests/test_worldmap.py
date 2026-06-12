"""Tests for the worldmap loader and validators."""
from pathlib import Path

import pytest

from examples.west_world_test.worldmap.loader import Location, WorldMap, load_world_map

LOCATIONS_PATH = str(Path(__file__).parents[1] / "data" / "map" / "locations.yaml")


@pytest.fixture()
def world() -> WorldMap:
    return load_world_map(LOCATIONS_PATH)


def test_loads_all_locations(world):
    assert len(world.locations) >= 25
    saloon = world.get("sweetwater_saloon")
    assert isinstance(saloon, Location)
    assert saloon.name == "甜水镇酒馆"
    assert saloon.active is True


def test_ids_unique_and_adjacency_symmetric(world):
    ids = [loc.id for loc in world.locations.values()]
    assert len(ids) == len(set(ids))
    for loc in world.locations.values():
        for nb in loc.adjacency:
            assert nb in world.locations, f"{loc.id} 邻接未知地点 {nb}"
            assert loc.id in world.get(nb).adjacency, f"{loc.id}->{nb} 非双向"


def test_active_subgraph_connected(world):
    active = world.active_ids()
    assert "sweetwater_saloon" in active and "abernathy_ranch" in active
    start = next(iter(active))
    seen, frontier = {start}, [start]
    while frontier:
        cur = frontier.pop()
        for nb in world.get(cur).adjacency:
            if nb in active and nb not in seen:
                seen.add(nb)
                frontier.append(nb)
    assert seen == active


def test_can_move_rules(world):
    assert world.can_move("sweetwater_saloon", "sweetwater_plaza") == (True, "")
    ok, reason = world.can_move("sweetwater_saloon", "abernathy_ranch")
    assert ok is False and "相邻" in reason
    ok, reason = world.can_move("sweetwater", "wilderness")
    assert ok is False and reason


def test_hidden_objects_and_visible_objects(world):
    saloon = world.get("sweetwater_saloon")
    visible = saloon.visible_objects()
    assert all(not o.get("hidden") for o in visible)
    assert any(o.get("hidden") for o in saloon.objects)
