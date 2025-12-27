"""
代理功能和 Key 绑定关系测试

测试内容：
1. ProxyManager 基本功能
2. 代理和 API Key 的绑定关系
3. 代理失败计数和自动禁用
4. 一致性哈希选择代理
5. ProxyCheckService 代理检测功能
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# 设置测试环境变量，避免配置验证错误
os.environ.setdefault("DATABASE_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DATABASE", "test_db")
os.environ.setdefault("API_KEYS", "[]")
os.environ.setdefault("ALLOWED_TOKENS", '["test-token"]')

from app.service.proxy.proxy_manager import ProxyManager
from app.service.proxy.proxy_check_service import ProxyCheckService, ProxyCheckResult


class TestProxyManager(unittest.TestCase):
    """ProxyManager 单元测试"""

    def setUp(self):
        """测试前初始化"""
        self.proxies = [
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080",
        ]
        self.manager = ProxyManager(self.proxies)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(len(self.manager.proxies), 3)
        self.assertEqual(len(self.manager.proxy_failure_counts), 3)
        self.assertEqual(len(self.manager.disabled_proxies), 0)
        self.assertEqual(len(self.manager.key_proxy_bindings), 0)

    def test_init_empty_proxies(self):
        """测试空代理列表初始化"""
        manager = ProxyManager([])
        self.assertEqual(len(manager.proxies), 0)
        self.assertEqual(len(manager.proxy_failure_counts), 0)

    def test_init_none_proxies(self):
        """测试 None 代理列表初始化"""
        manager = ProxyManager(None)
        self.assertEqual(len(manager.proxies), 0)

    def test_get_available_proxies(self):
        """测试获取可用代理列表"""
        async def run_test():
            available = await self.manager.get_available_proxies()
            self.assertEqual(len(available), 3)
            self.assertEqual(available, self.proxies)

        asyncio.run(run_test())

    def test_get_available_proxies_with_disabled(self):
        """测试获取可用代理列表（有禁用代理）"""
        async def run_test():
            self.manager.disabled_proxies.add(self.proxies[0])
            available = await self.manager.get_available_proxies()
            self.assertEqual(len(available), 2)
            self.assertNotIn(self.proxies[0], available)

        asyncio.run(run_test())

    def test_get_proxy_for_key_consistency_hash(self):
        """测试一致性哈希选择代理"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 3

                api_key = "sk-test-key-12345"

                # 多次获取应该返回相同的代理
                proxy1 = await self.manager.get_proxy_for_key(api_key)
                proxy2 = await self.manager.get_proxy_for_key(api_key)
                proxy3 = await self.manager.get_proxy_for_key(api_key)

                self.assertEqual(proxy1, proxy2)
                self.assertEqual(proxy2, proxy3)
                self.assertIn(proxy1, self.proxies)

        asyncio.run(run_test())

    def test_get_proxy_for_key_binding_created(self):
        """测试代理绑定关系创建"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 3

                api_key = "sk-test-key-12345"
                proxy = await self.manager.get_proxy_for_key(api_key)

                # 验证绑定关系已创建
                self.assertIn(api_key, self.manager.key_proxy_bindings)
                self.assertEqual(self.manager.key_proxy_bindings[api_key], proxy)

        asyncio.run(run_test())

    def test_get_proxy_for_key_different_keys(self):
        """测试不同 Key 可能绑定不同代理"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 3

                # 使用多个不同的 key 来测试分布
                keys = [f"sk-test-key-{i}" for i in range(100)]
                proxies_used = set()

                for key in keys:
                    proxy = await self.manager.get_proxy_for_key(key)
                    proxies_used.add(proxy)

                # 应该使用了多个代理（哈希分布）
                self.assertGreater(len(proxies_used), 1)

        asyncio.run(run_test())

    def test_get_proxy_for_key_random_mode(self):
        """测试随机选择代理模式"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = False
                mock_settings.PROXY_MAX_FAILURES = 3

                api_key = "sk-test-key-12345"
                proxy = await self.manager.get_proxy_for_key(api_key)

                # 随机模式下不应该创建绑定
                self.assertNotIn(api_key, self.manager.key_proxy_bindings)
                self.assertIn(proxy, self.proxies)

        asyncio.run(run_test())

    def test_get_proxy_for_key_no_proxies(self):
        """测试无代理时返回 None"""
        async def run_test():
            manager = ProxyManager([])
            proxy = await manager.get_proxy_for_key("sk-test-key")
            self.assertIsNone(proxy)

        asyncio.run(run_test())

    def test_record_proxy_failure(self):
        """测试记录代理失败"""
        async def run_test():
            proxy = self.proxies[0]

            # 记录失败但未达到阈值
            disabled = await self.manager.record_proxy_failure(proxy)
            self.assertFalse(disabled)
            self.assertEqual(self.manager.proxy_failure_counts[proxy], 1)

        asyncio.run(run_test())

    def test_record_proxy_failure_disable(self):
        """测试代理失败次数达到阈值后禁用"""
        async def run_test():
            proxy = self.proxies[0]
            self.manager.MAX_FAILURES = 3

            # 记录多次失败
            await self.manager.record_proxy_failure(proxy)
            await self.manager.record_proxy_failure(proxy)
            disabled = await self.manager.record_proxy_failure(proxy)

            self.assertTrue(disabled)
            self.assertIn(proxy, self.manager.disabled_proxies)

        asyncio.run(run_test())

    def test_record_proxy_failure_unbind_keys(self):
        """测试代理禁用时解除 Key 绑定"""
        async def run_test():
            proxy = self.proxies[0]
            self.manager.MAX_FAILURES = 3

            # 创建绑定关系
            self.manager.key_proxy_bindings["key1"] = proxy
            self.manager.key_proxy_bindings["key2"] = proxy
            self.manager.key_proxy_bindings["key3"] = self.proxies[1]

            # 禁用代理
            for _ in range(3):
                await self.manager.record_proxy_failure(proxy)

            # 验证绑定已解除
            self.assertNotIn("key1", self.manager.key_proxy_bindings)
            self.assertNotIn("key2", self.manager.key_proxy_bindings)
            # key3 绑定到其他代理，不受影响
            self.assertIn("key3", self.manager.key_proxy_bindings)

        asyncio.run(run_test())

    def test_record_proxy_success(self):
        """测试记录代理成功重置失败计数"""
        async def run_test():
            proxy = self.proxies[0]

            # 先记录一些失败
            await self.manager.record_proxy_failure(proxy)
            await self.manager.record_proxy_failure(proxy)
            self.assertEqual(self.manager.proxy_failure_counts[proxy], 2)

            # 记录成功
            await self.manager.record_proxy_success(proxy)
            self.assertEqual(self.manager.proxy_failure_counts[proxy], 0)

        asyncio.run(run_test())

    def test_reset_proxy(self):
        """测试重置单个代理"""
        async def run_test():
            proxy = self.proxies[0]
            self.manager.MAX_FAILURES = 2

            # 禁用代理
            await self.manager.record_proxy_failure(proxy)
            await self.manager.record_proxy_failure(proxy)
            self.assertIn(proxy, self.manager.disabled_proxies)

            # 重置代理
            await self.manager.reset_proxy(proxy)
            self.assertNotIn(proxy, self.manager.disabled_proxies)
            self.assertEqual(self.manager.proxy_failure_counts[proxy], 0)

        asyncio.run(run_test())

    def test_reset_all_proxies(self):
        """测试重置所有代理"""
        async def run_test():
            # 设置一些状态
            self.manager.disabled_proxies.add(self.proxies[0])
            self.manager.proxy_failure_counts[self.proxies[1]] = 2
            self.manager.key_proxy_bindings["key1"] = self.proxies[0]

            # 重置所有
            await self.manager.reset_all_proxies()

            self.assertEqual(len(self.manager.disabled_proxies), 0)
            self.assertEqual(self.manager.proxy_failure_counts[self.proxies[1]], 0)
            self.assertEqual(len(self.manager.key_proxy_bindings), 0)

        asyncio.run(run_test())

    def test_disable_proxy(self):
        """测试手动禁用代理"""
        async def run_test():
            proxy = self.proxies[0]
            self.manager.key_proxy_bindings["key1"] = proxy

            await self.manager.disable_proxy(proxy)

            self.assertIn(proxy, self.manager.disabled_proxies)
            self.assertNotIn("key1", self.manager.key_proxy_bindings)

        asyncio.run(run_test())

    def test_enable_proxy(self):
        """测试手动启用代理"""
        async def run_test():
            proxy = self.proxies[0]
            self.manager.disabled_proxies.add(proxy)
            self.manager.proxy_failure_counts[proxy] = 5

            await self.manager.enable_proxy(proxy)

            self.assertNotIn(proxy, self.manager.disabled_proxies)
            self.assertEqual(self.manager.proxy_failure_counts[proxy], 0)

        asyncio.run(run_test())

    def test_get_proxy_status(self):
        """测试获取代理状态"""
        async def run_test():
            # 设置一些状态
            self.manager.disabled_proxies.add(self.proxies[0])
            self.manager.proxy_failure_counts[self.proxies[1]] = 2
            self.manager.key_proxy_bindings["key1"] = self.proxies[2]
            self.manager.key_proxy_bindings["key2"] = self.proxies[2]

            status = await self.manager.get_proxy_status()

            self.assertEqual(status["total"], 3)
            self.assertEqual(status["available"], 2)
            self.assertEqual(status["disabled"], 1)
            self.assertTrue(status["proxies"][self.proxies[0]]["is_disabled"])
            self.assertEqual(status["proxies"][self.proxies[1]]["failure_count"], 2)
            self.assertEqual(status["proxies"][self.proxies[2]]["bound_keys_count"], 2)

        asyncio.run(run_test())

    def test_unbind_key_from_proxy(self):
        """测试解除 Key 绑定"""
        async def run_test():
            self.manager.key_proxy_bindings["key1"] = self.proxies[0]
            self.manager.key_proxy_bindings["key2"] = self.proxies[1]

            await self.manager.unbind_key_from_proxy("key1")

            self.assertNotIn("key1", self.manager.key_proxy_bindings)
            self.assertIn("key2", self.manager.key_proxy_bindings)

        asyncio.run(run_test())

    def test_reload_proxies_add_new(self):
        """测试重新加载代理 - 添加新代理"""
        async def run_test():
            new_proxies = self.proxies + ["http://proxy4.example.com:8080"]
            await self.manager.reload_proxies(new_proxies)

            self.assertEqual(len(self.manager.proxies), 4)
            self.assertIn("http://proxy4.example.com:8080", self.manager.proxies)

        asyncio.run(run_test())

    def test_reload_proxies_remove_old(self):
        """测试重新加载代理 - 移除旧代理"""
        async def run_test():
            # 创建绑定
            self.manager.key_proxy_bindings["key1"] = self.proxies[0]

            new_proxies = self.proxies[1:]  # 移除第一个代理
            await self.manager.reload_proxies(new_proxies)

            self.assertEqual(len(self.manager.proxies), 2)
            self.assertNotIn(self.proxies[0], self.manager.proxies)
            # 绑定应该被解除
            self.assertNotIn("key1", self.manager.key_proxy_bindings)

        asyncio.run(run_test())

    def test_rebind_after_proxy_disabled(self):
        """测试代理禁用后重新绑定到其他代理"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 2

                # 设置实例的 MAX_FAILURES
                self.manager.MAX_FAILURES = 2

                api_key = "sk-test-key-12345"

                # 获取初始代理
                proxy1 = await self.manager.get_proxy_for_key(api_key)

                # 禁用该代理
                await self.manager.record_proxy_failure(proxy1)
                await self.manager.record_proxy_failure(proxy1)

                # 再次获取代理，应该绑定到新代理
                proxy2 = await self.manager.get_proxy_for_key(api_key)

                self.assertNotEqual(proxy1, proxy2)
                self.assertNotIn(proxy1, await self.manager.get_available_proxies())

        asyncio.run(run_test())


class TestProxyCheckService(unittest.TestCase):
    """ProxyCheckService 单元测试"""

    def setUp(self):
        """测试前初始化"""
        self.service = ProxyCheckService()

    def test_valid_proxy_format(self):
        """测试有效代理格式验证"""
        valid_proxies = [
            "http://proxy.example.com:8080",
            "https://proxy.example.com:8080",
            "socks5://proxy.example.com:1080",
            "http://user:pass@proxy.example.com:8080",
        ]
        for proxy in valid_proxies:
            self.assertTrue(
                self.service._is_valid_proxy_format(proxy),
                f"Should be valid: {proxy}"
            )

    def test_invalid_proxy_format(self):
        """测试无效代理格式验证"""
        invalid_proxies = [
            "proxy.example.com:8080",  # 缺少协议
            "ftp://proxy.example.com:8080",  # 不支持的协议
            "http://",  # 缺少主机
            "",  # 空字符串
            "not-a-proxy",  # 无效格式
        ]
        for proxy in invalid_proxies:
            self.assertFalse(
                self.service._is_valid_proxy_format(proxy),
                f"Should be invalid: {proxy}"
            )

    def test_cache_result(self):
        """测试缓存结果"""
        result = ProxyCheckResult(
            proxy="http://proxy.example.com:8080",
            is_available=True,
            response_time=0.5,
            checked_at=1000.0
        )
        self.service._cache_result(result)

        self.assertIn("http://proxy.example.com:8080", self.service._cache)

    def test_get_cached_result_valid(self):
        """测试获取有效缓存"""
        result = ProxyCheckResult(
            proxy="http://proxy.example.com:8080",
            is_available=True,
            response_time=0.5,
            checked_at=time.time()
        )
        self.service._cache_result(result)

        cached = self.service._get_cached_result("http://proxy.example.com:8080")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.is_available, True)

    def test_get_cached_result_expired(self):
        """测试获取过期缓存"""
        result = ProxyCheckResult(
            proxy="http://proxy.example.com:8080",
            is_available=True,
            response_time=0.5,
            checked_at=time.time() - 100  # 过期
        )
        self.service._cache_result(result)

        cached = self.service._get_cached_result("http://proxy.example.com:8080")
        self.assertIsNone(cached)

    def test_check_single_proxy_invalid_format(self):
        """测试检测无效格式代理"""
        async def run_test():
            result = await self.service.check_single_proxy("invalid-proxy")
            self.assertFalse(result.is_available)
            self.assertEqual(result.error_message, "Invalid proxy format")

        asyncio.run(run_test())

    def test_check_single_proxy_with_cache(self):
        """测试使用缓存检测代理"""
        async def run_test():
            # 预设缓存
            cached_result = ProxyCheckResult(
                proxy="http://proxy.example.com:8080",
                is_available=True,
                response_time=0.5,
                checked_at=time.time()
            )
            self.service._cache_result(cached_result)

            # 应该返回缓存结果
            result = await self.service.check_single_proxy(
                "http://proxy.example.com:8080",
                use_cache=True
            )
            self.assertTrue(result.is_available)
            self.assertEqual(result.response_time, 0.5)

        asyncio.run(run_test())

    def test_get_cache_stats(self):
        """测试获取缓存统计"""
        # 添加一些缓存
        self.service._cache["proxy1"] = ProxyCheckResult(
            proxy="proxy1",
            is_available=True,
            checked_at=time.time()
        )
        self.service._cache["proxy2"] = ProxyCheckResult(
            proxy="proxy2",
            is_available=False,
            checked_at=time.time() - 100  # 过期
        )

        stats = self.service.get_cache_stats()
        self.assertEqual(stats["total_cached"], 2)
        self.assertEqual(stats["valid_cached"], 1)
        self.assertEqual(stats["expired_cached"], 1)

    def test_clear_cache(self):
        """测试清除缓存"""
        self.service._cache["proxy1"] = ProxyCheckResult(
            proxy="proxy1",
            is_available=True,
            checked_at=time.time()
        )

        self.service.clear_cache()
        self.assertEqual(len(self.service._cache), 0)


class TestProxyKeyBindingIntegration(unittest.TestCase):
    """代理和 Key 绑定关系集成测试"""

    def test_binding_persistence(self):
        """测试绑定关系持久性"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 3

                proxies = [
                    "http://proxy1.example.com:8080",
                    "http://proxy2.example.com:8080",
                ]
                manager = ProxyManager(proxies)

                # 创建多个 key 的绑定
                keys = ["key1", "key2", "key3"]
                bindings = {}

                for key in keys:
                    proxy = await manager.get_proxy_for_key(key)
                    bindings[key] = proxy

                # 验证绑定持久性
                for key in keys:
                    proxy = await manager.get_proxy_for_key(key)
                    self.assertEqual(proxy, bindings[key])

        asyncio.run(run_test())

    def test_binding_after_proxy_recovery(self):
        """测试代理恢复后的绑定行为"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 2

                proxies = [
                    "http://proxy1.example.com:8080",
                    "http://proxy2.example.com:8080",
                ]
                manager = ProxyManager(proxies)

                api_key = "test-key"

                # 获取初始绑定
                initial_proxy = await manager.get_proxy_for_key(api_key)

                # 禁用代理
                await manager.record_proxy_failure(initial_proxy)
                await manager.record_proxy_failure(initial_proxy)

                # 获取新绑定
                new_proxy = await manager.get_proxy_for_key(api_key)
                self.assertNotEqual(initial_proxy, new_proxy)

                # 恢复原代理
                await manager.reset_proxy(initial_proxy)

                # 由于已有新绑定，应该保持新绑定
                current_proxy = await manager.get_proxy_for_key(api_key)
                self.assertEqual(current_proxy, new_proxy)

        asyncio.run(run_test())

    def test_multiple_keys_same_proxy(self):
        """测试多个 Key 绑定到同一代理"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 2

                # 只有一个代理
                proxies = ["http://proxy1.example.com:8080"]
                manager = ProxyManager(proxies)

                keys = ["key1", "key2", "key3"]

                for key in keys:
                    proxy = await manager.get_proxy_for_key(key)
                    self.assertEqual(proxy, proxies[0])

                # 所有 key 都应该绑定到同一个代理
                status = await manager.get_proxy_status()
                self.assertEqual(status["proxies"][proxies[0]]["bound_keys_count"], 3)

        asyncio.run(run_test())

    def test_all_proxies_disabled_fallback(self):
        """测试所有代理禁用时的 fallback"""
        async def run_test():
            with patch('app.service.proxy.proxy_manager.settings') as mock_settings:
                mock_settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY = True
                mock_settings.PROXY_MAX_FAILURES = 1

                proxies = [
                    "http://proxy1.example.com:8080",
                    "http://proxy2.example.com:8080",
                ]
                manager = ProxyManager(proxies)

                # 禁用所有代理
                for proxy in proxies:
                    await manager.record_proxy_failure(proxy)

                # 应该返回第一个代理作为 fallback
                proxy = await manager.get_proxy_for_key("test-key")
                self.assertEqual(proxy, proxies[0])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
