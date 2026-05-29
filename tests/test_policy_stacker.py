# -*- coding: utf-8 -*-
"""
policy_stacker.py 测试套件

测试政策组合叠加分析：
  - 叠加规则查询 (get_stacking_rule)
  - 政策相似度计算 (calculate_policy_similarity)
  - 组合分析 (PolicyStacker.analyze)
  - 数据类 (PolicyStackItem / PolicyBundle / PolicyCeiling)
  - 报告格式化
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from policy_stacker import (
    PolicyStacker,
    PolicyStackItem,
    PolicyBundle,
    PolicyCeiling,
    get_stacking_rule,
    calculate_policy_similarity,
    format_stacking_report,
    quick_stack,
    STACKING_RULES,
)


# ============================================================
# 叠加规则查询
# ============================================================


class TestGetStackingRule:
    """测试 get_stacking_rule 函数"""

    def test_complementary_rule(self):
        """拨改投 + 税收优惠 = complementary"""
        rule = get_stacking_rule("拨改投", "税收优惠")
        assert rule == "complementary"

    def test_complementary_reversed(self):
        """反向查询结果相同"""
        rule = get_stacking_rule("税收优惠", "拨改投")
        assert rule == "complementary"

    def test_exclusive_rule(self):
        """同类政策互斥"""
        rule = get_stacking_rule("拨改投", "拨改投")
        assert rule == "exclusive"

    def test_exclusive_fund(self):
        """基金 + 拨改投 互斥"""
        rule = get_stacking_rule("基金/投融资", "拨改投")
        assert rule == "exclusive"

    def test_conditional_rule(self):
        """专项补贴 + 专项补贴 = conditional"""
        rule = get_stacking_rule("专项补贴", "专项补贴")
        assert rule == "conditional"

    def test_partial_rule(self):
        """专项补贴 + 基金 = partial"""
        rule = get_stacking_rule("专项补贴", "基金/投融资")
        assert rule == "partial"

    def test_same_type_default_exclusive(self):
        """未定义的同类型默认互斥"""
        rule = get_stacking_rule("资质认定", "资质认定")
        assert rule == "exclusive"

    def test_unknown_types_default_complementary(self):
        """未知类型默认可叠加"""
        rule = get_stacking_rule("未知类型A", "未知类型B")
        assert rule == "complementary"

    def test_all_rules_defined(self):
        """验证规则矩阵完整性：至少有 15 条规则"""
        assert len(STACKING_RULES) >= 15


# ============================================================
# 政策相似度
# ============================================================


class TestCalculatePolicySimilarity:
    """测试 calculate_policy_similarity 函数"""

    def test_identical_policies(self):
        """完全相同政策 -> 高相似度"""
        policy = {
            "title": "关于发放人工智能专项资金的通知",
            "summary": "给予每家企业最高200万元补助",
            "source": "国务院",
        }
        sim = calculate_policy_similarity(policy, policy)
        assert sim > 0.5  # 高相似度

    def test_different_policies(self):
        """完全不同的政策 -> 低相似度"""
        a = {"title": "人工智能产业发展政策", "summary": "支持大模型", "source": "国务院"}
        b = {"title": "农业现代化推进政策", "summary": "种业振兴", "source": "农业农村部"}
        sim = calculate_policy_similarity(a, b)
        assert sim < 0.3

    def test_same_source_bonus(self):
        """相同来源增加相似度"""
        a = {"title": "人工智能政策A", "summary": "资金支持", "source": "国务院"}
        b = {"title": "人工智能政策B", "summary": "资金支持", "source": "国务院"}
        c = {"title": "人工智能政策B", "summary": "资金支持", "source": "工信部"}
        sim_same = calculate_policy_similarity(a, b)
        sim_diff = calculate_policy_similarity(a, c)
        assert sim_same > sim_diff

    def test_same_amount_bonus(self):
        """相同金额增加相似度（同一资金池）"""
        a = {"title": "专项补贴", "summary": "最高200万元补助", "source": ""}
        b = {"title": "专项补贴", "summary": "最高200万元补助", "source": ""}
        c = {"title": "专项补贴", "summary": "最高500万元补助", "source": ""}
        sim_same = calculate_policy_similarity(a, b)
        sim_diff = calculate_policy_similarity(a, c)
        assert sim_same >= sim_diff

    def test_empty_policies(self):
        """空政策"""
        a = {"title": "", "summary": "", "source": ""}
        b = {"title": "", "summary": "", "source": ""}
        sim = calculate_policy_similarity(a, b)
        assert 0 <= sim <= 1

    def test_range_0_to_1(self):
        """相似度范围 0-1"""
        a = {"title": "人工智能", "summary": "大模型", "source": "A"}
        b = {"title": "新能源", "summary": "光伏", "source": "B"}
        sim = calculate_policy_similarity(a, b)
        assert 0 <= sim <= 1


# ============================================================
# PolicyStackItem 数据类
# ============================================================


class TestPolicyStackItem:
    """测试 PolicyStackItem"""

    def test_creation(self):
        """创建 PolicyStackItem"""
        item = PolicyStackItem(
            policy={"title": "test"},
            policy_type="专项补贴",
            individual_roi=5.0,
        )
        assert item.policy_type == "专项补贴"
        assert item.individual_roi == 5.0
        assert item.stacking_role == "primary"

    def test_defaults(self):
        """默认值"""
        item = PolicyStackItem(policy={"title": "test"}, policy_type="其他")
        assert item.individual_benefit == 0
        assert item.overlap_note == ""


# ============================================================
# PolicyBundle 数据类
# ============================================================


class TestPolicyBundle:
    """测试 PolicyBundle"""

    def test_creation(self):
        """创建 PolicyBundle"""
        bundle = PolicyBundle(
            bundle_id=1,
            name="最优组合",
            total_benefit=500,
            total_cost=50,
            combined_roi=10.0,
        )
        assert bundle.name == "最优组合"
        assert bundle.combined_roi == 10.0

    def test_defaults(self):
        """默认值"""
        bundle = PolicyBundle()
        assert bundle.policies == []
        assert bundle.exclusions == []


# ============================================================
# PolicyStacker.analyze
# ============================================================


class TestPolicyStacker:
    """测试 PolicyStacker 组合分析"""

    @pytest.fixture
    def stacker(self):
        return PolicyStacker()

    @pytest.fixture
    def three_policies_with_roi(self):
        """三条带 ROI 数据的政策"""
        return [
            {
                "policy": {
                    "title": "人工智能专项资金补贴",
                    "summary": "支持大模型研发，最高补助500万元",
                    "source": "国务院",
                },
                "roi_ratio": 6.0,
                "benefit": 500,
                "cost": 30,
                "policy_type": "专项补贴",
                "recommendation": 4,
            },
            {
                "policy": {
                    "title": "高新技术企业税收优惠",
                    "summary": "减按15%税率征收企业所得税",
                    "source": "国家税务总局",
                },
                "roi_ratio": 20.0,
                "benefit": 200,
                "cost": 5,
                "policy_type": "税收优惠",
                "recommendation": 5,
            },
            {
                "policy": {
                    "title": "专精特新企业认定",
                    "summary": "给予100万元奖励",
                    "source": "工信部",
                },
                "roi_ratio": 4.0,
                "benefit": 100,
                "cost": 15,
                "policy_type": "资质认定",
                "recommendation": 3,
            },
        ]

    def test_analyze_empty(self, stacker):
        """空列表分析"""
        result = stacker.analyze([])
        assert result["bundles"] == []
        assert result["summary"] == "No policies to analyze"

    def test_analyze_single_policy(self, stacker):
        """单条政策分析"""
        policies = [
            {
                "policy": {"title": "专项补贴", "summary": "补助200万"},
                "roi_ratio": 5.0,
                "benefit": 200,
                "cost": 20,
                "policy_type": "专项补贴",
                "recommendation": 4,
            }
        ]
        result = stacker.analyze(policies)
        assert "bundles" in result
        assert "ceiling" in result
        assert isinstance(result["ceiling"], PolicyCeiling)

    def test_analyze_three_complementary(self, stacker, three_policies_with_roi):
        """三条互补政策的分析"""
        result = stacker.analyze(three_policies_with_roi)
        bundles = result["bundles"]
        pairwise = result["pairwise"]
        assert len(bundles) >= 1
        assert isinstance(pairwise, dict)
        # ceiling 应有值
        ceiling = result["ceiling"]
        assert ceiling.theoretical_max >= 0

    def test_analyze_with_enterprise_profile(self, stacker, three_policies_with_roi):
        """带企业画像分析"""
        profile = {
            "basic_info": {"company_name": "测试企业", "registered_capital": 5000},
            "industry": {"primary_sector": "数字经济"},
        }
        result = stacker.analyze(three_policies_with_roi, enterprise_profile=profile)
        assert "bundles" in result

    def test_exclusive_policies(self, stacker):
        """互斥政策检测"""
        policies = [
            {
                "policy": {"title": "基金A", "summary": "投融资"},
                "roi_ratio": 3.0,
                "benefit": 100,
                "cost": 10,
                "policy_type": "基金/投融资",
                "recommendation": 3,
            },
            {
                "policy": {"title": "拨改投", "summary": "股权投资"},
                "roi_ratio": 5.0,
                "benefit": 200,
                "cost": 20,
                "policy_type": "拨改投",
                "recommendation": 4,
            },
        ]
        result = stacker.analyze(policies)
        # 基金和拨改投互斥
        pairwise = result["pairwise"]
        # pairwise 格式: {(0,1): {"rule": str, "reason": str, "similarity": float}}
        exclusive_pairs = [v for v in pairwise.values() if v.get("rule") == "exclusive"]
        assert len(exclusive_pairs) >= 1


# ============================================================
# format_stacking_report
# ============================================================


class TestFormatStackingReport:
    """测试报告格式化"""

    def test_format_basic(self):
        """基本格式化"""
        analysis = {
            "bundles": [
                PolicyBundle(
                    name="推荐组合",
                    total_benefit=600,
                    total_cost=40,
                    combined_roi=15.0,
                    recommendation="强烈推荐",
                )
            ],
            "ceiling": PolicyCeiling(
                theoretical_max=800,
                feasible_max=600,
                existing_income=100,
                incremental_space=500,
                by_type={"专项补贴": {"count": 2, "total_benefit": 400}},
            ),
            "pairwise": {(0, 1): {"rule": "complementary", "reason": "ok", "similarity": 0.1}},
            "summary": "3 条政策可组合，预计收益 600 万元",
        }
        report = format_stacking_report(analysis)
        assert isinstance(report, str)
        assert "Policy" in report or len(report) > 10


# ============================================================
# quick_stack
# ============================================================


class TestQuickStack:
    """测试 quick_stack 便捷函数"""

    def test_quick_stack(self):
        """一步到位分析"""
        policies = [
            {
                "policy": {"title": "专项补贴", "summary": "补助200万"},
                "roi_ratio": 5.0,
                "benefit": 200,
                "cost": 20,
                "policy_type": "专项补贴",
                "recommendation": 4,
            },
            {
                "policy": {"title": "税收优惠", "summary": "减税"},
                "roi_ratio": 10.0,
                "benefit": 100,
                "cost": 5,
                "policy_type": "税收优惠",
                "recommendation": 5,
            },
        ]
        report = quick_stack(policies)
        assert isinstance(report, str)
        assert len(report) > 0


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """边界情况"""

    def test_large_bundle(self):
        """大量政策"""
        policies = [
            {
                "policy": {"title": f"政策{i}", "summary": f"摘要{i}"},
                "roi_ratio": float(i),
                "benefit": float(i * 100),
                "cost": float(i * 5),
                "policy_type": ["专项补贴", "税收优惠", "资质认定"][i % 3],
                "recommendation": min(i, 5),
            }
            for i in range(1, 8)
        ]
        stacker = PolicyStacker()
        result = stacker.analyze(policies)
        assert "bundles" in result
        assert "ceiling" in result
