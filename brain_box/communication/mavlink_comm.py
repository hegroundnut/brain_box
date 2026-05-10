"""MAVLink 通信协议实现 — 与无人机通信."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from brain_box.config.settings import MAVLinkConfig
from brain_box.core.device import DeviceInfo, DeviceProtocol, DeviceStatus

logger = logging.getLogger("brain_box.communication.mavlink")

_MAX_SIMULATED_DRONES = 3


class MAVLinkProtocol(DeviceProtocol):
    """
    MAVLink 通信协议实现.

    使用 pymavlink 与无人机进行 MAVLink 通信，
    支持心跳检测、状态查询、指令下发等功能。
    """

    def __init__(self, config: MAVLinkConfig) -> None:
        self._config = config
        self._connection: Any = None
        self._devices: dict[str, DeviceInfo] = {}
        self._running = False
        self._scan_task: asyncio.Task[None] | None = None

    @property
    def protocol_name(self) -> str:
        return "mavlink"

    @property
    def devices(self) -> dict[str, DeviceInfo]:
        return dict(self._devices)

    async def connect(self) -> None:
        """建立 MAVLink 连接."""
        try:
            from pymavlink import mavutil

            self._connection = mavutil.mavlink_connection(
                self._config.connection_string,
                source_system=self._config.system_id,
                source_component=self._config.component_id,
                baud=self._config.baud_rate,
            )
            self._running = True
            self._scan_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(
                "MAVLink 已连接: %s", self._config.connection_string
            )
        except ImportError:
            logger.warning(
                "pymavlink 未安装，MAVLink 协议使用模拟模式"
            )
            self._running = True
            self._scan_task = asyncio.create_task(self._simulated_heartbeat_loop())
        except Exception:
            logger.exception("MAVLink 连接失败")
            raise

    async def disconnect(self) -> None:
        """断开 MAVLink 连接."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scan_task
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.info("MAVLink 已断开")

    async def scan_devices(self) -> list[DeviceInfo]:
        """返回当前已发现的无人机列表."""
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

        if self._connection:
            return await self._send_mavlink_command(device, command)

        return {"success": True, "message": f"模拟发送指令 {cmd_type} 到 {device_id}"}

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

        logger.info(
            "向设备 %s 发送 %d 个航点", device_id, len(waypoints)
        )

        if self._connection:
            return await self._upload_mission(device, waypoints)

        return {
            "success": True,
            "message": f"模拟发送 {len(waypoints)} 个航点到 {device_id}",
            "waypoint_count": len(waypoints),
        }

    def _update_device_status(self) -> None:
        """根据心跳超时更新设备状态."""
        timeout = self._config.heartbeat_timeout
        for device in self._devices.values():
            if device.is_alive(timeout):
                if device.status != DeviceStatus.BUSY:
                    device.status = DeviceStatus.ONLINE
            else:
                device.status = DeviceStatus.OFFLINE

    async def _heartbeat_loop(self) -> None:
        """MAVLink 心跳监听循环."""
        while self._running:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._connection.recv_match(
                        type="HEARTBEAT", blocking=True, timeout=1
                    ),
                )
                if msg:
                    self._process_heartbeat(msg)

                await self._poll_messages()
            except Exception:
                logger.exception("MAVLink 心跳循环异常")
            await asyncio.sleep(0.1)

    async def _simulated_heartbeat_loop(self) -> None:
        """模拟心跳循环（pymavlink 不可用时）."""
        sim_id = 0
        while self._running:
            sim_id_str = f"drone_sim_{sim_id}"
            if sim_id_str not in self._devices and sim_id < _MAX_SIMULATED_DRONES:
                self._devices[sim_id_str] = DeviceInfo(
                    device_id=sim_id_str,
                    device_type="quadcopter",
                    protocol="mavlink",
                    status=DeviceStatus.ONLINE,
                    ip_address="127.0.0.1",
                    port=14550 + sim_id,
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
                    },
                )
                logger.info("模拟发现无人机: %s", sim_id_str)
                sim_id += 1

            for device in self._devices.values():
                device.last_heartbeat = time.time()
                device.status = DeviceStatus.ONLINE

            await asyncio.sleep(self._config.scan_interval)

    def _process_heartbeat(self, msg: Any) -> None:
        """处理心跳消息，更新设备列表."""
        sys_id = msg.get_srcSystem()
        device_id = f"drone_{sys_id}"

        if device_id not in self._devices:
            self._devices[device_id] = DeviceInfo(
                device_id=device_id,
                device_type=self._get_mav_type_name(msg.type),
                protocol="mavlink",
                status=DeviceStatus.ONLINE,
                metadata={
                    "autopilot": msg.autopilot,
                    "mav_type": msg.type,
                    "system_status": msg.system_status,
                },
            )
            logger.info("发现新无人机: %s (type=%s)", device_id, msg.type)

        device = self._devices[device_id]
        device.last_heartbeat = time.time()
        device.status = DeviceStatus.ONLINE
        device.metadata["system_status"] = msg.system_status

    async def _poll_messages(self) -> None:
        """轮询位置等消息."""
        if not self._connection:
            return
        msg = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._connection.recv_match(
                type="GLOBAL_POSITION_INT", blocking=False
            ),
        )
        if msg:
            sys_id = msg.get_srcSystem()
            device_id = f"drone_{sys_id}"
            device = self._devices.get(device_id)
            if device:
                device.position = {
                    "latitude": msg.lat / 1e7,
                    "longitude": msg.lon / 1e7,
                    "altitude": msg.alt / 1000.0,
                    "relative_alt": msg.relative_alt / 1000.0,
                    "heading": msg.hdg / 100.0,
                }

    async def _send_mavlink_command(
        self, device: DeviceInfo, command: dict[str, Any]
    ) -> dict[str, Any]:
        """通过 MAVLink 发送指令."""
        cmd_type = command.get("type", "")
        if cmd_type == "arm":
            await self._arm_disarm(device, arm=True)
        elif cmd_type == "disarm":
            await self._arm_disarm(device, arm=False)
        elif cmd_type == "takeoff":
            altitude = command.get("altitude", 10.0)
            await self._takeoff(device, altitude)
        elif cmd_type == "land":
            await self._land(device)
        elif cmd_type == "goto":
            await self._goto(device, command)
        else:
            return {"success": False, "error": f"未知指令类型: {cmd_type}"}
        return {"success": True, "command": cmd_type, "device_id": device.device_id}

    async def _arm_disarm(self, device: DeviceInfo, *, arm: bool) -> None:
        from pymavlink import mavutil

        self._connection.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1 if arm else 0,
            0, 0, 0, 0, 0, 0,
        )

    async def _takeoff(self, device: DeviceInfo, altitude: float) -> None:
        from pymavlink import mavutil

        self._connection.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            altitude,
        )

    async def _land(self, device: DeviceInfo) -> None:
        from pymavlink import mavutil

        self._connection.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0, 0, 0, 0,
        )

    async def _goto(self, device: DeviceInfo, command: dict[str, Any]) -> None:
        from pymavlink import mavutil

        lat = command.get("latitude", 0)
        lon = command.get("longitude", 0)
        alt = command.get("altitude", 10)
        self._connection.mav.command_long_send(
            int(device.device_id.split("_")[1]),
            0,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            0,
            0, 0, 0, 0,
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
        )

    async def _upload_mission(
        self, device: DeviceInfo, waypoints: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """上传航点任务到无人机."""
        if not self._connection:
            return {"success": False, "error": "MAVLink 未连接"}

        from pymavlink import mavutil

        target_system = int(device.device_id.split("_")[1])

        self._connection.mav.mission_count_send(target_system, 0, len(waypoints))

        for i, wp in enumerate(waypoints):
            self._connection.mav.mission_item_int_send(
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

    @staticmethod
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
