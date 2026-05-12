"""导航服务 — 协调导航指令处理、轨迹生成和设备控制."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from models.algorithm import (
    NavigationAlgorithm,
    NavigationInstruction,
    NavigationTrajectory,
    Waypoint,
)

from core.drone_manager import DroneManager
from core.mavlink_comm import MAVLinkProtocol
from core.protocol_registry import ProtocolRegistry

logger = logging.getLogger("brainBox.core.navigation_service")


class AlgorithmRegistry:
    """导航算法注册中心."""

    def __init__(self) -> None:
        self._algorithms: dict[str, NavigationAlgorithm] = {}

    def register(self, algorithm: NavigationAlgorithm) -> None:
        self._algorithms[algorithm.algorithm_name] = algorithm
        logger.info("已注册导航算法: %s", algorithm.algorithm_name)

    def get(self, name: str) -> NavigationAlgorithm | None:
        return self._algorithms.get(name)

    def get_default(self) -> NavigationAlgorithm | None:
        if self._algorithms:
            return next(iter(self._algorithms.values()))
        return None

    def list_algorithms(self) -> list[str]:
        return list(self._algorithms.keys())


class SimpleNavigationAlgorithm(NavigationAlgorithm):
    """简单直线导航算法."""

    @property
    def algorithm_name(self) -> str:
        return "simple_linear"

    async def generate_trajectory(
        self,
        device_id: str,
        current_position: dict[str, float],
        target_position: dict[str, float],
        parameters: dict[str, Any] | None = None,
    ) -> NavigationTrajectory:
        params = parameters or {}
        step_count = int(params.get("step_count", 5))
        speed = float(params.get("speed", 5.0))

        waypoints: list[Waypoint] = []
        cur_lat = current_position.get("latitude", 0.0)
        cur_lon = current_position.get("longitude", 0.0)
        cur_alt = current_position.get("altitude", 0.0)
        tgt_lat = target_position.get("latitude", 0.0)
        tgt_lon = target_position.get("longitude", 0.0)
        tgt_alt = target_position.get("altitude", 0.0)
        for i in range(step_count + 1):
            ratio = i / step_count
            waypoints.append(Waypoint(
                latitude=cur_lat + ratio * (tgt_lat - cur_lat),
                longitude=cur_lon + ratio * (tgt_lon - cur_lon),
                altitude=cur_alt + ratio * (tgt_alt - cur_alt),
                speed=speed,
            ))

        total_distance = _calc_distance(current_position, target_position)
        estimated_time = total_distance / speed if speed > 0 else 0

        return NavigationTrajectory(
            trajectory_id=str(uuid.uuid4()),
            device_id=device_id,
            waypoints=waypoints,
            algorithm_name=self.algorithm_name,
            total_distance=total_distance,
            estimated_time=estimated_time,
        )


def _calc_distance(pos1: dict[str, float], pos2: dict[str, float]) -> float:
    """简单距离估算（米）."""
    import math  # noqa: PLC0415
    lat1, lon1 = pos1.get("latitude", 0), pos1.get("longitude", 0)
    lat2, lon2 = pos2.get("latitude", 0), pos2.get("longitude", 0)
    alt1, alt2 = pos1.get("altitude", 0), pos2.get("altitude", 0)
    dlat = (lat2 - lat1) * 111320
    dlon = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    dalt = alt2 - alt1
    return math.sqrt(dlat ** 2 + dlon ** 2 + dalt ** 2)


class NavigationService:
    """导航服务."""

    def __init__(
        self,
        algorithm_registry: AlgorithmRegistry,
        drone_manager: DroneManager,
        protocol_registry: ProtocolRegistry,
    ) -> None:
        self._algorithms = algorithm_registry
        self._drone_manager = drone_manager
        self._protocol_registry = protocol_registry
        self._active_trajectories: dict[str, NavigationTrajectory] = {}

    async def process_instruction(self, instruction: NavigationInstruction) -> NavigationTrajectory:
        algo_name = instruction.algorithm
        algo = self._algorithms.get(algo_name)
        if not algo:
            algo = self._algorithms.get_default()
        if not algo:
            raise ValueError(f"没有可用的导航算法: {algo_name}")

        device = self._drone_manager.get_device(instruction.device_id)
        current_position: dict[str, float] = (
            device.position if device
            else {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}
        )

        trajectory = await algo.generate_trajectory(
            device_id=instruction.device_id,
            current_position=current_position,
            target_position=instruction.target_position,
            parameters=instruction.parameters,
        )

        self._active_trajectories[trajectory.trajectory_id] = trajectory
        logger.info(
            "导航轨迹已生成: %s (设备=%s, 算法=%s, 航点数=%d)",
            trajectory.trajectory_id, instruction.device_id,
            trajectory.algorithm_name, len(trajectory.waypoints),
        )
        return trajectory

    async def execute_trajectory(self, trajectory_id: str) -> dict[str, Any]:
        trajectory = self._active_trajectories.get(trajectory_id)
        if not trajectory:
            return {"success": False, "error": f"轨迹 {trajectory_id} 未找到"}

        try:
            proto = self._protocol_registry.get("mavlink")
            if isinstance(proto, MAVLinkProtocol):
                waypoints_data = [wp.to_dict() for wp in trajectory.waypoints]
                result = await proto.send_waypoints(trajectory.device_id, waypoints_data)
            else:
                result = await self._drone_manager.send_command(
                    trajectory.device_id,
                    {"type": "mission", "waypoints": [wp.to_dict() for wp in trajectory.waypoints]},
                )
        except Exception:
            logger.exception("轨迹 %s 执行异常", trajectory_id)
            result = {"success": False, "error": "执行异常"}

        self._active_trajectories.pop(trajectory_id, None)
        return result

    def get_active_trajectories(self) -> dict[str, dict[str, Any]]:
        return {tid: t.to_dict() for tid, t in self._active_trajectories.items()}

    def list_algorithms(self) -> list[str]:
        return self._algorithms.list_algorithms()

    def list_protocols(self) -> list[str]:
        return self._protocol_registry.list_protocols()
