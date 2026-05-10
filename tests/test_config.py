"""配置模块测试."""

import os
from pathlib import Path

from brain_box.config.settings import Settings, reset_settings


def test_default_settings() -> None:
    reset_settings()
    s = Settings()
    assert s.edge.base_url == "http://192.168.1.100:8080"
    assert s.server.port == 9000
    assert s.mavlink.connection_string == "udpin:0.0.0.0:14550"


def test_from_yaml(tmp_path: Path) -> None:
    reset_settings()
    config = tmp_path / "test_config.yaml"
    config.write_text(
        "edge:\n  base_url: http://10.0.0.1:8080\nserver:\n  port: 8888\n"
    )
    s = Settings.from_yaml(config)
    assert s.edge.base_url == "http://10.0.0.1:8080"
    assert s.server.port == 8888


def test_env_override() -> None:
    reset_settings()
    os.environ["BRAIN_BOX_EDGE_URL"] = "http://env.example.com"
    os.environ["BRAIN_BOX_SERVER_PORT"] = "7777"
    try:
        s = Settings()
        s.apply_env_overrides()
        assert s.edge.base_url == "http://env.example.com"
        assert s.server.port == 7777
    finally:
        del os.environ["BRAIN_BOX_EDGE_URL"]
        del os.environ["BRAIN_BOX_SERVER_PORT"]


def test_missing_yaml() -> None:
    reset_settings()
    s = Settings.from_yaml("/nonexistent/path.yaml")
    assert s.edge.base_url == "http://192.168.1.100:8080"
