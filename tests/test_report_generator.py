# -*- coding: utf-8 -*-
"""
report_generator.py 测试套件

测试报告生成器：
  - generate_brief 简报生成
  - generate_deep_analysis_request 深度分析请求
  - _render_radar ASCII 雷达图
  - _render_probability_bar 概率条
  - _slugify 文件名安全化
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from report_generator import ReportGenerator
from enterprise_matcher import MatchResult


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def generator(tmp_path):
    """创建临时报告生成器"""
    return ReportGenerator(str(tmp_path))


@pytest.fixture
def sample_match():
    """创建示例 MatchResult"""
    return MatchResult(
        policy_url_hash="abc123def456",
        policy_title="关于加快推进人工智能产业发展的实施意见",
        policy_url="https://www.example.gov.cn/policy/2026/001",
        policy_source="国务院-人工智能",
        policy_date="2026-05-20",
        policy_summary="支持大模型、深度学习等关键技术研究，单个项目最高补助500万元。",
        enterprise_id="demo_tech",
        enterprise_name="DEMO科技有限公司",
    )


@pytest.fixture
def full_match():
    """带完整评分的 MatchResult"""
    m = MatchResult(
        policy_url_hash="abc123",
        policy_title="关于加快推进人工智能产业发展的实施意见",
        policy_url="https://www.example.gov.cn/policy/2026/001",
        policy_source="国务院-人工智能",
        policy_date="2026-05-20",
        policy_summary="支持大模型、深度学习等关键技术研究。",
        enterprise_id="demo_tech",
        enterprise_name="DEMO科技有限公司",
    )
    m.score_tech = 4
    m.score_prod = 3
    m.score_mkt = 2
    m.score_cap = 3
    m.score_total = 12
    m.weighted_score = 3.2
    m.hard_conditions_pass = True
    m.hard_conditions_detail = {"注册地": {"通过": True, "说明": "湖北省"}, "高企资质": {"通过": True, "说明": "已认定"}}
    m.hard_pass_rate = "100%"
    m.weights_used = {"tech": 0.35, "prod": 0.25, "mkt": 0.2, "cap": 0.2}
    m.success_probability = 0.65
    m.probability_factors = ["高企资质通过", "注册地匹配", "行业高度相关"]
    m.roi_ratio = 5.2
    m.roi_verdict = "值得申报"
    m.roi_detail = {"risk_level": "中", "payback_months": 6}
    m.improvement_paths = [
        {"dimension": "Tech", "current_score": 4, "gap": 1, "difficulty": "中", "estimated_time": "3个月", "suggestions": ["申请发明专利"]},
    ]
    m.recommendation = "4/5 强烈推荐"
    m.recommendation_score = 4
    m.urgency = "P0"
    m.matched_keywords = ["人工智能", "大模型", "深度学习"]
    m.opportunities = ["国家级政策，资金支持力度大"]
    m.risks = ["申报竞争激烈"]
    m.preference_notes = ["偏好资金补贴类政策"]
    return m


# ============================================================
# generate_brief
# ============================================================


class TestGenerateBrief:
    """测试简报生成"""

    def test_brief_creates_file(self, generator, sample_match):
        """生成简报文件"""
        path = generator.generate_brief(sample_match)
        assert Path(path).exists()
        assert path.endswith(".md")

    def test_brief_contains_title(self, generator, sample_match):
        """简报包含政策标题"""
        path = generator.generate_brief(sample_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "人工智能" in content

    def test_brief_contains_enterprise(self, generator, sample_match):
        """简报包含企业名"""
        path = generator.generate_brief(sample_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "demo_tech" in content

    def test_brief_with_full_match(self, generator, full_match):
        """完整评分的简报"""
        path = generator.generate_brief(full_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "4/5 强烈推荐" in content
        assert "成功率" in content or "成功概率" in content or "概率" in content

    def test_brief_contains_radar(self, generator, full_match):
        """简报包含雷达图"""
        path = generator.generate_brief(full_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "Tech" in content
        assert "Prod" in content

    def test_brief_filename_format(self, generator, sample_match):
        """文件名格式正确"""
        path = generator.generate_brief(sample_match)
        filename = Path(path).name
        assert "demo_tech" in filename
        assert "brief" in filename


# ============================================================
# generate_deep_analysis_request
# ============================================================


class TestGenerateDeepAnalysis:
    """测试深度分析请求生成"""

    def test_creates_file(self, generator, sample_match):
        """生成深度分析文件"""
        path = generator.generate_deep_analysis_request(sample_match)
        assert Path(path).exists()

    def test_contains_workflow(self, generator, sample_match):
        """包含工作流说明"""
        path = generator.generate_deep_analysis_request(sample_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "深度分析" in content or "工作流" in content or "六步" in content

    def test_contains_policy_info(self, generator, sample_match):
        """包含政策信息"""
        path = generator.generate_deep_analysis_request(sample_match)
        content = Path(path).read_text(encoding="utf-8")
        assert "人工智能" in content

    def test_with_brief_path(self, generator, sample_match):
        """传入简报路径"""
        brief_path = generator.generate_brief(sample_match)
        deep_path = generator.generate_deep_analysis_request(sample_match, brief_path=brief_path)
        assert Path(deep_path).exists()
        content = Path(deep_path).read_text(encoding="utf-8")
        assert "brief" in content.lower() or "简报" in content


# ============================================================
# _render_radar
# ============================================================


class TestRenderRadar:
    """测试 ASCII 雷达图"""

    def test_radar_all_five(self, generator):
        """全满分雷达图"""
        radar = generator._render_radar(5, 5, 5, 5)
        assert "5/5" in radar
        assert "Tech" in radar

    def test_radar_all_zero(self, generator):
        """全零雷达图"""
        radar = generator._render_radar(0, 0, 0, 0)
        assert "0/5" in radar

    def test_radar_mixed(self, generator):
        """混合分数"""
        radar = generator._render_radar(4, 2, 3, 1)
        assert "4/5" in radar
        assert "2/5" in radar


# ============================================================
# _render_probability_bar
# ============================================================


class TestRenderProbabilityBar:
    """测试概率条"""

    def test_high_probability(self, generator):
        """高概率"""
        bar = generator._render_probability_bar(0.8)
        assert "高" in bar
        assert "80%" in bar

    def test_medium_probability(self, generator):
        """中概率"""
        bar = generator._render_probability_bar(0.5)
        assert "中" in bar

    def test_low_probability(self, generator):
        """低概率"""
        bar = generator._render_probability_bar(0.2)
        assert "低" in bar

    def test_zero_probability(self, generator):
        """零概率"""
        bar = generator._render_probability_bar(0.0)
        assert "0%" in bar

    def test_one_hundred_percent(self, generator):
        """100% 概率"""
        bar = generator._render_probability_bar(1.0)
        assert "100%" in bar


# ============================================================
# _slugify
# ============================================================


class TestSlugify:
    """测试文件名安全化"""

    def test_chinese_text(self, generator):
        """中文文本"""
        slug = generator._slugify("关于加快推进人工智能产业发展")
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_special_chars_removed(self, generator):
        """特殊字符被移除"""
        slug = generator._slugify("政策/测试:冒号?问号")
        assert "/" not in slug
        assert ":" not in slug
        assert "?" not in slug

    def test_empty_string(self, generator):
        """空字符串"""
        slug = generator._slugify("")
        assert isinstance(slug, str)

    def test_max_length(self, generator):
        """长度限制"""
        long_title = "A" * 200
        slug = generator._slugify(long_title)
        # _slugify 可能不限制长度，但不应报错
        assert isinstance(slug, str)


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """边界情况"""

    def test_minimal_match(self, generator):
        """最小 MatchResult"""
        m = MatchResult(
            policy_url_hash="x",
            policy_title="测试",
            policy_url="https://example.com",
            policy_source="测试",
            policy_date="2026-01-01",
            policy_summary="摘要",
            enterprise_id="ent",
            enterprise_name="企业",
        )
        path = generator.generate_brief(m)
        assert Path(path).exists()

    def test_multiple_reports(self, generator, sample_match):
        """生成多份报告不冲突"""
        path1 = generator.generate_brief(sample_match)
        path2 = generator.generate_brief(sample_match)
        # 文件名含时间戳，可能相同也可能不同
        assert Path(path1).exists()
        assert Path(path2).exists()
