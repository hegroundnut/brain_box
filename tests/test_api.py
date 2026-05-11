"""API 接口测试."""

import time
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from brain_box.api.routes import create_api_router
from brain_box.communication.registry import ProtocolRegistry
from brain_box.config.settings import EdgeServerConfig
from brain_box.core.device import DeviceInfo, DeviceProtocol, DeviceStatus
from brain_box.drone.manager import DroneManager
from brain_box.edge.client import EdgeClient
from brain_box.edge.reporter import EdgeReporter
from brain_box.navigation.registry import AlgorithmRegistry
from brain_box.navigation.service import NavigationService
from brain_box.navigation.simple_nav import SimpleNavigationAlgorithm
from brain_box.storage.database import Database

HTTP_OK = 200


class MockProtocol(DeviceProtocol):
    @property
    def protocol_name(self) -> str:
        return "mock"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def scan_devices(self) -> list[DeviceInfo]:
        return [
            DeviceInfo(
                device_id="test_drone_1",
                device_type="quadcopter",
                protocol="mock",
                status=DeviceStatus.ONLINE,
                last_heartbeat=time.time(),
                position={"latitude": 39.9, "longitude": 116.4, "altitude": 100},
            )
        ]

    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        return {"success": True}

    async def get_device_status(self, device_id: str) -> DeviceInfo | None:
        return None


@pytest.fixture
def db(tmp_path: Any) -> Database:
    """使用临时路径创建测试数据库."""
    database = Database(db_path=tmp_path / "test.db")
    database.open()
    yield database
    database.close()


@pytest.fixture
def app(db: Database) -> FastAPI:
    registry = ProtocolRegistry()
    registry.register(MockProtocol())

    algo_registry = AlgorithmRegistry()
    algo_registry.register(SimpleNavigationAlgorithm())

    drone_manager = DroneManager(registry, database=db)
    edge_client = EdgeClient(EdgeServerConfig())
    edge_reporter = EdgeReporter(edge_client, drone_manager)
    nav_service = NavigationService(algo_registry, drone_manager, registry, database=db)

    test_app = FastAPI()
    router = create_api_router(drone_manager, nav_service, edge_reporter, database=db)
    test_app.include_router(router)
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_scan_drones(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/drones/scan")
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_query_drones(client: AsyncClient) -> None:
    await client.post("/api/v1/drones/scan")
    resp = await client.post("/api/v1/drones/query", json={"device_id": "test_drone_1"})
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["data"]["device_id"] == "test_drone_1"


@pytest.mark.asyncio
async def test_query_nonexistent_drone(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/drones/query", json={"device_id": "nope"})
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_drones_summary(client: AsyncClient) -> None:
    await client.post("/api/v1/drones/scan")
    resp = await client.post("/api/v1/drones/summary")
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_navigation_instruction(client: AsyncClient) -> None:
    await client.post("/api/v1/drones/scan")
    resp = await client.post(
        "/api/v1/navigation/instruction",
        json={
            "instruction_id": "nav_001",
            "device_id": "test_drone_1",
            "target_position": {"latitude": 39.91, "longitude": 116.41, "altitude": 100},
            "algorithm": "simple_linear",
        },
    )
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["success"] is True
    assert "waypoints" in data["data"]


@pytest.mark.asyncio
async def test_trajectory_persisted_in_db(client: AsyncClient, db: Database) -> None:
    """生成轨迹后应在数据库中存储为 pending 状态."""
    await client.post("/api/v1/drones/scan")
    resp = await client.post(
        "/api/v1/navigation/instruction",
        json={
            "instruction_id": "nav_db_001",
            "device_id": "test_drone_1",
            "target_position": {"latitude": 39.91, "longitude": 116.41, "altitude": 100},
        },
    )
    assert resp.status_code == HTTP_OK
    trajectory_id = resp.json()["data"]["trajectory_id"]

    record = db.get_trajectory(trajectory_id)
    assert record is not None
    assert record["status"] == "pending"
    assert record["device_id"] == "test_drone_1"


@pytest.mark.asyncio
async def test_trajectory_history_api(client: AsyncClient) -> None:
    """历史轨迹查询接口应返回已存储的轨迹."""
    await client.post("/api/v1/drones/scan")
    await client.post(
        "/api/v1/navigation/instruction",
        json={
            "instruction_id": "nav_hist_001",
            "device_id": "test_drone_1",
            "target_position": {"latitude": 39.92, "longitude": 116.42, "altitude": 120},
        },
    )
    resp = await client.post(
        "/api/v1/navigation/trajectories/history",
        json={"device_id": "test_drone_1"},
    )
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_list_algorithms(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/navigation/algorithms")
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert "simple_linear" in data["data"]


@pytest.mark.asyncio
async def test_system_status(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/system/status")
    assert resp.status_code == HTTP_OK
    data = resp.json()
    assert data["data"]["status"] == "running"
