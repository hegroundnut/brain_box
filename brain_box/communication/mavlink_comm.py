"""MAVLink 通信协议实现 — 支持多连接通道与无人机通信."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from brain_box.config.settings import MAVLinkConfig, MAVLinkConnectionEntry
from brain_box.core.device import DeviceInfo, DeviceProtocol, DeviceStatus

logger = logging.getLogger("brain_box.communication.mavlink")

_MAX_SIMULATED_DRONES = 3


class _MAVLinkChannel:
    """单个 MAVLink 连接通道（内部使用）."""

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

    @property
    def label(self) -> str:
        return self.entry.label or self.entry.connection_string

    async def open(self, devices: dict[str, DeviceInfo]) -> None:
        """打开连接并启动心跳循环."""
        try:
            from pymavlink import mavutil

            self.connection = mavutil.mavlink_connection(
                self.entry.connection_string,
                source_system=self.system_id,
                source_component=self.component_id,
                baud=self.entry.baud_rate,
            )
            self.simulated = False
            self._running = True
            self._task = asyncio.create_task(self._heartbeat_loop(devices))
            logger.info(
                "MAVLink 通道已连接: %s (%s)",
                self.label,
                self.entry.connection_string,
            )
        except ImportError:
            logger.warning(
                "pymavlink 未安装，通道 '%s' 使用模拟模式", self.label
            )
            self.simulated = True
            self._running = True
            self._task = asyncio.create_task(
                self._simulated_heartbeat_loop(devices)
            )
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

    # ── 心跳循环 ──────────────────────────────────────────────

    async def _heartbeat_loop(self, devices: dict[str, DeviceInfo]) -> None:
        while self._running:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.connection.recv_match(
                        type="HEARTBEAT", blocking=True, timeout=1
                    ),
                )
                if msg:
                    _process_heartbeat(msg, devices, self.label)

                await self._poll_messages(devices)
            except Exception:
                logger.exception("MAVLink 心跳循环异常 (通道 %s)", self.label)
            await asyncio.sleep(0.1)

    async def _simulated_heartbeat_loop(
        self, devices: dict[str, DeviceInfo]
    ) -> None:
        sim_id = 0
        prefix = self.label.replace(" ", "_")
        while self._running:
            sim_id_str = f"drone_sim_{prefix}_{sim_id}"
            if sim_id_str not in devices and sim_id < _MAX_SIMULATED_DRONES:
                devices[sim_id_str] = DeviceInfo(
                    device_id=sim_id_str,
                    device_type="quadcopter",
                    protocol="mavlink",
                    status=DeviceStatus.ONLINE,
                    ip_address="127.0.0.1",
                    port=int(
                        self.entry.connection_string.rsplit(":", 1)[-1]
                        if ":" in self.entry.connection_string
                        else 14550
                    )
                    + sim_id,
                    last_heartbeat=time.time(),
                    position={
                        "latitude": 39.9042 + sim_id * 0.001,
                        "longitude": 116.4074 + sim_id * 0.001,
                        "altitude": 100.0 + sim_id * 10,
                    },
                    metadata={
                        "autopilot": "simulated",
                        "mav_type": "quadrotor",
                        "system_status": "active",
                        "channel": self.label,
                    },
                )
                logger.info("模拟发现无人机: %s (通道 %s)", sim_id_str, self.label)
                sim_id += 1

            for device in devices.values():
                if device.metadata.get("channel") == self.label:
                    device.last_heartbeat = time.time()
                    device.status = DeviceStatus.ONLINE

            await asyncio.sleep(3.0)

    async def _poll_messages(self, devices: dict[str, DeviceInfo]) -> None:
        if not self.connection:
            return
        msg = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.connection.recv_match(
                type="GLOBAL_POSITION_INT", blocking=False
            ),
        )
        if msg:
            sys_id = msg.get_srcSystem()
            device_id = f"drone_{sys_id}"
            device = devices.get(device_id)
            if device:
                device.position = {
                    "latitude": msg.lat / 1e7,
                    "longitude": msg.lon / 1e7,
                    "altitude": msg.alt / 1000.0,
                    "relative_alt": msg.relative_alt / 1000.0,
                    "heading": msg.hdg / 100.0,
                }


# ── 公共辅助函数 ──────────────────────────────────────────────


def _process_heartbeat(
    msg: Any, devices: dict[str, DeviceInfo], channel_label: str
) -> None:
    sys_id = msg.get_srcSystem()
    device_id = f"drone_{sys_id}"

    if device_id not in devices:
        devices[device_id] = DeviceInfo(
            device_id=device_id,
            device_type=_get_mav_type_name(msg.type),
            protocol="mavlink",
            status=DeviceStatus.ONLINE,
            metadata={
                "autopilot": msg.autopilot,
                "mav_type": msg.type,
                "system_status": msg.system_status,
                "channel": channel_label,
            },
        )
        logger.info(
            "发现新无人机: %s (type=%s, 通道=%s)",
            device_id,
            msg.type,
            channel_label,
        )

    device = devices[device_id]
    device.last_heartbeat = time.time()
    device.status = DeviceStatus.ONLINE
    device.metadata["system_status"] = msg.system_status


def _get_mav_type_name(mav_type: int) -> str:
    type_map = {
        0: "generic",
        1: "fixed_wing",
        2: "quadrotor",
        3: "coaxial",
        4: "helicopter",
        13: "hexarotor",
        14: "octorotor",
    }
    return type_map.get(mav_type, f"unknown_{mav_type}")


# ── 主协议类 ──────────────────────────────────────────────────


class MAVLinkProtocol(DeviceProtocol):
    """
    MAVLink 通信协议实现（多连接通道）.

    支持同时在多个端口/地址上监听和发送 MAVLink 消息，
    每个通道可以是 UDP、TCP 或串口连接。
    """

    def __init__(self, config: MAVLinkConfig) -> None:
        self._config = config
        self._devices: dict[str, DeviceInfo] = {}
        self._channels: list[_MAVLinkChannel] = []

    @property
    def protocol_name(self) -> str:
        return "mavlink"

    @property
    def devices(self) -> dict[str, DeviceInfo]:
        return dict(self._devices)

    async def connect(self) -> None:
        """建立所有 MAVLink 通道连接."""
        entries = self._config.get_connections()
        logger.info("MAVLink 初始化 %d 个连接通道", len(entries))
        for entry in entries:
            channel = _MAVLinkChannel(
                entry=entry,
                system_id=self._config.system_id,
                component_id=self._config.component_id,
            )
            try:
                await channel.open(self._devices)
                self._channels.append(channel)
            except Exception:
                logger.exception(
                    "MAVLink 通道 '%s' 启动失败，跳过",
                    entry.label or entry.connection_string,
                )

    async def disconnect(self) -> None:
        """断开所有 MAVLink 通道."""
        for ch in self._channels:
            try:
                await ch.close()
            except Exception:
                logger.exception("MAVLink 通道 '%s' 关闭异常", ch.label)
        self._channels.clear()
        logger.info("MAVLink 所有通道已断开")

    async def scan_devices(self) -> list[DeviceInfo]:
        """返回当前所有通道已发现的无人机列表."""
        self._update_device_status()
        return list(self._devices.values())

    async def send_command(
        self, device_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        """向无人机发送 MAVLink 指令."""
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 未找到"}

        cmd_type = command.get("type", "")
        logger.info("向设备 %s 发送指令: %s", device_id, cmd_type)

        channel = self._find_channel_for_device(device)
        if channel and channel.connection:
            return await self._send_mavlink_command(channel, device, command)

        return {
            "success": True,
            "message": f"模拟发送指令 {cmd_type} 到 {device_id}",
        }

    async def get_device_status(self, device_id: str) -> DeviceInfo | None:
        """获取指定无人机状态."""
        self._update_device_status()
        return self._devices.get(device_id)

    async def send_waypoints(
        self, device_id: str, waypoints: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """向无人机发送航点任务."""
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "error": f"设备 {device_id} 未找到"}

        logger.info("向设备 %s 发送 %d 个航点", device_id, len(waypoints))

        channel = self._find_channel_for_device(device)
        if channel and channel.connection:
            return await self._upload_mission(channel, device, waypoints)

        return {
            "success": True,
            "message": f"模拟发送 {len(waypoints)} 个航点到 {device_id}",
            "waypoint_count": len(waypoints),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _find_channel_for_device(self, device: DeviceInfo) -> _MAVLinkChannel | None:
        """根据设备 metadata 中的 channel 标签找到对应通道."""
        ch_label = device.metadata.get("channel", "")
        for ch in self._channels:
            if ch.label == ch_label:
                return ch
        return self._channels[0] if self._channels else None

    def _update_device_status(self) -> None:
        timeout = self._config.heartbeat_timeout
        for device in self._devices.values():
            if device.is_alive(timeout):
                if device.status != DeviceStatus.BUSY:
                    device.status = DeviceStatus.ONLINE
            else:
                device.status = DeviceStatus.OFFLINE

    async def _send_mavlink_command(
        self,
        channel: _MAVLinkChannel,
        device: DeviceInfo,
        command: dict[str, Any],
    ) -> dict[str, Any]:
        cmd_type = command.get("type", "")
        conn = channel.connection
        if cmd_type == "arm":
            await self._arm_disarm(conn, device, arm=True)
        elif cmd_type == "disarm":
            await self._arm_disarm(conn, device, arm=False)
        elif cmd_type == "takeoff":
            altitude = command.get("altitude", 10.0)
            await self._takeoff(conn, device, altitude)
        elif cmd_type == "land":
            await self._land(conn, device)
        elif cmd_type == "goto":
            await self._goto(conn, device, command)
        else:
            return {"success": False, "error": f"未知指令类型: {cmd_type}"}
        return {"success": True, "command": cmd_type, "device_id": device.device_id}

    @staticmethod
    async def _arm_disarm(conn: Any, device: DeviceInfo, *, arm: bool) -> None:
        from pymavlink import mavutil

        conn.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1 if arm else 0,
            0, 0, 0, 0, 0, 0,
        )

    @staticmethod
    async def _takeoff(conn: Any, device: DeviceInfo, altitude: float) -> None:
        from pymavlink import mavutil

        conn.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            altitude,
        )

    @staticmethod
    async def _land(conn: Any, device: DeviceInfo) -> None:
        from pymavlink import mavutil

        conn.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0, 0, 0, 0,
        )

    @staticmethod
    async def _goto(conn: Any, device: DeviceInfo, command: dict[str, Any]) -> None:
        from pymavlink import mavutil

        lat = command.get("latitude", 0)
        lon = command.get("longitude", 0)
        alt = command.get("altitude", 10)
        conn.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            0,
            0, 0, 0, 0,
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
        )

    @staticmethod
    async def _upload_mission(
        channel: _MAVLinkChannel,
        device: DeviceInfo,
        waypoints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        conn = channel.connection
        if not conn:
            return {"success": False, "error": "MAVLink 未连接"}

        from pymavlink import mavutil

        target_system = int(device.device_id.split("_")[1])

        conn.mav.mission_count_send(target_system, 0, len(waypoints))

        for i, wp in enumerate(waypoints):
            conn.mav.mission_item_int_send(
                target_system, 0,
                i,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0, 1,
                wp.get("hold_time", 0),
                0, 0, 0,
                int(wp.get("latitude", 0) * 1e7),
                int(wp.get("longitude", 0) * 1e7),
                wp.get("altitude", 10),
            )

        return {"success": True, "waypoint_count": len(waypoints)}
