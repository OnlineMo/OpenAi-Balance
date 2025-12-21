"""
代理管理器模块

提供代理的状态管理、失败计数和自动禁用功能。
支持：
- 代理失败计数跟踪
- 自动禁用失败次数过多的代理
- 解除 API Key 与代理的绑定关系
- 代理状态查询
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Set

from app.config.config import settings
from app.log.logger import Logger

logger = Logger.setup_logger("proxy_manager")


class ProxyManager:
    """
    代理管理器

    管理代理的状态、失败计数和 API Key 绑定关系。

    Attributes:
        proxies: 所有代理列表
        proxy_failure_counts: 代理失败计数字典
        disabled_proxies: 被禁用的代理集合
        key_proxy_bindings: API Key 与代理的绑定关系
        MAX_FAILURES: 最大失败次数阈值
    """

    def __init__(self, proxies: List[str] = None):
        """
        初始化代理管理器

        Args:
            proxies: 代理列表
        """
        self.proxies = proxies or []
        self.proxy_failure_counts: Dict[str, int] = {proxy: 0 for proxy in self.proxies}
        self.disabled_proxies: Set[str] = set()
        self.key_proxy_bindings: Dict[str, str] = {}  # api_key -> proxy
        self.MAX_FAILURES = settings.PROXY_MAX_FAILURES
        self._lock = asyncio.Lock()
        self._last_check_time: Dict[str, float] = {}  # proxy -> last check timestamp

    async def reload_proxies(self, new_proxies: List[str]):
        """
        重新加载代理列表

        保留现有代理的状态，添加新代理，移除不存在的代理。

        Args:
            new_proxies: 新的代理列表
        """
        async with self._lock:
            new_proxy_set = set(new_proxies)
            old_proxy_set = set(self.proxies)

            # 添加新代理
            for proxy in new_proxy_set - old_proxy_set:
                self.proxy_failure_counts[proxy] = 0
                logger.info(f"Added new proxy: {proxy}")

            # 移除不存在的代理
            for proxy in old_proxy_set - new_proxy_set:
                self.proxy_failure_counts.pop(proxy, None)
                self.disabled_proxies.discard(proxy)
                self._last_check_time.pop(proxy, None)
                # 解除与该代理的所有绑定
                keys_to_unbind = [k for k, v in self.key_proxy_bindings.items() if v == proxy]
                for key in keys_to_unbind:
                    del self.key_proxy_bindings[key]
                logger.info(f"Removed proxy: {proxy}")

            self.proxies = new_proxies

    async def get_available_proxies(self) -> List[str]:
        """
        获取所有可用的代理列表

        Returns:
            可用代理列表
        """
        async with self._lock:
            return [p for p in self.proxies if p not in self.disabled_proxies]

    async def get_proxy_for_key(self, api_key: str) -> Optional[str]:
        """
        根据 API Key 获取代理

        如果启用了一致性哈希，则使用哈希值选择代理。
        否则随机选择一个可用代理。

        Args:
            api_key: API 密钥

        Returns:
            代理地址，如果没有可用代理则返回 None
        """
        if not self.proxies:
            return None

        async with self._lock:
            available_proxies = [p for p in self.proxies if p not in self.disabled_proxies]

            if not available_proxies:
                logger.warning("No available proxies, all proxies are disabled")
                # 如果所有代理都被禁用，返回第一个代理作为 fallback
                return self.proxies[0] if self.proxies else None

            if settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY:
                # 检查是否已有绑定
                if api_key in self.key_proxy_bindings:
                    bound_proxy = self.key_proxy_bindings[api_key]
                    if bound_proxy in available_proxies:
                        return bound_proxy
                    # 绑定的代理已被禁用，需要重新绑定
                    del self.key_proxy_bindings[api_key]

                # 使用一致性哈希选择代理
                proxy = available_proxies[hash(api_key) % len(available_proxies)]
                self.key_proxy_bindings[api_key] = proxy
                return proxy
            else:
                return random.choice(available_proxies)

    async def record_proxy_failure(self, proxy: str) -> bool:
        """
        记录代理失败

        增加失败计数，如果超过阈值则禁用代理。

        Args:
            proxy: 代理地址

        Returns:
            True 如果代理被禁用
        """
        if not proxy or proxy not in self.proxy_failure_counts:
            return False

        async with self._lock:
            self.proxy_failure_counts[proxy] += 1
            current_count = self.proxy_failure_counts[proxy]

            if current_count >= self.MAX_FAILURES:
                self.disabled_proxies.add(proxy)
                # 解除与该代理的所有绑定
                keys_to_unbind = [k for k, v in self.key_proxy_bindings.items() if v == proxy]
                for key in keys_to_unbind:
                    del self.key_proxy_bindings[key]
                logger.warning(
                    f"Proxy {proxy} has been disabled after {current_count} failures. "
                    f"Unbound {len(keys_to_unbind)} API keys."
                )
                return True

            logger.info(f"Proxy {proxy} failure count: {current_count}/{self.MAX_FAILURES}")
            return False

    async def record_proxy_success(self, proxy: str):
        """
        记录代理成功

        重置失败计数。

        Args:
            proxy: 代理地址
        """
        if not proxy or proxy not in self.proxy_failure_counts:
            return

        async with self._lock:
            if self.proxy_failure_counts[proxy] > 0:
                self.proxy_failure_counts[proxy] = 0
                logger.debug(f"Proxy {proxy} success, failure count reset")

    async def reset_proxy(self, proxy: str):
        """
        重置代理状态

        重置失败计数并重新启用代理。

        Args:
            proxy: 代理地址
        """
        async with self._lock:
            if proxy in self.proxy_failure_counts:
                self.proxy_failure_counts[proxy] = 0
            self.disabled_proxies.discard(proxy)
            logger.info(f"Proxy {proxy} has been reset and re-enabled")

    async def reset_all_proxies(self):
        """重置所有代理状态"""
        async with self._lock:
            for proxy in self.proxies:
                self.proxy_failure_counts[proxy] = 0
            self.disabled_proxies.clear()
            self.key_proxy_bindings.clear()
            logger.info("All proxies have been reset")

    async def disable_proxy(self, proxy: str):
        """
        手动禁用代理

        Args:
            proxy: 代理地址
        """
        async with self._lock:
            if proxy in self.proxies:
                self.disabled_proxies.add(proxy)
                # 解除与该代理的所有绑定
                keys_to_unbind = [k for k, v in self.key_proxy_bindings.items() if v == proxy]
                for key in keys_to_unbind:
                    del self.key_proxy_bindings[key]
                logger.info(f"Proxy {proxy} has been manually disabled")

    async def enable_proxy(self, proxy: str):
        """
        手动启用代理

        Args:
            proxy: 代理地址
        """
        async with self._lock:
            if proxy in self.proxies:
                self.disabled_proxies.discard(proxy)
                self.proxy_failure_counts[proxy] = 0
                logger.info(f"Proxy {proxy} has been manually enabled")

    async def get_proxy_status(self) -> Dict:
        """
        获取所有代理的状态

        Returns:
            包含代理状态信息的字典
        """
        async with self._lock:
            status = {
                "total": len(self.proxies),
                "available": len(self.proxies) - len(self.disabled_proxies),
                "disabled": len(self.disabled_proxies),
                "proxies": {}
            }

            for proxy in self.proxies:
                status["proxies"][proxy] = {
                    "failure_count": self.proxy_failure_counts.get(proxy, 0),
                    "is_disabled": proxy in self.disabled_proxies,
                    "bound_keys_count": sum(1 for v in self.key_proxy_bindings.values() if v == proxy),
                    "last_check_time": self._last_check_time.get(proxy)
                }

            return status

    async def update_last_check_time(self, proxy: str):
        """
        更新代理最后检测时间

        Args:
            proxy: 代理地址
        """
        async with self._lock:
            self._last_check_time[proxy] = time.time()

    async def unbind_key_from_proxy(self, api_key: str):
        """
        解除 API Key 与代理的绑定

        Args:
            api_key: API 密钥
        """
        async with self._lock:
            if api_key in self.key_proxy_bindings:
                proxy = self.key_proxy_bindings[api_key]
                del self.key_proxy_bindings[api_key]
                logger.info(f"Unbound API key from proxy {proxy}")


# 单例相关
_proxy_manager_instance: Optional[ProxyManager] = None
_proxy_manager_lock = asyncio.Lock()


async def get_proxy_manager() -> ProxyManager:
    """
    获取 ProxyManager 单例实例

    Returns:
        ProxyManager 单例实例
    """
    global _proxy_manager_instance

    async with _proxy_manager_lock:
        if _proxy_manager_instance is None:
            _proxy_manager_instance = ProxyManager(settings.PROXIES)
            logger.info(f"ProxyManager instance created with {len(settings.PROXIES)} proxies")
        return _proxy_manager_instance


async def reset_proxy_manager():
    """重置 ProxyManager 单例实例"""
    global _proxy_manager_instance

    async with _proxy_manager_lock:
        if _proxy_manager_instance:
            _proxy_manager_instance = None
            logger.info("ProxyManager instance has been reset")


async def reload_proxy_manager():
    """重新加载代理配置"""
    global _proxy_manager_instance

    async with _proxy_manager_lock:
        if _proxy_manager_instance:
            await _proxy_manager_instance.reload_proxies(settings.PROXIES)
            _proxy_manager_instance.MAX_FAILURES = settings.PROXY_MAX_FAILURES
            logger.info("ProxyManager configuration reloaded")
        else:
            _proxy_manager_instance = ProxyManager(settings.PROXIES)
            logger.info(f"ProxyManager instance created with {len(settings.PROXIES)} proxies")
