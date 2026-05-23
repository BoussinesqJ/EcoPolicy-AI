# -*- coding: utf-8 -*-
"""
JSON API 解析器
- 用于国务院搜索 API 等返回 JSON 的数据源
- 最安全的抓取方式（等同于官方搜索功能）
"""

import json
import logging
from datetime import datetime

from utils import clean_text, now_iso

logger = logging.getLogger("policy_monitor")


def parse_api(url: str, json_text: str, source_name: str) -> list[dict]:
    """
    解析 JSON API 返回。
    特别适配国务院搜索 API 的返回格式。
    """
    if not json_text:
        return []

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败 ({source_name}): {e}")
        return []

    policies = []

    # 国务院搜索 API 格式
    search_vo = data.get("searchVO") or {}
    results = search_vo.get("listVO") or []

    if results:
        for item in results:
            title = clean_text(item.get("title", ""))
            page_url = item.get("url", "")

            # 日期：毫秒时间戳转日期
            pub_time = item.get("pubtime", "")
            date_str = ""
            if pub_time:
                try:
                    ts = int(pub_time) / 1000  # 毫秒转秒
                    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    date_str = str(pub_time)

            summary = clean_text(item.get("summary", "") or item.get("description", ""))

            if title and page_url:
                policies.append({
                    "title": title,
                    "url": page_url,
                    "date": date_str,
                    "source": source_name,
                    "summary": summary[:500],
                    "fetched_at": now_iso(),
                })
    else:
        # 通用 JSON 数组格式（备用）
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    title = clean_text(item.get("title", item.get("name", "")))
                    page_url = item.get("url", item.get("link", ""))
                    if title and page_url:
                        policies.append({
                            "title": title,
                            "url": page_url,
                            "date": item.get("date", ""),
                            "source": source_name,
                            "summary": clean_text(item.get("summary", ""))[:500],
                            "fetched_at": now_iso(),
                        })

    logger.info(f"API 解析完成 ({source_name}): {len(policies)} 条")
    return policies
