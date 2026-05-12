"""无人机管理器 — 统一管理通过各协议发现的无人机设备."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from models.device import DeviceInfo, DeviceStatus

from core.protocol_registry import ProtocolRegistry

logger = logging.getLogger("brainBox.core.drone_manager")

_DEVICE_EVICT_TIMEOUT: float = 60.0


class DroneManager:
    """无人机管理器."""

    def __init__(
        self,
        protocol_registry: ProtocolRegistry,
        scan_interval: float = 3.0,
        evict_timeout: float = _DEVICE_EVICT_TIMEOUT,
    ) -> None:
        self._registry = protocol_registry
        self._scan_interval = scan_interval
        self._evict_timeout = evict_timeout
        self._devices: dict[str, DeviceInfo] = {}
        self._running = False
        self._scan_task: asyncio.Task[None] | None = None

    @property
    def devices(self) -> dict[str, DeviceInfo]:
        return dict(self._devices)

    async def start(self) -> None:
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info("无人机管理器已启动，扫描间隔: %.1fs", self._scan_interval)

    async def stop(self) -> None:
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scan_task
        logger.info("无人机管理器已停止")

    async def scan_now(self) -> list[DeviceInfo]:
        all_devices: list[DeviceInfo] = []
        for protocol_name in self._registry.list_protocols():
            proto = self._registry.get(protocol_name)
            if proto is None:
                continue
            try:
                devices = await proto.scan_devices()
                for device in devices:
                    self._devices[device.device_id] = device
                all_devices.extend(devices)
            except Exception:
                logger.exception("通过协议 '%s' 扫描失败", protocol_name)
        self._evict_stale_devices()
        return all_devices

    def get_device(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)

    def get_online_devices(self) -> list[DeviceInfo]:
        return [d for d in self._devices.values() if d.status == DeviceStatus.ONLINE]

    def get_all_devices_summary(self) -> dict[str, Any]:
        devices_list = [d.to_dict() for d in self._devices.values()]
        return {
            "total": len(devices_list),
            "online": sum(1 for d in self._devices.values() if d.status == DeviceStatus.ONLINE),
            "offline": sum(1 for d in self._devices.values() if d.status == DeviceStatus.OFFLINE),
            "devices": devices_list,
        }

    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 不存在"}
        proto = self._registry.get(device.protocol)
        if not proto:
            return {"success": False, "error": f"协议 {device.protocol} 未注册"}
        return await proto.send_command(device_id, command)

    def _evict_stale_devices(self) -> None:
        now = time.time()
        stale = [
            did for did, d in self._devices.items()
            if d.last_heartbeat > 0 and (now - d.last_heartbeat) > self._evict_timeout
        ]
        for did in stale:
            dev = self._devices.pop(did)
            logger.info("驱逐离线设备: %s (离线 %.0fs)", did, now - dev.last_heartbeat)

    async def _scan_loop(self) -> None:
        while self._running:
            await self.scan_now()
            await asyncio.sleep(self._scan_interval)
