"""通信协议注册中心."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("brainBox.core.protocol_registry")


class DeviceProtocol:
    """设备通信协议抽象基类."""

    @property
    def protocol_name(self) -> str:
        raise NotImplementedError

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def scan_devices(self) -> list[Any]:
        raise NotImplementedError

    async def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def get_device_status(self, device_id: str) -> Any:
        raise NotImplementedError


class ProtocolRegistry:
    """通信协议注册中心 — 支持动态注册和发现通信协议."""

    def __init__(self) -> None:
        self._protocols: dict[str, DeviceProtocol] = {}

    def register(self, protocol: DeviceProtocol) -> None:
        name = protocol.protocol_name
        if name in self._protocols:
            logger.warning("协议 '%s' 已存在，将被覆盖", name)
        self._protocols[name] = protocol
        logger.info("已注册通信协议: %s", name)

    def unregister(self, name: str) -> None:
        if name in self._protocols:
            del self._protocols[name]
            logger.info("已注销通信协议: %s", name)

    def get(self, name: str) -> DeviceProtocol | None:
        return self._protocols.get(name)

    def list_protocols(self) -> list[str]:
        return list(self._protocols.keys())

    async def connect_all(self) -> None:
        for name, proto in self._protocols.items():
            try:
                await proto.connect()
                logger.info("协议 '%s' 连接成功", name)
            except Exception:
                logger.exception("协议 '%s' 连接失败", name)

    async def disconnect_all(self) -> None:
        for name, proto in self._protocols.items():
            try:
                await proto.disconnect()
                logger.info("协议 '%s' 已断开", name)
            except Exception:
                logger.exception("协议 '%s' 断开失败", name)

    async def scan_all_devices(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, proto in self._protocols.items():
            try:
                devices = await proto.scan_devices()
                results[name] = devices
            except Exception:
                logger.exception("协议 '%s' 扫描设备失败", name)
                results[name] = []
        return results
