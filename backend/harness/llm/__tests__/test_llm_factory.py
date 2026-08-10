
"""
LLM Client 工厂测试模块

测试内容：
1. 线程安全测试：多线程并发调用时不会创建重复实例
2. 缓存生命周期测试：TTL 过期、清理、定向删除
3. 客户端创建测试：正常、错误场景
"""
import threading
import time
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from harness.llm.factory import (
    get_llm_client,
    clear_llm_client_cache,
    remove_llm_client,
    _client_cache,
    _cache_lock
)
from harness.llm.base import LLMClient
from harness.llm.langchain_client import LangChainClient


class TestLLMFactory:
    """LLM Factory 测试类"""

    def setup_method(self):
        """测试前清理缓存"""
        # 清空所有缓存项
        with _cache_lock:
            _client_cache.clear()

    def test_get_llm_client_default(self):
        """测试获取默认 LLM 客户端"""
        client = get_llm_client()
        assert client is not None
        assert isinstance(client, LLMClient)
        # 验证有缓存项，但不固定是 qwen（取决于配置）
        assert len(_client_cache) == 1

    def test_get_llm_client_by_name(self):
        """测试通过名称获取 LLM 客户端"""
        client = get_llm_client('openai')
        assert client is not None
        assert 'openai' in _client_cache

    def test_get_llm_client_cached(self):
        """测试缓存复用"""
        client1 = get_llm_client('qwen')
        client2 = get_llm_client('qwen')
        assert client1 is client2, "同一个名称应该返回同一个实例"

    def test_thread_safety_concurrent_creation(self):
        """测试多线程并发创建时的线程安全"""
        clients = []
        errors = []

        def get_client():
            try:
                client = get_llm_client('qwen')
                clients.append(client)
            except Exception as e:
                errors.append(e)

        # 启动 20 个线程并发获取
        threads = []
        for _ in range(20):
            t = threading.Thread(target=get_client)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证：所有线程都拿到了同一个实例，没有报错
        assert len(errors) == 0, f"不应该有错误: {errors}"
        assert len(clients) == 20
        first_client = clients[0]
        assert all(c is first_client for c in clients), "所有线程应该拿到同一个实例"

    def test_cache_clear(self):
        """测试清空缓存"""
        # 先创建客户端
        client1 = get_llm_client('qwen')
        # 再创建一个
        client2 = get_llm_client('openai')
        
        assert len(_client_cache) == 2

        # 清空缓存
        asyncio.run(clear_llm_client_cache())
        assert len(_client_cache) == 0, "缓存应该被清空"

        # 再次获取，应该创建新实例
        client3 = get_llm_client('qwen')
        assert client3 is not None
        assert client3 is not client1, "清空后应该创建新实例"

    def test_remove_client(self):
        """测试定向删除客户端"""
        # 创建两个客户端
        client_qwen = get_llm_client('qwen')
        client_openai = get_llm_client('openai')
        assert 'qwen' in _client_cache
        assert 'openai' in _client_cache

        # 删除 qwen
        asyncio.run(remove_llm_client('qwen'))
        assert 'qwen' not in _client_cache
        assert 'openai' in _client_cache  # openai 应该还在

        # 删除 openai
        asyncio.run(remove_llm_client('openai'))
        assert 'openai' not in _client_cache

    def test_close_client(self):
        """测试关闭客户端"""
        client = get_llm_client('qwen')
        assert client._closed is False  # 应该未关闭

        # 调用关闭
        asyncio.run(client.close())
        assert client._closed is True, "客户端应该被标记为已关闭"

        # 再次关闭不应该报错
        asyncio.run(client.close())  # 应该安全重复调用

    def test_unknown_client_error(self):
        """测试未知客户端错误"""
        with pytest.raises(ValueError, match="Unknown LLM client"):
            get_llm_client('unknown_provider_that_does_not_exist')


class TestLangChainClient:
    """LangChain Client 测试类"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        client = LangChainClient()
        assert client._client is None
        assert client._closed is False
        assert hasattr(client, '_client_params')

    def test_get_client(self):
        """测试获取底层客户端"""
        client = LangChainClient()
        client_obj = client._get_client()
        assert client_obj is not None
        assert client._client is client_obj

        # 再次获取应该返回同一个
        client_obj2 = client._get_client()
        assert client_obj2 is client_obj

    def test_closed_client_protection(self):
        """测试已关闭客户端的防护"""
        client = LangChainClient()
        asyncio.run(client.close())

        with pytest.raises(RuntimeError, match="Client has been closed"):
            client._get_client()


class TestCacheTTL:
    """缓存 TTL 测试类"""

    @pytest.mark.slow
    def test_ttl_expiration(self):
        """测试 TTL 过期（使用 Patch 加速）"""
        # 使用 Patch 来模拟时间流逝
        current_time = 1000
        
        with patch('harness.llm.factory.time.monotonic') as mock_monotonic:
            # 初始时间
            mock_monotonic.side_effect = lambda: current_time
            
            client1 = get_llm_client('qwen')
            assert 'qwen' in _client_cache

            # 稍微过一点时间，但未过期
            current_time = 1000 + 1800  # 30分钟 - 一点
            client2 = get_llm_client('qwen')
            assert client2 is client1, "TTL 内应该复用实例"

            # 超过 TTL
            current_time = 1000 + 3600  # 超过 30分钟
            client3 = get_llm_client('qwen')
            assert client3 is not client1, "超过 TTL 应该创建新实例"


if __name__ == "__main__":
    # 如果直接运行这个文件，进行简单的测试
    pytest.main([__file__, "-v"])
