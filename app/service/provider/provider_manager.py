"""
提供商管理器模块

管理所有提供商的初始化、获取和重新加载。
"""

import asyncio
import json
from typing import Dict, List, Optional

from app.config.config import settings
from app.config.provider_config import ProviderConfig, ProvidersConfig
from app.log.logger import get_key_manager_logger
from app.service.key.key_manager import KeyManager
from app.service.provider.provider_key_manager import (
    ProviderKeyManager,
    get_provider_key_manager,
)
from app.service.provider.provider_service import ProviderService

logger = get_key_manager_logger()


class ProviderManager:
    """
    提供商管理器

    管理所有提供商的生命周期，包括：
    - 初始化提供商
    - 获取提供商服务
    - 重新加载配置

    Attributes:
        _services: 提供商名称到服务实例的映射
        _key_manager: 多提供商密钥管理器
        _default_provider: 默认提供商名称
        _lock: 异步锁
    """

    def __init__(self):
        """初始化提供商管理器"""
        self._services: Dict[str, ProviderService] = {}
        self._key_manager: Optional[ProviderKeyManager] = None
        self._default_provider: str = "default"
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """
        初始化提供商管理器

        从配置中加载提供商配置并创建服务实例。
        """
        async with self._lock:
            if self._initialized:
                logger.info("ProviderManager already initialized, skipping.")
                return

            self._key_manager = await get_provider_key_manager()
            self._default_provider = settings.DEFAULT_PROVIDER

            # 解析提供商配置
            providers_config = self._parse_providers_config()

            if not providers_config:
                logger.info("No providers configured, using default provider from settings.")
                # 创建默认提供商（使用现有配置）
                await self._create_default_provider()
            else:
                # 注册所有配置的提供商
                for config in providers_config:
                    await self._register_provider(config)

                # 如果 DEFAULT_PROVIDER 未设置或为 "default"，自动使用第一个启用的提供商
                if self._default_provider == "default" and self._services:
                    first_provider = next(iter(self._services.keys()))
                    self._default_provider = first_provider
                    logger.info(
                        f"DEFAULT_PROVIDER not set, using first enabled provider: {first_provider}"
                    )

            self._initialized = True
            logger.info(
                f"ProviderManager initialized with {len(self._services)} providers. "
                f"Default provider: {self._default_provider}"
            )

    def _parse_providers_config(self) -> List[ProviderConfig]:
        """
        解析提供商配置

        Returns:
            提供商配置列表
        """
        try:
            config_str = settings.PROVIDERS_CONFIG
            if not config_str or config_str == "[]":
                return []

            config_data = json.loads(config_str)
            if not isinstance(config_data, list):
                logger.error("PROVIDERS_CONFIG must be a JSON array")
                return []

            providers = []
            for item in config_data:
                try:
                    provider = ProviderConfig(**item)
                    providers.append(provider)
                except Exception as e:
                    logger.error(f"Failed to parse provider config: {item}, error: {e}")

            return providers

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse PROVIDERS_CONFIG as JSON: {e}")
            return []

    async def _create_default_provider(self) -> None:
        """
        创建默认提供商

        使用现有的全局配置创建默认提供商。
        """
        if not settings.API_KEYS:
            logger.warning("No API keys configured for default provider.")
            return

        default_config = ProviderConfig(
            name="default",
            path="",
            base_url=settings.BASE_URL,
            api_keys=settings.API_KEYS,
            custom_headers=settings.CUSTOM_HEADERS,
            timeout=settings.TIME_OUT,
            max_failures=settings.MAX_FAILURES,
            max_retries=settings.MAX_RETRIES,
            enabled=True,
        )

        await self._register_provider(default_config)
        self._default_provider = "default"

    async def _register_provider(self, config: ProviderConfig) -> bool:
        """
        注册一个提供商

        Args:
            config: 提供商配置

        Returns:
            True 如果注册成功
        """
        if not config.enabled:
            logger.info(f"Provider '{config.name}' is disabled, skipping.")
            return False

        if not config.api_keys:
            logger.warning(f"Provider '{config.name}' has no API keys, skipping.")
            return False

        # 注册到密钥管理器
        await self._key_manager.register_provider(config)

        # 获取密钥管理器实例
        key_manager = await self._key_manager.get_manager(config.name)
        if not key_manager:
            logger.error(f"Failed to get key manager for provider '{config.name}'")
            return False

        # 创建服务实例
        service = ProviderService(config, key_manager)
        self._services[config.name] = service

        logger.info(f"Registered provider service '{config.name}'")
        return True

    async def get_service(self, name: str) -> Optional[ProviderService]:
        """
        获取指定提供商的服务

        Args:
            name: 提供商名称

        Returns:
            ProviderService 实例，如果不存在则返回 None
        """
        async with self._lock:
            return self._services.get(name)

    async def get_default_service(self) -> Optional[ProviderService]:
        """
        获取默认提供商的服务

        Returns:
            默认提供商的 ProviderService 实例
        """
        return await self.get_service(self._default_provider)

    async def get_service_by_path(self, path: str) -> Optional[ProviderService]:
        """
        根据路径获取提供商服务

        Args:
            path: 路由路径标识

        Returns:
            ProviderService 实例，如果不存在则返回 None
        """
        async with self._lock:
            for name, service in self._services.items():
                if service.config.path == path:
                    return service
            return None

    async def get_all_services(self) -> Dict[str, ProviderService]:
        """
        获取所有提供商服务

        Returns:
            提供商名称到服务实例的映射
        """
        async with self._lock:
            return self._services.copy()

    async def get_all_providers_status(self) -> Dict[str, dict]:
        """
        获取所有提供商的状态

        Returns:
            提供商名称到状态信息的映射
        """
        if self._key_manager:
            return await self._key_manager.get_all_providers_status()
        return {}

    async def reload_config(self) -> None:
        """
        重新加载提供商配置

        保留现有提供商的失败计数状态。
        """
        async with self._lock:
            logger.info("Reloading provider configuration...")

            # 更新默认提供商
            self._default_provider = settings.DEFAULT_PROVIDER

            # 解析新配置
            providers_config = self._parse_providers_config()

            if not providers_config:
                # 如果没有配置提供商，检查是否需要更新默认提供商
                if "default" in self._services:
                    default_service = self._services["default"]
                    # 检查配置是否有变化
                    if (
                        default_service.config.base_url != settings.BASE_URL
                        or default_service.config.api_keys != settings.API_KEYS
                    ):
                        # 清空并重新创建默认提供商
                        self._services.clear()
                        if self._key_manager:
                            await self._key_manager.clear_all()
                        await self._create_default_provider()
                else:
                    await self._create_default_provider()
            else:
                # 重新加载所有提供商
                if self._key_manager:
                    await self._key_manager.reload_providers(providers_config)

                # 重新创建服务实例
                self._services.clear()
                for config in providers_config:
                    if not config.enabled:
                        continue
                    key_manager = await self._key_manager.get_manager(config.name)
                    if key_manager:
                        service = ProviderService(config, key_manager)
                        self._services[config.name] = service

                # 如果 DEFAULT_PROVIDER 未设置或为 "default"，自动使用第一个启用的提供商
                if self._default_provider == "default" and self._services:
                    first_provider = next(iter(self._services.keys()))
                    self._default_provider = first_provider
                    logger.info(
                        f"DEFAULT_PROVIDER not set, using first enabled provider: {first_provider}"
                    )

            logger.info(
                f"Provider configuration reloaded. {len(self._services)} providers active. "
                f"Default provider: {self._default_provider}"
            )

    @property
    def default_provider(self) -> str:
        """获取默认提供商名称"""
        return self._default_provider

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized


# 单例实例
_provider_manager: Optional[ProviderManager] = None
_provider_manager_lock = asyncio.Lock()


async def get_provider_manager() -> ProviderManager:
    """
    获取 ProviderManager 单例实例

    Returns:
        ProviderManager 单例实例
    """
    global _provider_manager

    async with _provider_manager_lock:
        if _provider_manager is None:
            _provider_manager = ProviderManager()
            logger.info("ProviderManager instance created.")
        return _provider_manager


async def reset_provider_manager() -> None:
    """重置 ProviderManager 单例实例"""
    global _provider_manager

    async with _provider_manager_lock:
        _provider_manager = None
        logger.info("ProviderManager instance has been reset.")
