"""导航算法注册中心 — 支持动态注册和发现导航算法."""

from __future__ import annotations

import logging

from brain_box.core.algorithm import NavigationAlgorithm

logger = logging.getLogger("brain_box.navigation.registry")


class AlgorithmRegistry:
    """
    导航算法注册中心.

    使用注册模式管理所有导航算法，支持运行时动态注册新算法。
    """

    def __init__(self) -> None:
        self._algorithms: dict[str, NavigationAlgorithm] = {}

    def register(self, algorithm: NavigationAlgorithm) -> None:
        """注册导航算法."""
        name = algorithm.algorithm_name
        if name in self._algorithms:
            logger.warning("算法 '%s' 已存在，将被覆盖", name)
        self._algorithms[name] = algorithm
        logger.info("已注册导航算法: %s", name)

    def unregister(self, name: str) -> None:
        """注销导航算法."""
        if name in self._algorithms:
            del self._algorithms[name]
            logger.info("已注销导航算法: %s", name)

    def get(self, name: str) -> NavigationAlgorithm | None:
        """获取指定算法."""
        return self._algorithms.get(name)

    def get_default(self) -> NavigationAlgorithm | None:
        """获取默认算法（第一个注册的）."""
        if self._algorithms:
            return next(iter(self._algorithms.values()))
        return None

    def list_algorithms(self) -> list[str]:
        """列出所有已注册算法."""
        return list(self._algorithms.keys())
