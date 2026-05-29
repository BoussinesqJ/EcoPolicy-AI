# -*- coding: utf-8 -*-
"""
中国人大网 (npc.gov.cn) 专用解析器
- 解析首页政策列表（ul.list 元素）
- 处理相对 URL
- 提取日期（从 URL 路径中解析）
"""

import re
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import clean_text, now_iso

logger = logging.getLogger("policy_monitor")

# NPC 基础 URL
NPC_BASE = "http://www.npc.gov.cn"

# 需要排除的外部域名
EXTERNAL_DOMAINS = [
    "news.cn", "china.com.cn", "people.com.cn",
    "kdocs.cn", "xinhuanet.com", "scio.gov.cn",
    "gov.cn/zhibo", "gov.cn/live",
]

# 导航/非政策链接关键词
NAV_KEYWORDS = [
    "首页", "上一页", "下一页", "尾页", "更多", "返回",
    "关于我们", "联系我们", "网站地图", "登录", "注册",
    "信息公开", "政务公开", "在线办事", "互动平台",
    "图片", "视频", "直播", "英文",
    "全国人大常委会", "委员长会议",
]


def parse_npc(url: str, html_content: str, source_name: str = "中国人大网") -> list[dict]:
    """
    解析中国人大网政策列表页。
    从多个 ul.list 元素中提取政策链接。
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "lxml")
    policies = []
    seen_urls = set()

    # 收集所有 ul.list 和 ul.sliderRiglist 中的链接
    target_lists = soup.find_all("ul", class_="list")
    target_lists += soup.find_all("ul", class_="sliderRiglist")
    target_lists += soup.find_all("ul", class_="listP")
    target_lists += soup.find_all("ul", class_="fang3")

    for ul in target_lists:
        for li in ul.find_all("li"):
            a = li.find("a")
            if not a:
                continue

            href = a.get("href", "")
            title = clean_text(a.get_text())

            if not title or len(title) < 6:
                continue

            # 过滤导航链接
            if _is_nav_link(title):
                continue

            # 解析 URL
            abs_url = _resolve_url(url, href)
            if not abs_url:
                continue

            # 过滤外部链接
            if _is_external(abs_url):
                continue

            # 过滤已见 URL
            if abs_url in seen_urls:
                continue
            seen_urls.add(abs_url)

            # 从 URL 路径提取日期（格式：/202605/t20260527_455099.html）
            date_str = _extract_date_from_url(abs_url)

            policies.append({
                "title": title,
                "url": abs_url,
                "date": date_str,
                "source": source_name,
                "summary": "",
                "fetched_at": now_iso(),
            })

    logger.info(f"NPC 解析完成 ({source_name}): {len(policies)} 条")
    return policies


def _resolve_url(base_url: str, href: str) -> str | None:
    """解析相对/绝对 URL"""
    if not href or href == "#" or href.startswith("javascript"):
        return None

    # 已经是绝对 URL
    if href.startswith("http://") or href.startswith("https://"):
        return href

    # 相对 URL：基于 NPC 基础 URL 解析
    if href.startswith("./") or href.startswith("/"):
        return urljoin(NPC_BASE + "/npc/", href)

    return None


def _is_external(url: str) -> bool:
    """检查是否为外部链接"""
    for domain in EXTERNAL_DOMAINS:
        if domain in url:
            return True
    return False


def _is_nav_link(title: str) -> bool:
    """判断是否为导航链接"""
    for kw in NAV_KEYWORDS:
        if title == kw or title.startswith(kw):
            return True

    # 过滤纯年份
    if re.match(r"^\d{4}年?$", title):
        return True

    # 过滤短标题（人大常委会/全会等组织名）
    if len(title) <= 15 and ("委员会" in title or "全会" in title or "常委会" in title):
        return True

    return False


def _extract_date_from_url(url: str) -> str:
    """从 URL 路径提取日期（格式：/202605/t20260527_...）"""
    match = re.search(r"/(\d{6})/t(\d{8})_", url)
    if match:
        date_str = match.group(2)  # e.g., "20260527"
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    # 备用：/202604/ 格式
    match = re.search(r"/(\d{6})/", url)
    if match:
        ym = match.group(1)
        return f"{ym[:4]}-{ym[4:6]}"

    return ""
