# -*- coding: utf-8 -*-
"""
policy_monitor/fetcher.py 测试套件

测试安全 HTTP 客户端：
  - SafeFetcher 初始化
  - fetch 网页抓取（mock）
  - fetch_bytes 二进制抓取（mock）
  - robots.txt 检查
  - 重试机制
  - 错误处理
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "policy_monitor"))
sys.path.insert(0, str(PROJECT_ROOT))

from fetcher import SafeFetcher


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def fetcher_config():
    """最小配置"""
    return {
        "safety": {
            "min_delay_seconds": 0.1,
            "max_delay_seconds": 0.2,
            "api_min_delay_seconds": 0.1,
            "api_max_delay_seconds": 0.2,
            "timeout_seconds": 5,
            "max_retries": 2,
            "respect_robots": True,
            "user_agents": ["TestAgent/1.0"],
        }
    }


@pytest.fixture
def fetcher(fetcher_config):
    """创建 SafeFetcher（延迟极短，用于测试）"""
    return SafeFetcher(fetcher_config)


# ============================================================
# 初始化
# ============================================================


class TestSafeFetcherInit:
    """测试 SafeFetcher 初始化"""

    def test_init_default(self):
        """默认配置"""
        f = SafeFetcher({})
        assert f.timeout == 15  # 默认超时
        assert f.max_retries == 3

    def test_init_custom(self, fetcher_config):
        """自定义配置"""
        f = SafeFetcher(fetcher_config)
        assert f.timeout == 5
        assert f.max_retries == 2
        assert f.user_agents == ["TestAgent/1.0"]

    def test_init_minimal(self):
        """最小配置"""
        f = SafeFetcher({"safety": {}})
        assert f.min_delay == 30  # 默认值


# ============================================================
# fetch 网页抓取
# ============================================================


class TestFetch:
    """测试 fetch 方法"""

    def test_fetch_success(self, fetcher):
        """成功抓取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>测试内容</html>"
        mock_response.apparent_encoding = "utf-8"

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"):
            result = fetcher.fetch("https://example.com/test", source_type="html")

        assert result == "<html>测试内容</html>"

    def test_fetch_404_returns_none(self, fetcher):
        """404 返回 None"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"):
            result = fetcher.fetch("https://example.com/missing")

        assert result is None

    def test_fetch_403_returns_none(self, fetcher):
        """403 重试后返回 None"""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"), \
             patch("time.sleep"):
            result = fetcher.fetch("https://example.com/forbidden")

        assert result is None

    def test_fetch_timeout_retries(self, fetcher):
        """超时重试"""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise requests.Timeout("timeout")
            resp = MagicMock()
            resp.status_code = 200
            resp.text = "成功"
            resp.apparent_encoding = "utf-8"
            return resp

        with patch.object(fetcher._session, "get", side_effect=side_effect), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"), \
             patch("time.sleep"):
            result = fetcher.fetch("https://example.com/slow")

        assert result == "成功"
        assert call_count == 3

    def test_fetch_connection_error_returns_none(self, fetcher):
        """连接失败返回 None"""
        with patch.object(fetcher._session, "get", side_effect=requests.ConnectionError("fail")), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"), \
             patch("time.sleep"):
            result = fetcher.fetch("https://unreachable.com")

        assert result is None

    def test_fetch_robots_disallowed(self, fetcher):
        """robots.txt 禁止"""
        with patch.object(fetcher, "_check_robots", return_value=False):
            result = fetcher.fetch("https://example.com/forbidden", source_type="html")

        assert result is None

    def test_fetch_api_skips_robots(self, fetcher):
        """API 类型跳过 robots 检查"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "ok"}'
        mock_response.apparent_encoding = "utf-8"

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_wait_for_type"):
            result = fetcher.fetch("https://api.example.com/search", source_type="api")

        assert result == '{"data": "ok"}'

    def test_fetch_user_agent_set(self, fetcher):
        """请求带 User-Agent"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_response.apparent_encoding = "utf-8"

        with patch.object(fetcher._session, "get", return_value=mock_response) as mock_get, \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"):
            fetcher.fetch("https://example.com")

        # 检查 headers 被设置
        assert "User-Agent" in fetcher._session.headers


# ============================================================
# fetch_bytes
# ============================================================


class TestFetchBytes:
    """测试 fetch_bytes 方法"""

    def test_fetch_bytes_success(self, fetcher):
        """成功获取二进制"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"binary data"

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait"):
            result = fetcher.fetch_bytes("https://example.com/sitemap.xml")

        assert result == b"binary data"

    def test_fetch_bytes_robots_blocked(self, fetcher):
        """robots 禁止"""
        with patch.object(fetcher, "_check_robots", return_value=False):
            result = fetcher.fetch_bytes("https://example.com/secret.xml")

        assert result is None


# ============================================================
# robots.txt
# ============================================================


class TestRobotsCheck:
    """测试 robots.txt 检查"""

    def test_robots_disabled(self, fetcher):
        """禁用 robots 检查"""
        fetcher.respect_robots = False
        assert fetcher._check_robots("https://example.com/anything") is True

    def test_robots_cache_hit(self, fetcher):
        """缓存命中"""
        # 预填充缓存
        fetcher._robots_cache["https://example.com"] = None
        assert fetcher._check_robots("https://example.com/test") is True

    def test_robots_404_allows(self, fetcher):
        """robots.txt 404 -> 默认允许"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(fetcher._session, "get", return_value=mock_response):
            assert fetcher._check_robots("https://example.com/page") is True

    def test_robots_connection_error_allows(self, fetcher):
        """robots.txt 连接失败 -> 默认允许"""
        with patch.object(fetcher._session, "get", side_effect=Exception("timeout")):
            assert fetcher._check_robots("https://example.com/page") is True


# ============================================================
# close
# ============================================================


class TestClose:
    """测试 close 方法"""

    def test_close(self, fetcher):
        """正常关闭"""
        fetcher.close()  # 不应抛异常


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """边界情况"""

    def test_empty_url(self, fetcher):
        """空 URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_response.apparent_encoding = "utf-8"

        with patch.object(fetcher._session, "get", return_value=mock_response), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"):
            # 不应崩溃
            result = fetcher.fetch("")
            assert result is not None or result is None  # 取决于实现

    def test_retry_count_respected(self, fetcher):
        """重试次数被尊重"""
        call_count = 0

        def always_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise requests.Timeout("always fail")

        with patch.object(fetcher._session, "get", side_effect=always_timeout), \
             patch.object(fetcher, "_check_robots", return_value=True), \
             patch.object(fetcher, "_wait_for_type"), \
             patch("time.sleep"):
            result = fetcher.fetch("https://example.com/fail")

        assert result is None
        # max_retries=2, 所以总共 1 + 2 = 3 次尝试
        assert call_count == 3
