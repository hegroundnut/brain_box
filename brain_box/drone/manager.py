"""无人机管理器 — 统一管理通过各协议发现的无人机设备."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from brain_box.communication.registry import ProtocolRegistry
from brain_box.core.device import DeviceInfo, DeviceStatus

logger = logging.getLogger("brain_box.drone.manager")


class DroneManager:
    """
    无人机管理器.

    负责通过协议注册中心统一扫描、跟踪、查询无人机设备。
    与具体通信协议解耦，只依赖抽象接口。
    """

    def __init__(self, protocol_registry: ProtocolRegistry, scan_interval: float = 3.0) -> None:
        self._registry = protocol_registry
        self._scan_interval = scan_interval
        self._devices: dict[str, DeviceInfo] = {}
        self._running = False
        self._scan_task: asyncio.Task[None] | None = None
        self._status_callbacks: list[Any] = []

    @property
    def devices(self) -> dict[str, DeviceInfo]:
        return dict(self._devices)

    def on_status_change(self, callback: Any) -> None:
        """注册设备状态变化回调."""
        self._status_callbacks.append(callback)

    async def start(self) -> None:
        """启动无人机扫描."""
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info("无人机管理器已启动，扫描间隔: %.1fs", self._scan_interval)

    async def stop(self) -> None:
        """停止扫描."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scan_task
        logger.info("无人机管理器已停止")

    async def scan_now(self) -> list[DeviceInfo]:
        """立即执行一次扫描."""
        all_devices: list[DeviceInfo] = []
        for protocol_name in self._registry.list_protocols():
            proto = self._registry.get(protocol_name)
            if proto is None:
                continue
            try:
                devices = await proto.scan_devices()
                for device in devices:
                    old = self._devices.get(device.device_id)
                    self._devices[device.device_id] = device
                    if old and old.status != device.status:
                        await self._notify_status_change(device)
                all_devices.extend(devices)
            except Exception:
                logger.exception("通过协议 '%s' 扫描失败", protocol_name)
        return all_devices

    def get_device(self, device_id: str) -> DeviceInfo | None:
        """查询单个设备."""
        return self._devices.get(device_id)

    def get_online_devices(self) -> list[DeviceInfo]:
        """获取所有在线设备."""
        return [d for d in self._devices.values() if d.status == DeviceStatus.ONLINE]

    def get_devices_by_type(self, device_type: str) -> list[DeviceInfo]:
        """按类型查询设备."""
        return [d for d in self._devices.values() if d.device_type == device_type]

    def get_devices_by_protocol(self, protocol: str) -> list[DeviceInfo]:
        """按协议查询设备."""
        return [d for d in self._devices.values() if d.protocol == protocol]

    def get_all_devices_summary(self) -> dict[str, Any]:
        """获取所有设备汇总信息."""
        devices_list = [d.to_dict() for d in self._devices.values()]
        return {
            "total": len(devices_list),
            "online": sum(1 for d in self._devices.values() if d.status == DeviceStatus.ONLINE),
            "offline": sum(1 for d in self._devices.values() if d.status == DeviceStatus.OFFLINE),
            "devices": devices_list,
        }

    async def send_command(
        self, device_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        """向指定设备发送指令."""
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 不存在"}

        proto = self._registry.get(device.protocol)
        if not proto:
            return {"success": False, "error": f"协议 {device.protocol} 未注册"}

        return await proto.send_command(device_id, command)

    async def _scan_loop(self) -> None:
        """周期性扫描无人机."""
        while self._running:
            try:
                await self.scan_now()
            except Exception:
                logger.exception("扫描循环异常")
            await asyncio.sleep(self._scan_interval)

    async def _notify_status_change(self, device: DeviceInfo) -> None:
        """通知设备状态变化."""
        for cb in self._status_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(device)
                else:
                    cb(device)
            except Exception:
                logger.exception("状态变化回调异常")
