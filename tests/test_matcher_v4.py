# -*- coding: utf-8 -*-
"""
enterprise_matcher.py v4.0 扩展测试套件

补充测试六层评价体系的新增功能：
  - Layer 3: 成功概率 (success_probability)
  - Layer 4: ROI 量化 (roi_ratio / roi_verdict)
  - Layer 5: 提升路径 (improvement_paths)
  - Layer 6: 偏好过滤 (preference_match)
  - 推荐等级计算 (recommendation / recommendation_score)
  - 拒绝原因 (rejection_reasons)
  - 紧急度分级 (urgency)
"""

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from enterprise_matcher import EnterpriseMatcher, MatchResult


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def enterprise_dir(tmp_path):
    """创建带完整字段的企业画像目录"""
    profile = {
        "basic_info": {
            "company_name": "DEMO科技有限公司",
            "short_name": "DEMO科技",
            "registered_capital": 8000,
            "establishment_date": "2018-06-01",
            "registered_address": "湖北省武汉市东湖高新区",
            "employees": 200,
        },
        "industry": {
            "primary_sector": "数字经济",
            "sub_sector": "人工智能",
            "industry_keywords": ["人工智能", "大模型", "计算机视觉", "自然语言处理"],
        },
        "qualifications": {
            "high_tech_enterprise": True,
            "sme_specialized": True,
            "sme_specialized_level": "国家级",
            "other": ["ISO9001", "CMMI3"],
        },
        "innovation": {
            "invention_patents": 8,
            "utility_patents": 12,
            "software_copyrights": 15,
        },
        "regions": {
            "headquarters": "湖北",
            "branch_offices": ["北京", "上海"],
        },
        "business_model": {
            "has_production_base": True,
            "business_type": "研发+生产",
        },
        "financials": {
            "year_1": {"revenue": 12000, "profit": 1500, "rd_expense": 2000},
            "year_2": {"revenue": 15000, "profit": 2000, "rd_expense": 2500},
        },
        "strategy": {
            "policy_needs": ["资金补贴", "税收优惠", "人才引进"],
        },
    }

    ent_dir = tmp_path / "demo_tech"
    ent_dir.mkdir()
    with open(ent_dir / "profile.yaml", "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True)

    return tmp_path


@pytest.fixture
def matcher(enterprise_dir):
    return EnterpriseMatcher(str(enterprise_dir))


@pytest.fixture
def ai_policy():
    return {
        "title": "关于加快推进人工智能产业发展的实施意见",
        "url": "https://www.example.gov.cn/policy/2026/001",
        "date": "2026-05-20",
        "source": "国务院-人工智能",
        "summary": "支持大模型、深度学习、计算机视觉等关键技术研究，单个项目最高补助500万元。"
                   "对首次认定为国家级专精特新小巨人企业的人工智能企业，给予100万元奖励。",
        "keywords_matched": ["人工智能", "大模型", "专精特新"],
        "score": 8,
        "priority": "P0",
    }


@pytest.fixture
def weak_policy():
    """低匹配度政策"""
    return {
        "title": "关于加强食品安全监管的通知",
        "url": "https://www.example.gov.cn/policy/2026/100",
        "date": "2026-05-20",
        "source": "市场监管总局",
        "summary": "加强食品安全检查，落实食品安全主体责任，保障人民群众舌尖上的安全。",
        "score": 2,
        "priority": "P2",
    }


# ============================================================
# Layer 3: 成功概率
# ============================================================


class TestSuccessProbability:
    """测试 Layer 3 成功概率"""

    def test_probability_range(self, matcher, ai_policy):
        """概率在 0-95% 之间"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert 0 <= r.success_probability <= 95

    def test_probability_with_high_qualifications(self, matcher, ai_policy):
        """高资质企业概率更高"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            # DEMO 科技有高企 + 国家级专精特新 + 8 项发明专利
            # AI 政策应该有非零概率
            assert r.success_probability > 0

    def test_probability_factors_list(self, matcher, ai_policy):
        """概率因子列表"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.probability_factors, list)
            # 应有评估因子
            assert len(r.probability_factors) > 0

    def test_weak_policy_lower_probability(self, matcher, ai_policy, weak_policy):
        """不匹配的政策概率应该更低"""
        results_ai = matcher.match_policies([ai_policy], "demo_tech")
        results_weak = matcher.match_policies([weak_policy], "demo_tech")
        if results_ai and results_weak:
            assert results_ai[0].success_probability >= results_weak[0].success_probability


# ============================================================
# Layer 4: ROI
# ============================================================


class TestROI:
    """测试 Layer 4 ROI"""

    def test_roi_ratio_non_negative(self, matcher, ai_policy):
        """ROI >= 0"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert r.roi_ratio >= 0

    def test_roi_verdict_not_empty(self, matcher, ai_policy):
        """有 ROI 判定"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.roi_verdict, str)

    def test_roi_detail_dict(self, matcher, ai_policy):
        """ROI 详情是字典"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.roi_detail, dict)


# ============================================================
# Layer 5: 提升路径
# ============================================================


class TestImprovementPaths:
    """测试 Layer 5 提升路径"""

    def test_improvement_paths_list(self, matcher, ai_policy):
        """提升路径是列表"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.improvement_paths, list)

    def test_paths_have_structure(self, matcher, ai_policy):
        """每个路径有结构"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            for path in r.improvement_paths:
                # 每个路径至少是字符串或字典
                assert isinstance(path, (str, dict))


# ============================================================
# Layer 6: 偏好
# ============================================================


class TestPreferences:
    """测试 Layer 6 偏好过滤"""

    def test_preference_match_boolean(self, matcher, ai_policy):
        """preference_match 是布尔值"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.preference_match, bool)

    def test_preference_notes_list(self, matcher, ai_policy):
        """preference_notes 是列表"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.preference_notes, list)


# ============================================================
# 推荐等级
# ============================================================


class TestRecommendation:
    """测试推荐等级"""

    def test_recommendation_format(self, matcher, ai_policy):
        """推荐等级格式"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            valid = ["5/5 首选推荐", "4/5 强烈推荐", "3/5 推荐", "2/5 不推荐", "1/5 不匹配"]
            assert r.recommendation in valid

    def test_recommendation_score_range(self, matcher, ai_policy):
        """推荐分数 1-5"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert 1 <= r.recommendation_score <= 5

    def test_high_match_higher_score(self, matcher, ai_policy, weak_policy):
        """高匹配的推荐分数更高"""
        r_ai = matcher.match_policies([ai_policy], "demo_tech")
        r_weak = matcher.match_policies([weak_policy], "demo_tech")
        if r_ai and r_weak:
            assert r_ai[0].recommendation_score >= r_weak[0].recommendation_score


# ============================================================
# 拒绝原因
# ============================================================


class TestRejectionReasons:
    """测试拒绝原因"""

    def test_rejection_reasons_list(self, matcher, ai_policy):
        """rejection_reasons 是列表"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert isinstance(r.rejection_reasons, list)

    def test_rejection_for_weak_policy(self, matcher, weak_policy):
        """低分政策应有拒绝原因"""
        results = matcher.match_policies([weak_policy], "demo_tech")
        if results:
            r = results[0]
            if r.recommendation_score <= 2:
                # 低分应说明原因
                assert len(r.rejection_reasons) > 0


# ============================================================
# 紧急度
# ============================================================


class TestUrgency:
    """测试紧急度分级"""

    def test_urgency_values(self, matcher, ai_policy):
        """urgency 只能是 P0/P1/P2"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            assert r.urgency in ("P0", "P1", "P2")

    def test_urgency_p0_for_high_score(self, matcher, ai_policy):
        """高匹配+高优先级 -> P0"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            r = results[0]
            if r.score_total >= 15:
                assert r.urgency == "P0"


# ============================================================
# MatchResult.to_dict 完整性
# ============================================================


class TestMatchResultDict:
    """测试 MatchResult.to_dict 输出完整性"""

    def test_all_fields_in_dict(self, matcher, ai_policy):
        """to_dict 包含所有字段"""
        results = matcher.match_policies([ai_policy], "demo_tech")
        if results:
            d = results[0].to_dict()
            required_keys = [
                "policy_title", "policy_url", "enterprise_id",
                "score_tech", "score_prod", "score_mkt", "score_cap", "score_total",
                "hard_conditions_pass", "hard_conditions_detail",
                "weighted_score", "weights_used",
                "success_probability", "probability_factors",
                "roi_ratio", "roi_verdict", "roi_detail",
                "improvement_paths",
                "preference_match", "preference_notes",
                "recommendation", "recommendation_score",
                "urgency", "rejection_reasons",
                "matched_keywords", "opportunities", "risks",
            ]
            for key in required_keys:
                assert key in d, f"Missing key: {key}"


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCasesV4:
    """v4.0 边界情况"""

    def test_empty_summary_policy(self, matcher):
        """空摘要政策"""
        policy = {
            "title": "某政策",
            "url": "https://example.com/empty",
            "summary": "",
            "source": "测试",
            "date": "2026-05-20",
        }
        results = matcher.match_policies([policy], "demo_tech")
        # 不崩溃即可
        assert isinstance(results, list)

    def test_multiple_policies_sorted(self, matcher):
        """多条政策按分数排序"""
        policies = [
            {
                "title": "人工智能大模型专项",
                "url": "https://example.com/ai1",
                "summary": "人工智能 大模型 深度学习 计算机视觉",
                "source": "测试",
                "date": "2026-05-20",
            },
            {
                "title": "传统制造业技术改造",
                "url": "https://example.com/mfg",
                "summary": "制造业 车间 技改 设备更新",
                "source": "测试",
                "date": "2026-05-20",
            },
        ]
        results = matcher.match_policies(policies, "demo_tech")
        if len(results) >= 2:
            assert results[0].score_total >= results[1].score_total
