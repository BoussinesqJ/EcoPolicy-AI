# -*- coding: utf-8 -*-
"""
用户上传政策解析器
支持三种输入方式：
  1. URL 链接 — 抓取并解析网页内容
  2. 本地文件 — 解析 PDF / Word / 纯文本
  3. 粘贴文本 — 直接使用
"""

import re
import logging
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("policy_monitor")


# ============================================================
# 统一输出格式
# ============================================================

def _make_policy_dict(title: str, content: str, source: str, date: str = None) -> dict:
    """构造统一的政策字典"""
    return {
        "title": title or "未命名政策",
        "url": source,
        "date": date or "",
        "source": source,
        "summary": content[:2000] if content else "",
        "content": content or "",
        "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ============================================================
# 1. URL 解析
# ============================================================

def parse_url(url: str, timeout: int = 30) -> dict:
    """
    从 URL 抓取并解析政策内容。
    政府网站、新闻网站等通用解析。
    """
    logger.info(f"正在抓取: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
    except requests.RequestException as e:
        logger.error(f"抓取失败: {e}")
        raise ValueError(f"无法访问 URL: {url}\n错误: {e}")

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # 提取标题
    title = _extract_title(soup)

    # 提取正文
    content = _extract_main_content(soup)

    # 提取日期
    date = _extract_date(soup, html)

    if not content or len(content) < 50:
        logger.warning(f"正文内容过短 ({len(content)} 字符)，可能解析失败")

    return _make_policy_dict(title, content, url, date)


def _extract_title(soup: BeautifulSoup) -> str:
    """提取页面标题"""
    # 优先从 h1 提取
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if len(title) > 4:
            return title

    # 其次从 title 标签
    if soup.title:
        title = soup.title.get_text(strip=True)
        # 去除网站名称后缀
        for sep in [" - ", " — ", " – ", " | ", " _ ", "·"]:
            if sep in title:
                title = title.split(sep)[0].strip()
        if len(title) > 4:
            return title

    return ""


def _extract_main_content(soup: BeautifulSoup) -> str:
    """提取正文内容（适配政府网站）"""
    # 移除无用标签
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # 候选容器选择器（按优先级）
    selectors = [
        # 政府网站常见正文容器
        ".TRS_Editor",
        ".content",
        ".article-content",
        ".policy-content",
        ".main-content",
        "#zoom",
        "#content",
        ".text_content",
        ".news-content",
        ".detail-content",
        "article",
        ".pages_content",
        # 通用
        "main",
        ".main",
    ]

    for sel in selectors:
        container = soup.select_one(sel)
        if container:
            text = container.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return _clean_content(text)

    # 降级：取 body 全文
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        return _clean_content(text)

    return ""


def _clean_content(text: str) -> str:
    """清理正文内容"""
    # 移除多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 移除行首行尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # 移除广告/导航关键词行
    skip_patterns = [
        r"^(首页|网站地图|联系我们|关于我们|版权所有|ICP备)",
        r"^(上一篇|下一篇|相关阅读|推荐阅读)",
        r"^(分享到|打印|关闭|收藏)",
    ]
    lines = text.split("\n")
    filtered = []
    for line in lines:
        if any(re.match(p, line.strip()) for p in skip_patterns):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _extract_date(soup: BeautifulSoup, html: str) -> str:
    """提取发布日期"""
    # 方法1: meta 标签
    for meta_name in ["publishdate", "pubdate", "article:published_time", "date"]:
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            date = _parse_date(meta["content"])
            if date:
                return date

    # 方法2: 从正文区域提取日期
    date_patterns = [
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, html[:5000])  # 只搜索前 5000 字符
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y}-{mo:02d}-{d:02d}"

    return ""


def _parse_date(text: str) -> str:
    """解析日期字符串"""
    if not text:
        return ""
    text = text.strip()[:20]  # 只取前 20 字符

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y}-{mo:02d}-{d:02d}"

    m = re.search(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y}-{mo:02d}-{d:02d}"

    return ""


# ============================================================
# 2. 本地文件解析
# ============================================================

def parse_file(file_path: str) -> dict:
    """
    解析本地政策文件。
    支持: .txt / .md / .pdf / .docx
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()
    logger.info(f"正在解析文件: {path.name} ({suffix})")

    if suffix in (".txt", ".md", ".text"):
        content = _parse_text_file(path)
    elif suffix == ".pdf":
        content = _parse_pdf(path)
    elif suffix in (".doc", ".docx"):
        content = _parse_word(path)
    else:
        # 尝试作为纯文本读取
        logger.warning(f"未知文件类型 {suffix}，尝试作为纯文本解析")
        content = _parse_text_file(path)

    # 从文件名提取标题
    title = path.stem
    # 尝试从内容第一行提取标题
    if content:
        first_line = content.split("\n")[0].strip()
        if 4 < len(first_line) < 100:
            title = first_line

    return _make_policy_dict(title, content, str(path))


def _parse_text_file(path: Path) -> str:
    """解析纯文本文件"""
    encodings = ["utf-8", "gbk", "gb2312", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解码文件: {path}")


def _parse_pdf(path: Path) -> str:
    """解析 PDF 文件"""
    try:
        import PyPDF2
    except ImportError:
        raise ImportError(
            "需要安装 PyPDF2 库才能解析 PDF 文件\n"
            "运行: pip install PyPDF2"
        )

    text_parts = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n".join(text_parts)


def _parse_word(path: Path) -> str:
    """解析 Word 文件"""
    try:
        import docx
    except ImportError:
        raise ImportError(
            "需要安装 python-docx 库才能解析 Word 文件\n"
            "运行: pip install python-docx"
        )

    doc = docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


# ============================================================
# 3. 粘贴文本
# ============================================================

def parse_text(text: str, title: str = None) -> dict:
    """
    直接使用用户粘贴的政策文本。
    """
    if not text or len(text.strip()) < 20:
        raise ValueError("政策文本过短，请提供完整的政策内容")

    # 尝试从文本第一行提取标题
    if not title:
        lines = text.strip().split("\n")
        first_line = lines[0].strip()
        if 4 < len(first_line) < 100:
            title = first_line
        else:
            title = "用户输入政策"

    return _make_policy_dict(title, text, "用户粘贴输入")
