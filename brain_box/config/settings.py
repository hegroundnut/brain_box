"""可配置的系统设置，支持 YAML 文件和环境变量覆盖."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EdgeServerConfig:
    """边缘控制服务器配置."""

    base_url: str = "http://192.168.1.100:8080"
    heartbeat_path: str = "/api/v1/brain-box/heartbeat"
    drone_report_path: str = "/api/v1/brain-box/drone-report"
    trajectory_report_path: str = "/api/v1/brain-box/trajectory-report"
    heartbeat_interval: float = 5.0
    report_interval: float = 2.0
    timeout: float = 10.0


@dataclass
class MAVLinkConfig:
    """MAVLink 通信配置."""

    connection_string: str = "udpin:0.0.0.0:14550"
    system_id: int = 255
    component_id: int = 0
    scan_interval: float = 3.0
    heartbeat_timeout: float = 10.0
    baud_rate: int = 57600


@dataclass
class ServerConfig:
    """类脑盒子 HTTP 服务器配置."""

    host: str = "0.0.0.0"
    port: int = 9000
    debug: bool = False


@dataclass
class LoggingConfig:
    """日志配置."""

    level: str = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    log_dir: str = "logs"
    log_file: str = "brain_box.log"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass
class Settings:
    """全局配置."""

    edge: EdgeServerConfig = field(default_factory=EdgeServerConfig)
    mavlink: MAVLinkConfig = field(default_factory=MAVLinkConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Settings:
        """从 YAML 文件加载配置."""
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Settings:
        settings = cls()
        if "edge" in data:
            for k, v in data["edge"].items():
                if hasattr(settings.edge, k):
                    setattr(settings.edge, k, v)
        if "mavlink" in data:
            for k, v in data["mavlink"].items():
                if hasattr(settings.mavlink, k):
                    setattr(settings.mavlink, k, v)
        if "server" in data:
            for k, v in data["server"].items():
                if hasattr(settings.server, k):
                    setattr(settings.server, k, v)
        if "logging" in data:
            for k, v in data["logging"].items():
                if hasattr(settings.logging, k):
                    setattr(settings.logging, k, v)
        return settings

    def apply_env_overrides(self) -> None:
        """环境变量覆盖配置 (优先级最高)."""
        env_map = {
            "BRAIN_BOX_EDGE_URL": ("edge", "base_url"),
            "BRAIN_BOX_EDGE_HEARTBEAT_PATH": ("edge", "heartbeat_path"),
            "BRAIN_BOX_EDGE_DRONE_REPORT_PATH": ("edge", "drone_report_path"),
            "BRAIN_BOX_EDGE_TRAJECTORY_REPORT_PATH": ("edge", "trajectory_report_path"),
            "BRAIN_BOX_EDGE_HEARTBEAT_INTERVAL": ("edge", "heartbeat_interval"),
            "BRAIN_BOX_MAVLINK_CONNECTION": ("mavlink", "connection_string"),
            "BRAIN_BOX_MAVLINK_SYSTEM_ID": ("mavlink", "system_id"),
            "BRAIN_BOX_SERVER_HOST": ("server", "host"),
            "BRAIN_BOX_SERVER_PORT": ("server", "port"),
            "BRAIN_BOX_LOG_LEVEL": ("logging", "level"),
            "BRAIN_BOX_LOG_DIR": ("logging", "log_dir"),
        }
        for env_key, (section, attr) in env_map.items():
            val = os.environ.get(env_key)
            if val is None:
                continue
            obj = getattr(self, section)
            current = getattr(obj, attr)
            if isinstance(current, int):
                setattr(obj, attr, int(val))
            elif isinstance(current, float):
                setattr(obj, attr, float(val))
            elif isinstance(current, bool):
                setattr(obj, attr, val.lower() in ("true", "1", "yes"))
            else:
                setattr(obj, attr, val)


_settings: Settings | None = None


def get_settings(config_path: str | Path | None = None) -> Settings:
    """获取全局单例配置."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        path = config_path or os.environ.get("BRAIN_BOX_CONFIG", "config.yaml")
        _settings = Settings.from_yaml(path)
        _settings.apply_env_overrides()
    return _settings


def reset_settings() -> None:
    """重置配置 (测试用)."""
    global _settings  # noqa: PLW0603
    _settings = None
