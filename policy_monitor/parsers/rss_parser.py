# -*- coding: utf-8 -*-
"""
RSS/Atom 解析器
- 使用 feedparser 库
- 自动处理 RSS 2.0 / Atom / RDF
"""

import logging
from datetime import datetime

import feedparser

from utils import clean_text, now_iso

logger = logging.getLogger("policy_monitor")


def parse_rss(url: str, source_name: str, html_content: str = None) -> list[dict]:
    """
    解析 RSS/Atom feed。
    如果提供 html_content 则直接解析，否则通过 URL 获取。
    返回统一格式的政策列表。
    """
    try:
        if html_content:
            feed = feedparser.parse(html_content)
        else:
            feed = feedparser.parse(url)
    except Exception as e:
        logger.error(f"RSS 解析失败 ({url}): {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.warning(f"RSS 解析异常 ({url}): {feed.bozo_exception}")
        return []

    policies = []
    for entry in feed.entries:
        title = clean_text(getattr(entry, "title", ""))
        link = getattr(entry, "link", "")

        # 提取日期
        date_str = ""
        for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
            parsed = getattr(entry, date_field, None)
            if parsed:
                try:
                    date_str = datetime(*parsed[:6]).strftime("%Y-%m-%d")
                    break
                except Exception:
                    pass

        # 提取摘要
        summary = ""
        if hasattr(entry, "summary"):
            summary = clean_text(entry.summary)
        elif hasattr(entry, "description"):
            summary = clean_text(entry.description)

        if title and link:
            policies.append({
                "title": title,
                "url": link,
                "date": date_str,
                "source": source_name,
                "summary": summary[:500],
                "fetched_at": now_iso(),
            })

    logger.info(f"RSS 解析完成 ({source_name}): {len(policies)} 条")
    return policies
