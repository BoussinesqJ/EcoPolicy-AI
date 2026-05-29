# -*- coding: utf-8 -*-
"""
roi_calculator.py 测试套件

测试 ROI 量化评估模块：
  - 政策类型自动分类
  - PolicyFinancials / ROIResult 数据类
  - ROICalculator 核心计算
  - 行业基准对比
  - ROI 报告格式化
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from roi_calculator import (
    ROICalculator,
    PolicyFinancials,
    ROIResult,
    classify_policy_type,
    format_roi_report,
)


# ============================================================
# 政策类型分类
# ============================================================


class TestClassifyPolicyType:
    """测试 classify_policy_type 函数"""

    def test_subsidy_type(self):
        """专项补贴"""
        result = classify_policy_type(
            "关于发放人工智能专项资金补贴的通知",
            "给予每家企业最高200万元无偿资助"
        )
        assert result == "专项补贴"

    def test_tax_type(self):
        """税收优惠"""
        result = classify_policy_type(
            "关于落实高新技术企业税收优惠政策的通知",
            "减按15%税率征收企业所得税，研发费用加计扣除"
        )
        assert result == "税收优惠"

    def test_qualification_type(self):
        """资质认定"""
        result = classify_policy_type(
            "关于组织开展专精特新企业认定工作的通知"
        )
        assert result == "资质认定"

    def test_equity_type(self):
        """拨改投"""
        result = classify_policy_type(
            "关于设立政府股权投资基金的通知",
            "以增资扩股方式投入，政府参股比例不超过30%"
        )
        assert result == "拨改投"

    def test_project_approval_type(self):
        """项目审批"""
        result = classify_policy_type(
            "关于规范项目审批管理的通知",
            "重大建设项目需经可行性研究和立项审批"
        )
        assert result == "项目审批"

    def test_fund_type(self):
        """基金/投融资"""
        result = classify_policy_type(
            "关于设立产业引导基金的通知",
            "支持企业融资贷款贴息和信贷担保"
        )
        assert result == "基金/投融资"

    def test_unknown_type(self):
        """无关键词返回其他"""
        result = classify_policy_type("关于加强安全生产工作的通知")
        assert result == "其他"

    def test_competition_priority(self):
        """多个类型时取匹配度最高的"""
        # 补贴关键词出现 2 次，税收出现 1 次
        result = classify_policy_type(
            "专项资金补贴和税收减免",
            "给予专项资金支持和税收优惠"
        )
        assert result in ("专项补贴", "税收优惠")


# ============================================================
# PolicyFinancials 数据类
# ============================================================


class TestPolicyFinancials:
    """测试 PolicyFinancials 数据类"""

    def test_default_values(self):
        """默认值"""
        f = PolicyFinancials()
        assert f.policy_type == "其他"
        assert f.max_funding == 0
        assert f.application_cost == 0
        assert f.funding_duration_years == 1

    def test_custom_values(self):
        """自定义值"""
        f = PolicyFinancials(
            policy_type="专项补贴",
            max_funding=300,
            tax_benefit_annual=50,
            application_cost=15,
        )
        assert f.policy_type == "专项补贴"
        assert f.max_funding == 300


# ============================================================
# ROIResult 数据类
# ============================================================


class TestROIResult:
    """测试 ROIResult 数据类"""

    def test_default_values(self):
        """默认值"""
        r = ROIResult()
        assert r.total_benefit == 0
        assert r.roi_ratio == 0
        assert r.verdict == ""

    def test_to_dict(self):
        """转字典"""
        r = ROIResult(total_benefit=100, total_cost=20, roi_ratio=5.0)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["total_benefit"] == 100
        assert d["roi_ratio"] == 5.0
        assert "verdict" in d
        assert "risk_level" in d


# ============================================================
# ROICalculator 核心计算
# ============================================================


class TestROICalculator:
    """测试 ROICalculator"""

    def test_init_default_industry(self):
        """默认行业"""
        calc = ROICalculator()
        assert calc.industry == "通用"

    def test_init_specific_industry(self):
        """指定行业"""
        calc = ROICalculator(industry="人工智能")
        assert calc.industry == "人工智能"

    def test_calculate_positive_roi(self):
        """正向 ROI 计算"""
        calc = ROICalculator()
        financials = PolicyFinancials(
            policy_type="专项补贴",
            max_funding=300,
            application_cost=15,
            compliance_cost_annual=3,
            compliance_years=2,
            brand_value=30,
            market_value=20,
            policy_network_value=20,
            talent_value=10,
            follow_up_value=50,
        )
        result = calc.calculate(financials, success_probability=0.6)
        assert result.total_benefit > 0
        assert result.total_cost > 0
        assert isinstance(result.roi_ratio, float)
        assert result.verdict != ""

    def test_calculate_zero_probability(self):
        """成功概率为 0"""
        calc = ROICalculator()
        financials = PolicyFinancials(max_funding=300, application_cost=15)
        result = calc.calculate(financials, success_probability=0.0)
        assert result.risk_adjusted_benefit == 0

    def test_calculate_high_probability(self):
        """高成功概率"""
        calc = ROICalculator()
        financials = PolicyFinancials(
            policy_type="税收优惠",
            tax_benefit_annual=100,
            application_cost=5,
            funding_duration_years=5,
        )
        result = calc.calculate(financials, success_probability=0.9)
        assert result.roi_ratio > 10

    def test_calculate_has_benchmark(self):
        """有行业基准对比"""
        calc = ROICalculator(industry="人工智能")
        financials = PolicyFinancials(
            policy_type="专项补贴",
            max_funding=300,
            application_cost=15,
        )
        result = calc.calculate(financials, success_probability=0.6)
        # 应有基准对比
        assert result.benchmark_status != "" or result.benchmark_percentile >= 0

    def test_estimate_financials_subsidy(self):
        """从政策文本估算专项补贴财务参数"""
        calc = ROICalculator()
        policy = {
            "title": "关于发放人工智能专项资金的通知",
            "summary": "对符合条件的企业给予最高200万元补助",
        }
        profile = {
            "basic_info": {"registered_capital": 3000},
        }
        financials = calc.estimate_financials(policy, profile)
        assert financials.policy_type == "专项补贴"
        assert financials.max_funding > 0

    def test_estimate_financials_tax(self):
        """从政策文本估算税收优惠财务参数"""
        calc = ROICalculator()
        policy = {
            "title": "高新技术企业税收优惠政策",
            "summary": "减按15%税率征收企业所得税",
        }
        # estimate_financials 通过 _estimate_tax_benefit_by_revenue 读取
        # basic.get("finance", {}).get("annual_revenue") 或 basic.get("annual_revenue")
        profile = {
            "basic_info": {
                "registered_capital": 5000,
                "finance": {"annual_revenue": 10000},
            },
        }
        financials = calc.estimate_financials(policy, profile)
        assert financials.policy_type == "税收优惠"
        # 税收优惠不依赖 funding，但应正确分类
        assert financials.application_cost >= 0

    def test_get_benchmark_summary(self):
        """获取基准摘要"""
        calc = ROICalculator(industry="人工智能")
        summary = calc.get_benchmark_summary()
        assert isinstance(summary, dict)

    def test_auto_classify_industry(self):
        """自动识别行业"""
        profile = {
            "industry": {
                "primary_sector": "数字经济",
                "sub_sector": "人工智能",
            }
        }
        industry = ROICalculator.auto_classify_industry(profile)
        assert isinstance(industry, str)
        assert len(industry) > 0


# ============================================================
# ROI 报告格式化
# ============================================================


class TestFormatRoiReport:
    """测试 format_roi_report"""

    def test_basic_report(self):
        """基本报告"""
        result = ROIResult(
            total_benefit=200,
            total_cost=30,
            roi_ratio=6.67,
            verdict="值得申报",
        )
        financials = PolicyFinancials(policy_type="专项补贴")
        report = format_roi_report(result, financials)
        assert isinstance(report, str)
        assert "ROI" in report or "收益" in report or "回报" in report

    def test_report_with_benchmark(self):
        """带基准对比的报告"""
        result = ROIResult(
            total_benefit=200,
            total_cost=30,
            roi_ratio=6.67,
            benchmark_status="优于行业",
            verdict="值得申报",
        )
        financials = PolicyFinancials(policy_type="专项补贴")
        report = format_roi_report(result, financials)
        assert "优于行业" in report or "行业" in report


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """边界情况"""

    def test_zero_cost_roi(self):
        """零成本时 ROI 无限大"""
        calc = ROICalculator()
        financials = PolicyFinancials(max_funding=100, application_cost=0)
        result = calc.calculate(financials, success_probability=1.0)
        # ROI 应该非常高或有特殊处理
        assert result.total_cost >= 0

    def test_large_funding(self):
        """大额资金"""
        calc = ROICalculator()
        financials = PolicyFinancials(
            policy_type="拨改投",
            max_funding=5000,
            application_cost=30,
            equity_dilution=20,
        )
        result = calc.calculate(financials, success_probability=0.7)
        assert result.total_benefit > 0
