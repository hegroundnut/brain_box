"""类脑盒子服务器 — 主入口."""

from __future__ import annotations

import argparse
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from brain_box.api.routes import create_api_router
from brain_box.communication.mavlink_comm import MAVLinkProtocol
from brain_box.communication.registry import ProtocolRegistry
from brain_box.config import get_settings
from brain_box.drone.manager import DroneManager
from brain_box.edge.client import EdgeClient
from brain_box.edge.reporter import EdgeReporter
from brain_box.logging_config import setup_logging
from brain_box.navigation.registry import AlgorithmRegistry
from brain_box.navigation.service import NavigationService
from brain_box.navigation.simple_nav import SimpleNavigationAlgorithm

logger: logging.Logger


def build_app(config_path: str | None = None) -> FastAPI:
    """构建并返回 FastAPI 应用 (方便测试)."""
    global logger  # noqa: PLW0603

    settings = get_settings(config_path)
    logger = setup_logging(settings.logging)
    logger.info("类脑盒子服务器启动中...")
    logger.info("边缘服务: %s", settings.edge.base_url)
    logger.info("MAVLink: %s", settings.mavlink.connection_string)

    # ── 通信协议注册 ──
    protocol_registry = ProtocolRegistry()
    mavlink_proto = MAVLinkProtocol(settings.mavlink)
    protocol_registry.register(mavlink_proto)

    # ── 导航算法注册 ──
    algorithm_registry = AlgorithmRegistry()
    algorithm_registry.register(SimpleNavigationAlgorithm())

    # ── 无人机管理器 ──
    drone_manager = DroneManager(
        protocol_registry=protocol_registry,
        scan_interval=settings.mavlink.scan_interval,
    )

    # ── 边缘服务客户端 & 上报器 ──
    edge_client = EdgeClient(settings.edge)
    edge_reporter = EdgeReporter(
        edge_client=edge_client,
        drone_manager=drone_manager,
        heartbeat_interval=settings.edge.heartbeat_interval,
        report_interval=settings.edge.report_interval,
    )

    # ── 导航服务 ──
    navigation_service = NavigationService(
        algorithm_registry=algorithm_registry,
        drone_manager=drone_manager,
        protocol_registry=protocol_registry,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """应用生命周期管理."""
        await protocol_registry.connect_all()
        await drone_manager.start()
        await edge_client.start()
        await edge_reporter.start()
        logger.info("所有服务已启动")
        try:
            yield
        finally:
            logger.info("正在关闭服务...")
            await edge_reporter.stop()
            await edge_client.stop()
            await drone_manager.stop()
            await protocol_registry.disconnect_all()
            logger.info("所有服务已停止")

    app = FastAPI(
        title="BrainBox 类脑盒子服务器",
        description="类脑盒子服务器 — 无人机管控与导航系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    api_router = create_api_router(
        drone_manager=drone_manager,
        navigation_service=navigation_service,
        edge_reporter=edge_reporter,
    )
    app.include_router(api_router)

    return app


def main() -> None:
    """命令行入口."""
    parser = argparse.ArgumentParser(description="BrainBox 类脑盒子服务器")
    parser.add_argument(
        "-c", "--config", default=None, help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    args = parser.parse_args()

    settings = get_settings(args.config)
    host = args.host or settings.server.host
    port = args.port or settings.server.port

    app = build_app(args.config)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
