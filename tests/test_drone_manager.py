"""无人机管理器测试."""

import time
from typing import Any

import pytest

from brain_box.communication.registry import ProtocolRegistry
from brain_box.core.device import DeviceInfo, DeviceProtocol, DeviceStatus
from brain_box.drone.manager import DroneManager


class MockProtocol(DeviceProtocol):
    """测试用模拟协议."""

    def __init__(self) -> None:
        self._devices: list[DeviceInfo] = [
            DeviceInfo(
                device_id="mock_drone_1",
                device_type="quadcopter",
                protocol="mock",
                status=DeviceStatus.ONLINE,
                last_heartbeat=time.time(),
                position={"latitude": 39.9, "longitude": 116.4, "altitude": 100},
            ),
            DeviceInfo(
                device_id="mock_drone_2",
                device_type="hexarotor",
                protocol="mock",
                status=DeviceStatus.ONLINE,
                last_heartbeat=time.time(),
                position={"latitude": 39.91, "longitude": 116.41, "altitude": 150},
            ),
        ]

    @property
    def protocol_name(self) -> str:
        return "mock"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def scan_devices(self) -> list[DeviceInfo]:
        return self._devices

    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "device_id": device_id}

    async def get_device_status(self, device_id: str) -> DeviceInfo | None:
        for d in self._devices:
            if d.device_id == device_id:
                return d
        return None


@pytest.mark.asyncio
async def test_scan_devices() -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry)

    devices = await manager.scan_now()
    assert len(devices) == 2
    assert manager.get_device("mock_drone_1") is not None
    assert manager.get_device("mock_drone_2") is not None


@pytest.mark.asyncio
async def test_get_online_devices() -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry)
    await manager.scan_now()

    online = manager.get_online_devices()
    assert len(online) == 2


@pytest.mark.asyncio
async def test_get_devices_by_type() -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry)
    await manager.scan_now()

    quads = manager.get_devices_by_type("quadcopter")
    assert len(quads) == 1
    assert quads[0].device_id == "mock_drone_1"


@pytest.mark.asyncio
async def test_send_command() -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry)
    await manager.scan_now()

    result = await manager.send_command("mock_drone_1", {"type": "arm"})
    assert result["success"] is True


@pytest.mark.asyncio
async def test_summary() -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry)
    await manager.scan_now()

    summary = manager.get_all_devices_summary()
    assert summary["total"] == 2
    assert summary["online"] == 2
