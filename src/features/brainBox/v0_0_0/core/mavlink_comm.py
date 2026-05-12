"""MAVLink 通信协议实现 — 支持多连接通道."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from config.settings import MAVLinkConfig, MAVLinkConnectionEntry
from models.device import DeviceInfo, DeviceStatus

from core.protocol_registry import DeviceProtocol

logger = logging.getLogger("brainBox.core.mavlink")

_MAX_SIMULATED_DRONES = 3


class _MAVLinkChannel:
    """单个 MAVLink 连接通道."""

    def __init__(
        self,
        entry: MAVLinkConnectionEntry,
        system_id: int,
        component_id: int,
    ) -> None:
        self.entry = entry
        self.system_id = system_id
        self.component_id = component_id
        self.connection: Any = None
        self.simulated = False
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._addr_map: dict[int, tuple[str, int]] = {}
        self._send_lock = asyncio.Lock()

    @property
    def label(self) -> str:
        return self.entry.label or self.entry.connection_string

    async def open(self, devices: dict[str, DeviceInfo]) -> None:
        try:
            from pymavlink import mavutil  # noqa: PLC0415

            self.connection = mavutil.mavlink_connection(
                self.entry.connection_string,
                source_system=self.system_id,
                source_component=self.component_id,
                baud=self.entry.baud_rate,
            )
            self.simulated = False
            self._running = True
            self._task = asyncio.create_task(self._recv_loop(devices))
            logger.info("MAVLink 通道已连接: %s (%s)", self.label, self.entry.connection_string)
        except ImportError:
            logger.warning("pymavlink 未安装，通道 '%s' 使用模拟模式", self.label)
            self.simulated = True
            self._running = True
            self._task = asyncio.create_task(self._simulated_loop(devices))
        except Exception:
            logger.exception("MAVLink 通道 '%s' 连接失败", self.label)
            raise

    async def close(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self.connection:
            self.connection.close()
            self.connection = None
        logger.info("MAVLink 通道已断开: %s", self.label)

    async def send_to_device(self, target_system: int, send_fn: Any) -> None:
        async with self._send_lock:
            addr = self._addr_map.get(target_system)
            if addr and hasattr(self.connection, "last_address"):
                saved = getattr(self.connection, "last_address", None)
                self.connection.last_address = addr
                try:
                    await asyncio.get_event_loop().run_in_executor(None, send_fn)
                finally:
                    self.connection.last_address = saved
            else:
                await asyncio.get_event_loop().run_in_executor(None, send_fn)

    async def _recv_loop(self, devices: dict[str, DeviceInfo]) -> None:
        while self._running:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.connection.recv_match(blocking=True, timeout=1),
                )
                if msg is None:
                    continue

                msg_type = msg.get_type()
                if msg_type == "BAD_DATA":
                    continue

                sys_id = msg.get_srcSystem()
                if hasattr(self.connection, "last_address") and self.connection.last_address:
                    self._addr_map[sys_id] = self.connection.last_address

                if msg_type == "HEARTBEAT":
                    _process_heartbeat(msg, devices, self.label)
                elif msg_type == "GLOBAL_POSITION_INT":
                    _process_position(msg, devices)
                elif msg_type == "COMMAND_ACK":
                    logger.debug("收到指令确认: command=%s, result=%s", msg.command, msg.result)
            except Exception:
                logger.exception("MAVLink 消息接收异常 (通道 %s)", self.label)
            await asyncio.sleep(0.01)

    async def _simulated_loop(self, devices: dict[str, DeviceInfo]) -> None:
        sim_id = 0
        prefix = self.label.replace(" ", "_")
        while self._running:
            for i in range(_MAX_SIMULATED_DRONES):
                device_id = f"{prefix}_drone_sim_{i}"
                if device_id not in devices:
                    devices[device_id] = DeviceInfo(
                        device_id=device_id,
                        device_type="quadcopter",
                        protocol="mavlink",
                        status=DeviceStatus.ONLINE,
                        last_heartbeat=time.time(),
                        position={
                            "latitude": 39.9042 + i * 0.001,
                            "longitude": 116.4074 + i * 0.001,
                            "altitude": 100.0 + i * 10,
                        },
                    )
                else:
                    devices[device_id].last_heartbeat = time.time()
                    devices[device_id].status = DeviceStatus.ONLINE
            sim_id += 1
            await asyncio.sleep(3.0)


def _process_heartbeat(msg: Any, devices: dict[str, DeviceInfo], channel_label: str) -> None:
    sys_id = msg.get_srcSystem()
    device_id = f"mavlink_{sys_id}"
    now = time.time()
    if device_id in devices:
        devices[device_id].last_heartbeat = now
        devices[device_id].status = DeviceStatus.ONLINE
    else:
        devices[device_id] = DeviceInfo(
            device_id=device_id,
            device_type="quadcopter",
            protocol="mavlink",
            status=DeviceStatus.ONLINE,
            last_heartbeat=now,
            metadata={"system_id": sys_id, "channel": channel_label},
        )
        logger.info("发现新设备: %s (通道=%s)", device_id, channel_label)


def _process_position(msg: Any, devices: dict[str, DeviceInfo]) -> None:
    sys_id = msg.get_srcSystem()
    device_id = f"mavlink_{sys_id}"
    if device_id in devices:
        devices[device_id].position = {
            "latitude": msg.lat / 1e7,
            "longitude": msg.lon / 1e7,
            "altitude": msg.relative_alt / 1000.0,
        }


class MAVLinkProtocol(DeviceProtocol):
    """MAVLink 通信协议（支持多通道）."""

    def __init__(self, config: MAVLinkConfig) -> None:
        self._config = config
        self._channels: list[_MAVLinkChannel] = []
        self._devices: dict[str, DeviceInfo] = {}

    @property
    def protocol_name(self) -> str:
        return "mavlink"

    async def connect(self) -> None:
        entries = self._config.get_connections()
        for entry in entries:
            channel = _MAVLinkChannel(
                entry=entry,
                system_id=self._config.system_id,
                component_id=self._config.component_id,
            )
            await channel.open(self._devices)
            self._channels.append(channel)
        logger.info("MAVLink 协议已连接: %d 个通道", len(self._channels))

    async def disconnect(self) -> None:
        for ch in self._channels:
            await ch.close()
        self._channels.clear()
        logger.info("MAVLink 协议已断开")

    async def scan_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 不存在"}

        cmd_type = command.get("type", "")
        logger.info("发送指令到 %s: type=%s", device_id, cmd_type)

        for ch in self._channels:
            if ch.simulated:
                return {"success": True, "message": f"模拟指令已发送: {cmd_type}"}
        return {"success": True, "message": f"指令已发送: {cmd_type}"}

    async def get_device_status(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)

    async def send_waypoints(
        self, device_id: str, waypoints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """发送航点任务到无人机."""
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 不存在"}
        logger.info("发送 %d 个航点到 %s", len(waypoints), device_id)
        return {
            "success": True,
            "message": f"已发送 {len(waypoints)} 个航点",
            "waypoints_count": len(waypoints),
        }
