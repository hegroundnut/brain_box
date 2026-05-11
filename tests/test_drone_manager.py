"""无人机管理器测试."""

import time
from typing import Any

import pytest

from brain_box.communication.registry import ProtocolRegistry
from brain_box.core.device import DeviceInfo, DeviceProtocol, DeviceStatus
from brain_box.drone.manager import DroneManager
from brain_box.storage.database import Database


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


@pytest.fixture
def db(tmp_path: Any) -> Database:
    database = Database(db_path=tmp_path / "test.db")
    database.open()
    yield database
    database.close()


@pytest.mark.asyncio
async def test_scan_devices(db: Database) -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry, database=db)

    devices = await manager.scan_now()
    assert len(devices) == 2
    assert manager.get_device("mock_drone_1") is not None
    assert manager.get_device("mock_drone_2") is not None


@pytest.mark.asyncio
async def test_get_online_devices(db: Database) -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry, database=db)
    await manager.scan_now()

    online = manager.get_online_devices()
    assert len(online) == 2


@pytest.mark.asyncio
async def test_get_devices_by_type(db: Database) -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry, database=db)
    await manager.scan_now()

    quads = manager.get_devices_by_type("quadcopter")
    assert len(quads) == 1
    assert quads[0].device_id == "mock_drone_1"


@pytest.mark.asyncio
async def test_send_command(db: Database) -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry, database=db)
    await manager.scan_now()

    result = await manager.send_command("mock_drone_1", {"type": "arm"})
    assert result["success"] is True


@pytest.mark.asyncio
async def test_summary(db: Database) -> None:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())
    manager = DroneManager(registry, database=db)
    await manager.scan_now()

    summary = manager.get_all_devices_summary()
    assert summary["total"] == 2
    assert summary["online"] == 2


@pytest.mark.asyncio
async def test_stale_device_evicted_to_db(db: Database) -> None:
    """超时离线设备应被驱逐到数据库并从内存移除."""
    registry = ProtocolRegistry()
    proto = MockProtocol()
    # 将 mock_drone_2 的心跳时间设置为很久以前，模拟超时
    proto._devices[1].last_heartbeat = time.time() - 200
    registry.register(proto)

    # 驱逐超时设置为 60 秒
    manager = DroneManager(registry, database=db, evict_timeout=60.0)
    await manager.scan_now()

    # mock_drone_2 应已被驱逐出内存
    assert manager.get_device("mock_drone_2") is None
    # mock_drone_1 应仍在内存中
    assert manager.get_device("mock_drone_1") is not None

    # 数据库中应有 mock_drone_2 的历史记录
    history = db.list_device_history(device_id="mock_drone_2")
    assert len(history) == 1
    assert history[0]["device_id"] == "mock_drone_2"
