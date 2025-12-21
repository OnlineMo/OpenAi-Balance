"""
多提供商密钥管理模块

为每个提供商维护独立的 KeyManager 实例。
"""

import asyncio
from typing import Dict, List, Optional

from app.config.provider_config import ProviderConfig
from app.log.logger import get_key_manager_logger
from app.service.key.key_manager import KeyManager

logger = get_key_manager_logger()


class ProviderKeyManager:
    """
    多提供商密钥管理器

    为每个提供商维护独立的 KeyManager 实例，支持按提供商名称获取密钥管理器。

    Attributes:
        _managers: 提供商名称到 KeyManager 实例的映射
        _configs: 提供商名称到配置的映射
        _lock: 异步锁，保护并发访问
    """

    def __init__(self):
        """初始化多提供商密钥管理器"""
        self._managers: Dict[str, KeyManager] = {}
        self._configs: Dict[str, ProviderConfig] = {}
        self._lock = asyncio.Lock()

    async def register_provider(self, config: ProviderConfig) -> bool:
        """
        注册一个提供商

        Args:
            config: 提供商配置

        Returns:
            True 如果注册成功
        """
        async with self._lock:
            if not config.enabled:
                logger.info(f"Provider '{config.name}' is disabled, skipping registration.")
                return False

            if not config.api_keys:
                logger.warning(f"Provider '{config.name}' has no API keys, skipping registration.")
                return False

            # 创建新的 KeyManager 实例
            manager = KeyManager(config.api_keys)
            manager.MAX_FAILURES = config.max_failures

            self._managers[config.name] = manager
            self._configs[config.name] = config

            logger.info(
                f"Registered provider '{config.name}' with {len(config.api_keys)} API keys."
            )
            return True

    async def unregister_provider(self, name: str) -> bool:
        """
        注销一个提供商

        Args:
            name: 提供商名称

        Returns:
            True 如果注销成功
        """
        async with self._lock:
            if name in self._managers:
                del self._managers[name]
                del self._configs[name]
                logger.info(f"Unregistered provider '{name}'.")
                return True
            logger.warning(f"Provider '{name}' not found for unregistration.")
            return False

    async def get_manager(self, name: str) -> Optional[KeyManager]:
        """
        获取指定提供商的 KeyManager

        Args:
            name: 提供商名称

        Returns:
            KeyManager 实例，如果不存在则返回 None
        """
        async with self._lock:
            return self._managers.get(name)

    async def get_config(self, name: str) -> Optional[ProviderConfig]:
        """
        获取指定提供商的配置

        Args:
            name: 提供商名称

        Returns:
            ProviderConfig 实例，如果不存在则返回 None
        """
        async with self._lock:
            return self._configs.get(name)

    async def get_all_providers(self) -> List[str]:
        """
        获取所有已注册的提供商名称

        Returns:
            提供商名称列表
        """
        async with self._lock:
            return list(self._managers.keys())

    async def get_all_configs(self) -> List[ProviderConfig]:
        """
        获取所有已注册的提供商配置

        Returns:
            提供商配置列表
        """
        async with self._lock:
            return list(self._configs.values())

    async def get_provider_by_path(self, path: str) -> Optional[str]:
        """
        根据路径获取提供商名称

        Args:
            path: 路由路径标识

        Returns:
            提供商名称，如果不存在则返回 None
        """
        async with self._lock:
            for name, config in self._configs.items():
                if config.path == path:
                    return name
            return None

    async def get_all_providers_status(self) -> Dict[str, dict]:
        """
        获取所有提供商的密钥状态

        Returns:
            提供商名称到密钥状态的映射
        """
        result = {}
        async with self._lock:
            for name, manager in self._managers.items():
                config = self._configs.get(name)
                keys_status = await manager.get_all_keys_with_fail_count()
                result[name] = {
                    "config": config.model_dump() if config else {},
                    "keys_status": keys_status,
                    "total_keys": len(manager.api_keys),
                    "valid_keys_count": len(keys_status.get("valid_keys", {})),
                    "invalid_keys_count": len(keys_status.get("invalid_keys", {})),
                }
        return result

    async def reload_providers(self, configs: List[ProviderConfig]) -> None:
        """
        重新加载所有提供商配置

        保留现有提供商的失败计数状态。

        Args:
            configs: 新的提供商配置列表
        """
        async with self._lock:
            # 保存现有的失败计数
            preserved_counts: Dict[str, Dict[str, int]] = {}
            for name, manager in self._managers.items():
                preserved_counts[name] = manager.key_failure_counts.copy()

            # 清空现有管理器
            self._managers.clear()
            self._configs.clear()

        # 注册新的提供商
        for config in configs:
            if not config.enabled:
                continue
            if not config.api_keys:
                continue

            manager = KeyManager(config.api_keys)
            manager.MAX_FAILURES = config.max_failures

            # 恢复失败计数
            if config.name in preserved_counts:
                old_counts = preserved_counts[config.name]
                for key in manager.api_keys:
                    if key in old_counts:
                        manager.key_failure_counts[key] = old_counts[key]

            async with self._lock:
                self._managers[config.name] = manager
                self._configs[config.name] = config

            logger.info(
                f"Reloaded provider '{config.name}' with {len(config.api_keys)} API keys."
            )

    async def clear_all(self) -> None:
        """清空所有提供商"""
        async with self._lock:
            self._managers.clear()
            self._configs.clear()
            logger.info("Cleared all providers.")


# 单例实例
_provider_key_manager: Optional[ProviderKeyManager] = None
_provider_key_manager_lock = asyncio.Lock()


async def get_provider_key_manager() -> ProviderKeyManager:
    """
    获取 ProviderKeyManager 单例实例

    Returns:
        ProviderKeyManager 单例实例
    """
    global _provider_key_manager

    async with _provider_key_manager_lock:
        if _provider_key_manager is None:
            _provider_key_manager = ProviderKeyManager()
            logger.info("ProviderKeyManager instance created.")
        return _provider_key_manager


async def reset_provider_key_manager() -> None:
    """重置 ProviderKeyManager 单例实例"""
    global _provider_key_manager

    async with _provider_key_manager_lock:
        if _provider_key_manager:
            await _provider_key_manager.clear_all()
        _provider_key_manager = None
        logger.info("ProviderKeyManager instance has been reset.")
