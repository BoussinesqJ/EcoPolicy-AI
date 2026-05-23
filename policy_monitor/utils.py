# -*- coding: utf-8 -*-
"""
工具函数：URL 清洗、日期解析、哈希去重、文本清理
"""

import re
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse


def url_hash(url: str) -> str:
    """URL 去重哈希（SHA256 前 16 位）"""
    cleaned = url.strip().rstrip("/")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def normalize_url(base_url: str, href: str) -> str:
    """将相对 URL 转为绝对 URL"""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)


def extract_date(text: str) -> str:
    """
    从文本中提取日期，返回 YYYY-MM-DD 格式。
    支持：2026-05-15、2026/05/15、2026年05月15日、2026.05.15
    """
    if not text:
        return ""
    text = text.strip()

    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # YYYY/MM/DD
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # YYYY年MM月DD日
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # YYYY.MM.DD
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # YYYYMMDD
    m = re.search(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y}-{mo:02d}-{d:02d}"

    return ""


def clean_text(text: str) -> str:
    """清理文本：去除多余空白、换行、特殊字符"""
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_len: int = 200) -> str:
    """截断文本"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def get_domain(url: str) -> str:
    """提取域名"""
    parsed = urlparse(url)
    return parsed.netloc


def today_str() -> str:
    """今天日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def now_iso() -> str:
    """当前时间 ISO 格式"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
