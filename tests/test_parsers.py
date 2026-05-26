# -*- coding: utf-8 -*-
"""
parsers 测试套件

测试解析器：
  - user_upload.py: parse_url / parse_file / parse_text
  - api_parser.py: parse_api
  - html_parser.py: parse_html
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from policy_monitor.parsers.user_upload import (
    parse_url,
    parse_file,
    parse_text,
    _make_policy_dict,
    _extract_title,
    _extract_main_content,
    _clean_content,
)
from policy_monitor.parsers.api_parser import parse_api
from policy_monitor.parsers.html_parser import parse_html


class TestMakePolicyDict:
    """测试 _make_policy_dict 辅助函数"""

    def test_basic_creation(self):
        """测试基本创建"""
        result = _make_policy_dict("测试标题", "测试内容", "测试来源")
        assert result["title"] == "测试标题"
        assert result["content"] == "测试内容"
        assert result["source"] == "测试来源"

    def test_empty_title_defaults(self):
        """测试空标题默认值"""
        result = _make_policy_dict("", "内容", "来源")
        assert result["title"] == "未命名政策"

    def test_summary_truncation(self):
        """测试摘要截断"""
        long_content = "x" * 3000
        result = _make_policy_dict("标题", long_content, "来源")
        assert len(result["summary"]) <= 2000

    def test_date_handling(self):
        """测试日期处理"""
        result = _make_policy_dict("标题", "内容", "来源", "2026-05-20")
        assert result["date"] == "2026-05-20"

    def test_none_date(self):
        """测试空日期"""
        result = _make_policy_dict("标题", "内容", "来源", None)
        assert result["date"] == ""


class TestParseText:
    """测试 parse_text 函数"""

    def test_basic_text(self):
        """测试基本文本解析"""
        text = "关于加快推进人工智能产业发展的实施意见\n\n支持大模型、深度学习等关键技术研究"
        result = parse_text(text)
        assert "title" in result
        assert "content" in result
        assert result["content"] == text

    def test_title_from_first_line(self):
        """测试从第一行提取标题"""
        text = "关于加快推进人工智能产业发展的实施意见\n\n正文内容..."
        result = parse_text(text)
        assert result["title"] == "关于加快推进人工智能产业发展的实施意见"

    def test_custom_title(self):
        """测试自定义标题"""
        text = "这是一段政策内容，包含足够多的字符用于测试"
        result = parse_text(text, title="自定义标题")
        assert result["title"] == "自定义标题"

    def test_short_text_raises_error(self):
        """测试过短文本抛出异常"""
        with pytest.raises(ValueError, match="过短"):
            parse_text("短")

    def test_empty_text_raises_error(self):
        """测试空文本抛出异常"""
        with pytest.raises(ValueError):
            parse_text("")


class TestParseFile:
    """测试 parse_file 函数"""

    def test_parse_text_file(self, tmp_path):
        """测试解析纯文本文件"""
        text_file = tmp_path / "policy.txt"
        text_file.write_text("关于加快推进人工智能产业发展的实施意见\n\n正文内容...", encoding="utf-8")
        
        result = parse_file(str(text_file))
        assert "title" in result
        assert "人工智能" in result["content"]

    def test_parse_markdown_file(self, tmp_path):
        """测试解析 Markdown 文件"""
        md_file = tmp_path / "policy.md"
        md_file.write_text("# 政策标题\n\n正文内容...", encoding="utf-8")
        
        result = parse_file(str(md_file))
        assert "title" in result

    def test_nonexistent_file_raises_error(self):
        """测试不存在的文件抛出异常"""
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/file.txt")

    def test_encoding_gbk(self, tmp_path):
        """测试 GBK 编码文件"""
        gbk_file = tmp_path / "policy_gbk.txt"
        gbk_file.write_text("关于人工智能的政策", encoding="gbk")
        
        result = parse_file(str(gbk_file))
        assert "人工智能" in result["content"]


class TestExtractTitle:
    """测试 _extract_title 函数"""

    def test_h1_title(self, sample_html):
        """测试从 h1 提取标题"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_html, "lxml")
        title = _extract_title(soup)
        assert title == "关于加快推进人工智能产业发展的实施意见"

    def test_title_tag(self):
        """测试从 title 标签提取"""
        html = "<html><head><title>关于加快推进人工智能产业发展的实施意见 - 网站名称</title></head><body></body></html>"
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        title = _extract_title(soup)
        assert title == "关于加快推进人工智能产业发展的实施意见"

    def test_no_title(self):
        """测试无标题"""
        html = "<html><head></head><body></body></html>"
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        title = _extract_title(soup)
        assert title == ""


class TestExtractMainContent:
    """测试 _extract_main_content 函数"""

    def test_content_extraction(self, sample_html):
        """测试正文提取"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_html, "lxml")
        content = _extract_main_content(soup)
        assert "人工智能" in content
        assert "500亿元" in content

    def test_empty_body(self):
        """测试空 body"""
        html = "<html><head></head><body></body></html>"
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        content = _extract_main_content(soup)
        assert content == ""


class TestCleanContent:
    """测试 _clean_content 函数"""

    def test_remove_extra_newlines(self):
        """测试移除多余空行"""
        text = "第一行\n\n\n\n\n第二行"
        result = _clean_content(text)
        assert "\n\n\n" not in result

    def test_remove_navigation(self):
        """测试移除导航文字"""
        text = "正文内容\n首页\n网站地图\n联系我们"
        result = _clean_content(text)
        assert "首页" not in result
        assert "正文内容" in result


class TestParseApi:
    """测试 parse_api 函数"""

    def test_state_council_format(self, sample_api_response):
        """测试国务院 API 格式"""
        policies = parse_api(
            "https://example.com/api",
            sample_api_response,
            "国务院-测试"
        )
        assert len(policies) == 1
        assert policies[0]["title"] == "关于加快推进人工智能产业发展的实施意见"

    def test_empty_response(self):
        """测试空响应"""
        policies = parse_api("https://example.com/api", "", "测试")
        assert len(policies) == 0

    def test_invalid_json(self):
        """测试无效 JSON"""
        policies = parse_api("https://example.com/api", "not json", "测试")
        assert len(policies) == 0

    def test_missing_fields(self):
        """测试缺少字段"""
        json_str = '{"searchVO": {"listVO": [{"title": "测试"}]}}'
        policies = parse_api("https://example.com/api", json_str, "测试")
        # 缺少 url 的记录应该被跳过
        assert len(policies) == 0


class TestParseHtml:
    """测试 parse_html 函数"""

    def test_basic_html_parsing(self, sample_html):
        """测试基本 HTML 解析"""
        selectors = {"list": "a[href]"}
        policies = parse_html(
            "https://example.com",
            sample_html,
            "测试来源",
            selectors
        )
        # 示例 HTML 没有链接，应该返回空
        assert isinstance(policies, list)

    def test_html_with_links(self):
        """测试带链接的 HTML"""
        html = """
        <html>
        <body>
            <ul>
                <li><a href="/policy/1">关于加快推进人工智能产业发展的第一条实施意见</a></li>
                <li><a href="/policy/2">关于加快推进人工智能产业发展的第二条实施意见</a></li>
            </ul>
        </body>
        </html>
        """
        selectors = {"list": "ul li a"}
        policies = parse_html("https://example.com", html, "测试", selectors)
        assert len(policies) == 2

    def test_empty_html(self):
        """测试空 HTML"""
        policies = parse_html("https://example.com", "", "测试", {})
        assert len(policies) == 0

    def test_navigation_filtering(self):
        """测试导航链接过滤"""
        html = """
        <html>
        <body>
            <a href="/">首页</a>
            <a href="/about">关于我们</a>
            <a href="/policy/1">关于加快推进人工智能产业发展的实施意见</a>
        </body>
        </html>
        """
        selectors = {"list": "a"}
        policies = parse_html("https://example.com", html, "测试", selectors)
        # 导航链接应该被过滤
        titles = [p["title"] for p in policies]
        assert "首页" not in titles
        assert "关于我们" not in titles
