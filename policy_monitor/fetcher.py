# -*- coding: utf-8 -*-
"""
安全 HTTP 客户端
- 随机 User-Agent
- 30-60 秒随机延迟
- robots.txt 检查
- 失败自动重试（指数退避）
- 单源失败不阻断其他源
"""

import time
import random
import logging
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import requests
import yaml

logger = logging.getLogger("policy_monitor")


class SafeFetcher:
    """安全的 HTTP 请求客户端"""

    def __init__(self, config: dict):
        safety = config.get("safety", {})
        self.min_delay = safety.get("min_delay_seconds", 30)
        self.max_delay = safety.get("max_delay_seconds", 60)
        self.timeout = safety.get("timeout_seconds", 15)
        self.max_retries = safety.get("max_retries", 2)
        self.respect_robots = safety.get("respect_robots", True)
        self.user_agents = safety.get("user_agents", [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
        ])
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_request_time = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    def _random_ua(self) -> str:
        return random.choice(self.user_agents)

    def _check_robots(self, url: str) -> bool:
        """检查 robots.txt 是否允许抓取该 URL"""
        if not self.respect_robots:
            return True

        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_cache:
            robots_url = f"{domain}/robots.txt"
            try:
                # 手动获取 robots.txt 内容（避免 RobotFileParser 的编码/网络问题）
                resp = self._session.get(robots_url, timeout=8)
                if resp.status_code == 200:
                    rp = RobotFileParser()
                    rp.parse(resp.text.splitlines())
                    self._robots_cache[domain] = rp
                    logger.info(f"robots.txt 已加载: {robots_url}")
                else:
                    # 404/403 等 = 无 robots.txt = 默认允许
                    logger.info(f"robots.txt 不可用 (HTTP {resp.status_code}): {robots_url}，默认允许")
                    self._robots_cache[domain] = None
            except Exception as e:
                logger.warning(f"无法读取 robots.txt ({robots_url}): {e}，默认允许")
                self._robots_cache[domain] = None

        rp = self._robots_cache[domain]
        if rp is None:
            return True
        return rp.can_fetch("*", url)

    def _wait(self):
        """智能等待：确保两次请求之间有足够的随机间隔"""
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            wait_time = delay - elapsed
            logger.info(f"等待 {wait_time:.1f} 秒（礼貌性延迟）...")
            time.sleep(wait_time)

    def fetch(self, url: str) -> str | None:
        """
        安全获取网页内容。
        返回 HTML 文本，失败返回 None。
        """
        # robots.txt 检查
        if not self._check_robots(url):
            logger.warning(f"robots.txt 禁止抓取: {url}")
            return None

        self._wait()

        self._session.headers["User-Agent"] = self._random_ua()

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"正在请求: {url} (第 {attempt + 1} 次)")
                resp = self._session.get(url, timeout=self.timeout, allow_redirects=True)
                self._last_request_time = time.time()

                if resp.status_code == 200:
                    # 自动检测编码
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp.text
                elif resp.status_code == 403:
                    logger.warning(f"403 Forbidden: {url} (可能触发反爬)")
                    return None
                elif resp.status_code == 404:
                    logger.warning(f"404 Not Found: {url}")
                    return None
                else:
                    logger.warning(f"HTTP {resp.status_code}: {url}")

            except requests.Timeout:
                logger.warning(f"请求超时: {url}")
            except requests.ConnectionError:
                logger.warning(f"连接失败: {url}")
            except Exception as e:
                logger.error(f"请求异常: {url} -> {e}")

            # 指数退避
            if attempt < self.max_retries:
                backoff = (2 ** attempt) * 5 + random.uniform(0, 3)
                logger.info(f"重试等待 {backoff:.1f} 秒...")
                time.sleep(backoff)

        logger.error(f"请求最终失败: {url}")
        return None

    def fetch_bytes(self, url: str) -> bytes | None:
        """获取二进制内容（用于 sitemap.xml 等）"""
        if not self._check_robots(url):
            return None

        self._wait()
        self._session.headers["User-Agent"] = self._random_ua()

        try:
            resp = self._session.get(url, timeout=self.timeout, allow_redirects=True)
            self._last_request_time = time.time()
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            logger.error(f"二进制请求失败: {url} -> {e}")

        return None

    def close(self):
        """关闭会话"""
        self._session.close()
