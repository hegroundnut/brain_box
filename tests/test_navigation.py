"""导航模块测试."""

import pytest

from brain_box.navigation.registry import AlgorithmRegistry
from brain_box.navigation.simple_nav import SimpleNavigationAlgorithm


@pytest.mark.asyncio
async def test_simple_navigation() -> None:
    algo = SimpleNavigationAlgorithm()
    trajectory = await algo.generate_trajectory(
        device_id="drone_1",
        current_position={"latitude": 39.9, "longitude": 116.4, "altitude": 100},
        target_position={"latitude": 39.91, "longitude": 116.41, "altitude": 100},
        parameters={"step_count": 5},
    )
    assert trajectory.device_id == "drone_1"
    assert len(trajectory.waypoints) == 6
    assert trajectory.algorithm_name == "simple_linear"
    assert trajectory.total_distance > 0
    assert trajectory.waypoints[0].latitude == pytest.approx(39.9)
    assert trajectory.waypoints[-1].latitude == pytest.approx(39.91)


def test_algorithm_registry() -> None:
    registry = AlgorithmRegistry()
    algo = SimpleNavigationAlgorithm()
    registry.register(algo)
    assert "simple_linear" in registry.list_algorithms()
    assert registry.get("simple_linear") is algo
    assert registry.get_default() is algo


def test_algorithm_registry_unregister() -> None:
    registry = AlgorithmRegistry()
    algo = SimpleNavigationAlgorithm()
    registry.register(algo)
    registry.unregister("simple_linear")
    assert "simple_linear" not in registry.list_algorithms()
    assert registry.get("simple_linear") is None
