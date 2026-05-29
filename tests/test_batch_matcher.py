# -*- coding: utf-8 -*-
"""
batch_matcher.py 测试套件

测试批量匹配引擎：
  - BatchMatcher 初始化
  - run() 全量/指定企业/筛选
  - _load_policies 数据加载
  - _prepare_stacking_input
  - 错误处理（空企业/空政策/不存在企业）
"""

import sys
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "policy_monitor"))

from batch_matcher import BatchMatcher
from policy_monitor.database import PolicyDatabase


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def setup_dir(tmp_path):
    """创建临时目录结构"""
    enterprises_dir = tmp_path / "enterprises"
    enterprises_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return enterprises_dir, output_dir


@pytest.fixture
def enterprise_profile():
    return {
        "basic_info": {
            "company_name": "DEMO科技有限公司",
            "short_name": "DEMO科技",
            "registered_capital": 5000,
            "establishment_date": "2019-01-01",
            "registered_address": "湖北省武汉市",
        },
        "industry": {
            "primary_sector": "数字经济",
            "sub_sector": "人工智能",
            "industry_keywords": ["人工智能", "大模型", "计算机视觉"],
        },
        "qualifications": {
            "high_tech_enterprise": True,
            "sme_specialized": True,
            "sme_specialized_level": "省级",
        },
        "regions": {"headquarters": "湖北"},
        "business_model": {"has_production_base": True},
    }


@pytest.fixture
def populated_setup(setup_dir, enterprise_profile):
    """创建带数据的目录"""
    enterprises_dir, output_dir = setup_dir
    ent_dir = enterprises_dir / "demo_tech"
    ent_dir.mkdir()
    with open(ent_dir / "profile.yaml", "w", encoding="utf-8") as f:
        yaml.dump(enterprise_profile, f, allow_unicode=True)

    # 创建带数据的数据库
    db_path = str(setup_dir[0].parent / "policies.db")
    db = PolicyDatabase(db_path, str(setup_dir[0].parent / "exports"))

    policies = [
        {
            "title": "关于加快推进人工智能产业发展的实施意见",
            "url": "https://www.example.gov.cn/policy/2026/001",
            "date": "2026-05-20",
            "source": "国务院-人工智能",
            "summary": "支持大模型、深度学习、计算机视觉等关键技术研究，单个项目最高补助500万元。",
            "keywords_matched": ["人工智能", "大模型"],
            "score": 8,
            "priority": "P0",
            "fetched_at": "2026-05-25T10:00:00",
        },
        {
            "title": "关于促进新能源汽车产业发展通知",
            "url": "https://www.example.gov.cn/policy/2026/002",
            "date": "2026-05-21",
            "source": "工信部-新能源",
            "summary": "支持动力电池回收利用，充电基础设施建设。",
            "keywords_matched": ["新能源", "动力电池"],
            "score": 5,
            "priority": "P1",
            "fetched_at": "2026-05-25T11:00:00",
        },
    ]
    db.insert_batch(policies)
    db.close()

    return enterprises_dir, output_dir, Path(db_path)


# ============================================================
# 初始化
# ============================================================


class TestBatchMatcherInit:
    """测试 BatchMatcher 初始化"""

    def test_init(self, populated_setup):
        """正常初始化"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        assert len(bm.matcher.enterprises) == 1

    def test_init_empty_enterprises(self, setup_dir, tmp_path):
        """空企业目录"""
        enterprises_dir, output_dir = setup_dir
        db_path = str(tmp_path / "empty.db")
        bm = BatchMatcher(db_path, str(enterprises_dir), str(output_dir))
        assert len(bm.matcher.enterprises) == 0


# ============================================================
# run() 核心功能
# ============================================================


class TestBatchMatcherRun:
    """测试 run 方法"""

    def test_run_full(self, populated_setup):
        """全量匹配"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run()
        bm.close()

        assert "total_policies" in result
        assert "total_matches" in result
        assert "enterprises" in result
        assert "report_path" in result
        assert result["total_policies"] == 2
        assert result["total_matches"] >= 0

    def test_run_specific_enterprise(self, populated_setup):
        """指定企业"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run(enterprise_id="demo_tech")
        bm.close()

        assert "demo_tech" in result["enterprises"]

    def test_run_nonexistent_enterprise(self, populated_setup):
        """不存在的企业"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run(enterprise_id="nonexistent")
        bm.close()

        assert "error" in result

    def test_run_empty_db(self, setup_dir, tmp_path):
        """空数据库（有 schema 但无数据）"""
        enterprises_dir, output_dir = setup_dir
        ent_dir = enterprises_dir / "demo_tech"
        ent_dir.mkdir()
        with open(ent_dir / "profile.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"basic_info": {"company_name": "test"}}, f)

        # 先通过 PolicyDatabase 创建 schema
        db_path = str(tmp_path / "empty.db")
        from policy_monitor.database import PolicyDatabase
        db = PolicyDatabase(db_path, str(tmp_path / "exports"))
        db.close()

        bm = BatchMatcher(db_path, str(enterprises_dir), str(output_dir))
        result = bm.run()
        bm.close()

        assert "error" in result

    def test_run_with_date_filter(self, populated_setup):
        """日期筛选"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run(date_from="2026-05-21", date_to="2026-05-21")
        bm.close()

        # 只有 002 号政策在 05-21
        assert result["total_policies"] == 1

    def test_run_with_source_filter(self, populated_setup):
        """来源筛选"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run(source="国务院-人工智能")
        bm.close()

        assert result["total_policies"] == 1

    def test_run_min_score_filter(self, populated_setup):
        """最低分筛选"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        # 高分筛选：只保留 score >= 15
        result = bm.run(min_score=15)
        bm.close()

        # 大部分匹配会被过滤
        for eid, edata in result["enterprises"].items():
            for m in edata["matches"]:
                assert m.score_total >= 15


# ============================================================
# 报告生成
# ============================================================


class TestReportGeneration:
    """测试报告生成"""

    def test_report_file_created(self, populated_setup):
        """报告文件被创建"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run()
        bm.close()

        report_path = Path(result["report_path"])
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_report_contains_header(self, populated_setup):
        """报告包含标题"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        result = bm.run()
        bm.close()

        content = Path(result["report_path"]).read_text(encoding="utf-8")
        assert "batch" in content.lower() or "匹配" in content or "Report" in content


# ============================================================
# 边界情况
# ============================================================


class TestBatchMatcherEdgeCases:
    """边界情况"""

    def test_close_method(self, populated_setup):
        """close 方法正常执行"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        bm.run()
        bm.close()  # 不应抛异常

    def test_run_multiple_times(self, populated_setup):
        """多次运行不报错"""
        enterprises_dir, output_dir, db_path = populated_setup
        bm = BatchMatcher(str(db_path), str(enterprises_dir), str(output_dir))
        r1 = bm.run()
        r2 = bm.run()
        bm.close()
        assert r1["total_policies"] == r2["total_policies"]
