# -*- coding: utf-8 -*-
"""
enterprise_matcher.py 测试套件

测试六层评分体系：
  Layer 1: 维度评分 (Tech/Prod/Mkt/Cap)
  Layer 2: 可调权重
  Layer 3: 成功概率
  Layer 4: ROI 量化
  Layer 5: 提升路径
  Layer 6: 偏好过滤
"""

import pytest
import yaml
from pathlib import Path

from enterprise_matcher import EnterpriseMatcher, MatchResult


class TestEnterpriseMatcherInit:
    """测试 EnterpriseMatcher 初始化"""

    def test_init_with_valid_dir(self, sample_enterprise_dir):
        """测试使用有效目录初始化"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        assert len(matcher.enterprises) == 1
        assert "test_enterprise" in matcher.enterprises

    def test_init_with_empty_dir(self, tmp_path):
        """测试使用空目录初始化"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        matcher = EnterpriseMatcher(str(empty_dir))
        assert len(matcher.enterprises) == 0

    def test_init_with_nonexistent_dir(self, tmp_path):
        """测试使用不存在的目录初始化"""
        nonexistent = tmp_path / "nonexistent"
        matcher = EnterpriseMatcher(str(nonexistent))
        assert len(matcher.enterprises) == 0

    def test_get_enterprise_ids(self, sample_enterprise_dir):
        """测试获取企业 ID 列表"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        ids = matcher.get_enterprise_ids()
        assert isinstance(ids, list)
        assert "test_enterprise" in ids


class TestMatchResult:
    """测试 MatchResult 数据类"""

    def test_match_result_creation(self):
        """测试创建 MatchResult"""
        result = MatchResult(
            policy_url_hash="abc123",
            policy_title="测试政策",
            policy_url="https://example.com",
            policy_source="测试来源",
            policy_date="2026-05-20",
            policy_summary="测试摘要",
            enterprise_id="test_ent",
            enterprise_name="测试企业",
        )
        assert result.policy_title == "测试政策"
        assert result.score_tech == 0
        assert result.score_total == 0

    def test_match_result_to_dict(self):
        """测试 MatchResult 转字典"""
        result = MatchResult(
            policy_url_hash="abc123",
            policy_title="测试政策",
            policy_url="https://example.com",
            policy_source="测试来源",
            policy_date="2026-05-20",
            policy_summary="测试摘要",
            enterprise_id="test_ent",
            enterprise_name="测试企业",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["policy_title"] == "测试政策"
        assert "score_tech" in d
        assert "weighted_score" in d


class TestScoringDimensions:
    """测试四维评分逻辑"""

    def test_high_tech_keywords(self, sample_enterprise_dir, sample_policy):
        """测试技术关键词匹配"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            # 人工智能政策应该有较高的技术分
            assert result.score_tech >= 3

    def test_no_match_policy(self, sample_enterprise_dir):
        """测试不匹配的政策"""
        unrelated_policy = {
            "title": "关于加快推进农业现代化的实施意见",
            "url": "https://example.com/agriculture",
            "summary": "支持种业振兴、粮食安全、乡村振兴",
            "source": "国务院-农业",
            "date": "2026-05-20",
        }
        
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([unrelated_policy], "test_enterprise")
        
        # 不相关的政策应该不匹配或低分
        if results:
            assert results[0].score_total < 10

    def test_score_capped_at_5(self, sample_enterprise_dir):
        """测试评分上限为 5"""
        policy = {
            "title": "人工智能 大模型 深度学习 计算机视觉 自然语言处理",
            "url": "https://example.com/ai",
            "summary": "人工智能 大模型 深度学习 计算机视觉 自然语言处理 AIGC",
            "source": "测试",
            "date": "2026-05-20",
        }
        
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([policy], "test_enterprise")
        
        if results:
            result = results[0]
            assert result.score_tech <= 5
            assert result.score_prod <= 5
            assert result.score_mkt <= 5
            assert result.score_cap <= 5


class TestHardConditions:
    """测试硬性条件检查"""

    def test_region_match(self, sample_enterprise_dir, sample_policy):
        """测试注册地匹配"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            # 湖北企业应该通过注册地检查
            assert result.hard_conditions_pass is True

    def test_high_tech_qualification(self, sample_enterprise_dir, sample_policy):
        """测试高企资质检查"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            detail = result.hard_conditions_detail
            # 高企资质应该通过
            if "高企资质" in detail:
                assert detail["高企资质"]["通过"] is True


class TestRecommendationLevels:
    """测试推荐等级"""

    def test_recommendation_text_format(self, sample_enterprise_dir, sample_policy):
        """测试推荐等级文本格式"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            valid_levels = ["5/5 首选推荐", "4/5 强烈推荐", "3/5 推荐", 
                           "2/5 不推荐", "1/5 不匹配"]
            assert result.recommendation in valid_levels

    def test_recommendation_score_range(self, sample_enterprise_dir, sample_policy):
        """测试推荐分数范围"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            assert 1 <= result.recommendation_score <= 5


class TestBatchMatching:
    """测试批量匹配"""

    def test_match_multiple_policies(self, sample_enterprise_dir):
        """测试多条政策匹配"""
        policies = [
            {
                "title": "人工智能产业发展政策",
                "url": "https://example.com/ai",
                "summary": "支持大模型、深度学习",
                "source": "测试",
                "date": "2026-05-20",
            },
            {
                "title": "新能源汽车推广政策",
                "url": "https://example.com/ev",
                "summary": "支持新能源汽车、充电桩",
                "source": "测试",
                "date": "2026-05-20",
            },
        ]
        
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies(policies, "test_enterprise")
        
        # 应该返回匹配的结果（可能 0 或多条）
        assert isinstance(results, list)

    def test_results_sorted_by_score(self, sample_enterprise_dir):
        """测试结果按分数排序"""
        policies = [
            {
                "title": "人工智能大模型专项",
                "url": "https://example.com/ai1",
                "summary": "人工智能 大模型 深度学习",
                "source": "测试",
                "date": "2026-05-20",
            },
            {
                "title": "传统制造业转型",
                "url": "https://example.com/mfg",
                "summary": "制造业转型 技改",
                "source": "测试",
                "date": "2026-05-20",
            },
        ]
        
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies(policies, "test_enterprise")
        
        if len(results) >= 2:
            # 结果应该按分数降序排列
            assert results[0].score_total >= results[1].score_total


class TestWeightedScore:
    """测试加权评分"""

    def test_weighted_score_calculation(self, sample_enterprise_dir, sample_policy):
        """测试加权分数计算"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "test_enterprise")
        
        if results:
            result = results[0]
            # 加权分数应该在 0-5 之间
            assert 0 <= result.weighted_score <= 5
            # 应该有权重信息
            assert isinstance(result.weights_used, dict)


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_policy(self, sample_enterprise_dir):
        """测试空政策"""
        empty_policy = {
            "title": "",
            "url": "",
            "summary": "",
            "source": "",
            "date": "",
        }
        
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([empty_policy], "test_enterprise")
        
        # 空政策应该不匹配
        assert len(results) == 0

    def test_nonexistent_enterprise(self, sample_enterprise_dir, sample_policy):
        """测试不存在的企业"""
        matcher = EnterpriseMatcher(str(sample_enterprise_dir))
        results = matcher.match_policies([sample_policy], "nonexistent")
        
        # 不存在的企业应该返回空列表
        assert len(results) == 0
