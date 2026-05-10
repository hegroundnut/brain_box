"""设备抽象接口 — 支持多种设备类型和通信协议的统一接口."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DeviceStatus(StrEnum):
    """设备状态枚举."""

    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """设备基本信息."""

    device_id: str
    device_type: str
    protocol: str
    status: DeviceStatus = DeviceStatus.UNKNOWN
    ip_address: str = ""
    port: int = 0
    last_heartbeat: float = 0.0
    position: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_alive(self, timeout: float = 10.0) -> bool:
        """检查设备是否在线."""
        if self.last_heartbeat == 0.0:
            return False
        return (time.time() - self.last_heartbeat) < timeout

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "protocol": self.protocol,
            "status": self.status.value,
            "ip_address": self.ip_address,
            "port": self.port,
            "last_heartbeat": self.last_heartbeat,
            "position": self.position,
            "metadata": self.metadata,
        }


class DeviceProtocol(ABC):
    """
    设备通信协议抽象基类.

    所有设备通信方式（MAVLink, 串口, CAN 等）都实现此接口，
    实现与具体通信方式的解耦。
    """

    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """协议名称标识."""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接."""

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接."""

    @abstractmethod
    async def scan_devices(self) -> list[DeviceInfo]:
        """扫描发现设备."""

    @abstractmethod
    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        """向设备发送控制指令."""

    @abstractmethod
    async def get_device_status(self, device_id: str) -> DeviceInfo | None:
        """获取设备实时状态."""
