# -*- coding: utf-8 -*-
"""
Sitemap XML 解析器
- 解析 sitemap.xml 中的 <url><loc> 标签
- 等同于搜索引擎抓取行为，安全合规
"""

import logging

from bs4 import BeautifulSoup

from utils import normalize_url, now_iso

logger = logging.getLogger("policy_monitor")


def parse_sitemap(url: str, xml_content: str, source_name: str) -> list[dict]:
    """
    解析 sitemap.xml。
    返回统一格式的政策列表（仅含 URL，标题需后续抓取）。
    """
    if not xml_content:
        return []

    soup = BeautifulSoup(xml_content, "lxml-xml")
    urls = soup.find_all("url")

    if not urls:
        # 可能是 sitemap index（嵌套 sitemap）
        sitemaps = soup.find_all("sitemap")
        if sitemaps:
            logger.info(f"Sitemap index 发现 {len(sitemaps)} 个子 sitemap ({source_name})")
            # 返回子 sitemap 的 URL，由调用方递归处理
            sub_urls = []
            for sm in sitemaps:
                loc = sm.find("loc")
                if loc:
                    sub_urls.append({
                        "title": f"[Sitemap] {loc.get_text().strip()}",
                        "url": loc.get_text().strip(),
                        "date": "",
                        "source": source_name,
                        "summary": "",
                        "fetched_at": now_iso(),
                        "_is_sitemap": True,
                    })
            return sub_urls
        logger.warning(f"Sitemap 为空 ({source_name}): {url}")
        return []

    policies = []
    for url_entry in urls:
        loc = url_entry.find("loc")
        if not loc:
            continue

        page_url = loc.get_text().strip()
        if not page_url.startswith("http"):
            continue

        # 提取 lastmod 作为日期
        lastmod = url_entry.find("lastmod")
        date_str = ""
        if lastmod:
            from utils import extract_date
            date_str = extract_date(lastmod.get_text())

        policies.append({
            "title": f"[待抓取] {page_url.split('/')[-1]}",
            "url": page_url,
            "date": date_str,
            "source": source_name,
            "summary": "",
            "fetched_at": now_iso(),
        })

    logger.info(f"Sitemap 解析完成 ({source_name}): {len(policies)} 条 URL")
    return policies
