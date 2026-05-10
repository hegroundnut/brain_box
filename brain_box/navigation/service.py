"""导航服务 — 协调导航指令处理、轨迹生成和设备控制."""

from __future__ import annotations

import logging
from typing import Any

from brain_box.communication.mavlink_comm import MAVLinkProtocol
from brain_box.communication.registry import ProtocolRegistry
from brain_box.core.algorithm import NavigationInstruction, NavigationTrajectory
from brain_box.drone.manager import DroneManager
from brain_box.navigation.registry import AlgorithmRegistry

logger = logging.getLogger("brain_box.navigation.service")


class NavigationService:
    """
    导航服务.

    负责：
    1. 接收边缘控制服务下发的导航指令
    2. 调用导航算法生成轨迹
    3. 通过设备管理器控制无人机执行任务
    """

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

    async def process_instruction(
        self, instruction: NavigationInstruction
    ) -> NavigationTrajectory:
        """处理导航指令，生成轨迹."""
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
            trajectory.trajectory_id,
            instruction.device_id,
            trajectory.algorithm_name,
            len(trajectory.waypoints),
        )
        return trajectory

    async def execute_trajectory(
        self, trajectory_id: str
    ) -> dict[str, Any]:
        """执行导航轨迹 — 向无人机发送航点."""
        trajectory = self._active_trajectories.get(trajectory_id)
        if not trajectory:
            return {"success": False, "error": f"轨迹 {trajectory_id} 未找到"}

        proto = self._protocol_registry.get("mavlink")
        if isinstance(proto, MAVLinkProtocol):
            waypoints_data = [wp.to_dict() for wp in trajectory.waypoints]
            result = await proto.send_waypoints(trajectory.device_id, waypoints_data)
            logger.info(
                "轨迹 %s 已发送到设备 %s: %s",
                trajectory_id, trajectory.device_id, result
            )
            return result

        result = await self._drone_manager.send_command(
            trajectory.device_id,
            {"type": "mission", "waypoints": [wp.to_dict() for wp in trajectory.waypoints]},
        )
        return result

    def get_active_trajectories(self) -> dict[str, dict[str, Any]]:
        """获取所有活动轨迹."""
        return {
            tid: t.to_dict() for tid, t in self._active_trajectories.items()
        }

    def get_trajectory(self, trajectory_id: str) -> NavigationTrajectory | None:
        """获取指定轨迹."""
        return self._active_trajectories.get(trajectory_id)

    def list_algorithms(self) -> list[str]:
        """列出可用导航算法."""
        return self._algorithms.list_algorithms()

    def list_protocols(self) -> list[str]:
        """列出已注册通信协议."""
        return self._protocol_registry.list_protocols()
