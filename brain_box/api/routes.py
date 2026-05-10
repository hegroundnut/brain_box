"""API 路由 — 所有接口使用 POST 方法."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from brain_box.api.models import (
    ApiResponse,
    CommandRequest,
    DroneQueryRequest,
    NavigationInstructionRequest,
    TrajectoryExecuteRequest,
)
from brain_box.core.algorithm import NavigationInstruction
from brain_box.drone.manager import DroneManager
from brain_box.edge.reporter import EdgeReporter
from brain_box.navigation.service import NavigationService

logger = logging.getLogger("brain_box.api")


def _register_drone_routes(
    router: APIRouter,
    drone_manager: DroneManager,
) -> None:
    """注册无人机相关路由."""

    @router.post("/drones/query", response_model=ApiResponse)
    async def query_drones(req: DroneQueryRequest) -> ApiResponse:
        """查询无人机信息 (供边缘服务器等使用)."""
        if req.device_id:
            device = drone_manager.get_device(req.device_id)
            if device:
                return ApiResponse(data=device.to_dict())
            return ApiResponse(success=False, message=f"设备 {req.device_id} 未找到")

        devices = list(drone_manager.devices.values())
        if req.device_type:
            devices = [d for d in devices if d.device_type == req.device_type]
        if req.protocol:
            devices = [d for d in devices if d.protocol == req.protocol]
        if req.status:
            devices = [d for d in devices if d.status.value == req.status]

        return ApiResponse(data=[d.to_dict() for d in devices])

    @router.post("/drones/scan", response_model=ApiResponse)
    async def scan_drones() -> ApiResponse:
        """立即扫描网络中的无人机."""
        devices = await drone_manager.scan_now()
        return ApiResponse(
            message=f"扫描完成，发现 {len(devices)} 台设备",
            data=[d.to_dict() for d in devices],
        )

    @router.post("/drones/summary", response_model=ApiResponse)
    async def drones_summary() -> ApiResponse:
        """获取无人机汇总信息."""
        summary = drone_manager.get_all_devices_summary()
        return ApiResponse(data=summary)

    @router.post("/drones/command", response_model=ApiResponse)
    async def send_command(req: CommandRequest) -> ApiResponse:
        """向指定无人机发送控制指令."""
        result = await drone_manager.send_command(req.device_id, req.command)
        success = result.get("success", False)
        return ApiResponse(
            success=success,
            message=result.get("error", "") if not success else "指令已发送",
            data=result,
        )


def _register_navigation_routes(
    router: APIRouter,
    navigation_service: NavigationService,
    edge_reporter: EdgeReporter,
) -> None:
    """注册导航相关路由."""

    @router.post("/navigation/instruction", response_model=ApiResponse)
    async def receive_navigation_instruction(
        req: NavigationInstructionRequest,
    ) -> ApiResponse:
        """接收边缘控制服务下发的导航指令，生成导航轨迹."""
        instruction = NavigationInstruction(
            instruction_id=req.instruction_id,
            device_id=req.device_id,
            target_position=req.target_position,
            algorithm=req.algorithm,
            parameters=req.parameters,
        )
        try:
            trajectory = await navigation_service.process_instruction(instruction)
        except ValueError as e:
            return ApiResponse(success=False, message=str(e))

        trajectory_data = trajectory.to_dict()
        await edge_reporter.report_trajectory(trajectory_data)

        return ApiResponse(
            message="导航轨迹已生成并上报",
            data=trajectory_data,
        )

    @router.post("/navigation/execute", response_model=ApiResponse)
    async def execute_trajectory(req: TrajectoryExecuteRequest) -> ApiResponse:
        """执行导航轨迹 — 向无人机发送航点."""
        result = await navigation_service.execute_trajectory(req.trajectory_id)
        success = result.get("success", False)
        return ApiResponse(
            success=success,
            message="轨迹执行中" if success else result.get("error", ""),
            data=result,
        )

    @router.post("/navigation/trajectories", response_model=ApiResponse)
    async def list_trajectories() -> ApiResponse:
        """列出所有活动导航轨迹."""
        trajectories = navigation_service.get_active_trajectories()
        return ApiResponse(data=trajectories)

    @router.post("/navigation/algorithms", response_model=ApiResponse)
    async def list_algorithms() -> ApiResponse:
        """列出可用导航算法."""
        algorithms = navigation_service.list_algorithms()
        return ApiResponse(data=algorithms)


def _register_system_routes(
    router: APIRouter,
    drone_manager: DroneManager,
    navigation_service: NavigationService,
) -> None:
    """注册系统相关路由."""

    @router.post("/system/status", response_model=ApiResponse)
    async def system_status() -> ApiResponse:
        """获取系统状态."""
        summary = drone_manager.get_all_devices_summary()
        algorithms = navigation_service.list_algorithms()
        data: dict[str, Any] = {
            "status": "running",
            "drones": summary,
            "algorithms": algorithms,
        }
        return ApiResponse(data=data)

    @router.post("/system/protocols", response_model=ApiResponse)
    async def list_protocols() -> ApiResponse:
        """列出已注册通信协议."""
        protocols = navigation_service.list_protocols()
        return ApiResponse(data=protocols)


def create_api_router(
    drone_manager: DroneManager,
    navigation_service: NavigationService,
    edge_reporter: EdgeReporter,
) -> APIRouter:
    """创建 API 路由，注入依赖."""
    router = APIRouter(prefix="/api/v1")
    _register_drone_routes(router, drone_manager)
    _register_navigation_routes(router, navigation_service, edge_reporter)
    _register_system_routes(router, drone_manager, navigation_service)
    return router
