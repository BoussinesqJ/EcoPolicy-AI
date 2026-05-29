# -*- coding: utf-8 -*-
"""
HTML 列表页解析器
- 根据 CSS 选择器提取政策列表
- 自动提取标题、链接、日期
"""

import re
import logging

from bs4 import BeautifulSoup

from utils import clean_text, normalize_url, extract_date, now_iso

logger = logging.getLogger("policy_monitor")


def parse_html(url: str, html_content: str, source_name: str, selectors: dict) -> list[dict]:
    """
    解析 HTML 列表页。
    selectors: {"list": "CSS选择器", ...}
    返回统一格式的政策列表。
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "lxml")
    list_selector = selectors.get("list", "a")

    # 分离多个选择器（用逗号分隔）
    links = soup.select(list_selector)

    if not links:
        # 降级：尝试常见的列表选择器
        fallback_selectors = [
            "ul li a",
            "table td a",
            ".list a",
            ".news a",
            "a[href*='content']",
            "a[href*='art']",
            "a[href*='zc']",
        ]
        for sel in fallback_selectors:
            links = soup.select(sel)
            if links:
                logger.info(f"降级使用选择器: {sel} ({source_name})")
                break

    if not links:
        logger.warning(f"未找到链接 ({source_name}): {url}")
        return []

    policies = []
    seen_urls = set()

    for a_tag in links:
        href = a_tag.get("href", "")
        if not href or href == "#" or href.startswith("javascript"):
            continue

        abs_url = normalize_url(url, href)
        if abs_url in seen_urls:
            continue
        seen_urls.add(abs_url)

        # 提取标题
        title = clean_text(a_tag.get_text())
        if not title or len(title) < 4:
            continue

        # 过滤非政策链接（导航、页脚等）
        if _is_navigation(title, href):
            continue

        # 尝试从链接周围提取日期
        date_str = _extract_nearby_date(a_tag)

        policies.append({
            "title": title,
            "url": abs_url,
            "date": date_str,
            "source": source_name,
            "summary": "",
            "fetched_at": now_iso(),
        })

    logger.info(f"HTML 解析完成 ({source_name}): {len(policies)} 条")
    return policies


def _is_navigation(title: str, href: str = "") -> bool:
    """判断是否为导航链接（非政策内容）"""
    # 核心规则：政策标题通常 > 12 字符，短标题几乎都是导航项
    if len(title) <= 12:
        return True

    # URL 模式过滤：纯分类页/索引页链接
    if href:
        # 以 / 结尾的纯目录链接（无具体文件名）
        if href.rstrip("/").endswith("/index") or href.endswith("/"):
            # 除非 URL 包含日期模式（真实政策链接）
            if not re.search(r"/\d{6}/", href):
                return True

    nav_keywords = [
        "首页", "上一页", "下一页", "尾页", "更多", "返回",
        "网站地图", "联系我们", "关于我们", "首页 >>",
        ">>", "首页>", "登录", "注册", "搜索",
        # 导航分类
        "信息公开", "专题专栏", "科技统计", "预决算",
        "新闻动态", "司局机构", "科技视频", "科普服务",
        "在线办事", "互动平台", "职能介绍", "部长信箱",
        "舆论场", "政策解读", "公开目录",
        # 政府网站常见分类标签（非政策）
        "发改委令", "规范性文件", "规划文本", "规章文件",
        "政府信息公开", "政务公开", "文件发布",
    ]
    for kw in nav_keywords:
        if title == kw or title.startswith(kw):
            return True

    # 过滤纯年份标签（如 "2024年", "2025年"）
    import re
    if re.match(r"^\d{4}年?$", title):
        return True
    if re.match(r"^\d{4}年之前$", title):
        return True

    return False


def _extract_nearby_date(a_tag) -> str:
    """从链接的父元素或兄弟元素中提取日期"""
    # 方法1：同级元素
    parent = a_tag.parent
    if parent:
        text = parent.get_text()
        date = extract_date(text)
        if date:
            return date

    # 方法2：链接的 title 属性
    title_attr = a_tag.get("title", "")
    date = extract_date(title_attr)
    if date:
        return date

    # 方法3：链接本身文本
    date = extract_date(a_tag.get_text())
    return date
