"""边缘控制服务 HTTP 客户端 — 所有请求使用 POST."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from brain_box.config.settings import EdgeServerConfig

logger = logging.getLogger("brain_box.edge.client")


class EdgeClient:
    """
    边缘控制服务客户端.

    所有与边缘控制服务的通信都通过 POST 请求，
    URL 路径完全可配置。
    """

    def __init__(self, config: EdgeServerConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """初始化 HTTP 客户端."""
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
        )
        logger.info("边缘服务客户端已启动: %s", self._config.base_url)

    async def stop(self) -> None:
        """关闭 HTTP 客户端."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("边缘服务客户端已停止")

    async def send_heartbeat(self, data: dict[str, Any]) -> dict[str, Any]:
        """发送心跳到边缘服务."""
        return await self._post(self._config.heartbeat_path, data)

    async def report_drone_status(self, data: dict[str, Any]) -> dict[str, Any]:
        """上报无人机状态到边缘服务."""
        return await self._post(self._config.drone_report_path, data)

    async def report_trajectory(self, data: dict[str, Any]) -> dict[str, Any]:
        """上报导航轨迹到边缘服务."""
        return await self._post(self._config.trajectory_report_path, data)

    async def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """统一 POST 请求."""
        if not self._client:
            logger.warning("边缘服务客户端未初始化")
            return {"success": False, "error": "客户端未初始化"}
        try:
            response = await self._client.post(path, json=data)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            logger.debug("POST %s 成功: %s", path, response.status_code)
            return result
        except httpx.HTTPStatusError as e:
            logger.error("POST %s 失败: %s", path, e.response.status_code)
            return {"success": False, "error": str(e), "status_code": e.response.status_code}
        except httpx.RequestError as e:
            logger.error("POST %s 请求异常: %s", path, e)
            return {"success": False, "error": str(e)}
