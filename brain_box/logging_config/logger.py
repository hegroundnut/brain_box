"""灵活可配置的日志系统."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from brain_box.config.settings import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """初始化日志系统，返回 root logger."""
    root = logging.getLogger("brain_box")
    root.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(config.format)

    if config.console_enabled:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

    if config.file_enabled:
        log_dir = Path(config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / config.log_file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    return root
