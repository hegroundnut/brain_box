"""API 请求/响应数据模型."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DroneQueryRequest(BaseModel):
    """无人机查询请求."""

    device_id: str | None = Field(None, description="指定设备 ID")
    device_type: str | None = Field(None, description="按设备类型过滤")
    protocol: str | None = Field(None, description="按协议过滤")
    status: str | None = Field(None, description="按状态过滤")


class NavigationInstructionRequest(BaseModel):
    """导航指令请求 (边缘服务下发)."""

    instruction_id: str = Field(..., description="指令 ID")
    device_id: str = Field(..., description="目标设备 ID")
    target_position: dict[str, float] = Field(
        ..., description="目标位置 {latitude, longitude, altitude}"
    )
    algorithm: str = Field("default", description="导航算法名称")
    parameters: dict[str, Any] = Field(default_factory=dict, description="算法参数")


class CommandRequest(BaseModel):
    """设备控制指令请求."""

    device_id: str = Field(..., description="目标设备 ID")
    command: dict[str, Any] = Field(..., description="指令内容")


class TrajectoryExecuteRequest(BaseModel):
    """轨迹执行请求."""

    trajectory_id: str = Field(..., description="轨迹 ID")


class TrajectoryHistoryRequest(BaseModel):
    """历史轨迹查询请求."""

    device_id: str | None = Field(None, description="按设备 ID 过滤")
    status: str | None = Field(None, description="按状态过滤: pending/executed/failed")
    limit: int = Field(100, ge=1, le=1000, description="最多返回条数")


class DeviceHistoryRequest(BaseModel):
    """离线设备历史查询请求."""

    device_id: str | None = Field(None, description="按设备 ID 过滤")
    limit: int = Field(200, ge=1, le=1000, description="最多返回条数")


class ApiResponse(BaseModel):
    """统一 API 响应."""

    success: bool = True
    message: str = ""
    data: Any = None
