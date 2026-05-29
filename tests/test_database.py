# -*- coding: utf-8 -*-
"""
policy_monitor/database.py 测试套件

测试 SQLite 存储层：
  - CRUD 操作（insert / get / mark）
  - 去重机制（URL hash）
  - 匹配结果存储
  - Agent 运行日志
  - 导出功能（JSON / CSV）
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

# 确保能导入项目模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "policy_monitor"))
sys.path.insert(0, str(PROJECT_ROOT))

from database import PolicyDatabase
from utils import url_hash


@pytest.fixture
def db(tmp_path):
    """创建临时数据库"""
    db_path = str(tmp_path / "test_policies.db")
    export_dir = str(tmp_path / "exports")
    database = PolicyDatabase(db_path, export_dir)
    yield database
    database.close()


@pytest.fixture
def sample_policy():
    """示例政策数据"""
    return {
        "title": "关于加快推进人工智能产业发展的实施意见",
        "url": "https://www.example.gov.cn/policy/2026/001",
        "date": "2026-05-20",
        "source": "国务院-人工智能",
        "summary": "支持大模型、深度学习、计算机视觉等关键技术研究。",
        "keywords_matched": ["人工智能", "大模型"],
        "score": 8,
        "priority": "P0",
        "fetched_at": "2026-05-25T10:00:00",
    }


@pytest.fixture
def sample_policy_2():
    """第二条示例政策"""
    return {
        "title": "关于促进新能源汽车产业高质量发展的通知",
        "url": "https://www.example.gov.cn/policy/2026/002",
        "date": "2026-05-21",
        "source": "工信部-新能源汽车",
        "summary": "支持动力电池回收利用，充电基础设施建设。",
        "keywords_matched": ["新能源汽车", "动力电池"],
        "score": 6,
        "priority": "P1",
        "fetched_at": "2026-05-25T11:00:00",
    }


# ============================================================
# 基本 CRUD 操作
# ============================================================


class TestInsertAndQuery:
    """测试插入和查询"""

    def test_insert_new_policy(self, db, sample_policy):
        """测试插入新政策，返回 True"""
        result = db.insert(sample_policy)
        assert result is True

    def test_insert_duplicate_returns_false(self, db, sample_policy):
        """测试重复插入同一政策，返回 False"""
        db.insert(sample_policy)
        result = db.insert(sample_policy)
        assert result is False

    def test_insert_batch(self, db, sample_policy, sample_policy_2):
        """测试批量插入"""
        count = db.insert_batch([sample_policy, sample_policy_2])
        assert count == 2

    def test_insert_batch_with_duplicate(self, db, sample_policy, sample_policy_2):
        """测试批量插入含重复"""
        db.insert(sample_policy)
        count = db.insert_batch([sample_policy, sample_policy_2])
        assert count == 1  # 只有 1 条是新增的

    def test_get_latest(self, db, sample_policy, sample_policy_2):
        """测试获取最新政策"""
        db.insert(sample_policy)
        db.insert(sample_policy_2)
        results = db.get_latest(limit=10)
        assert len(results) == 2
        # 按日期降序
        assert results[0]["date"] >= results[1]["date"]

    def test_get_latest_limit(self, db):
        """测试 limit 参数"""
        for i in range(5):
            db.insert({
                "title": f"政策{i}",
                "url": f"https://example.com/policy/{i}",
                "date": f"2026-05-{20 + i:02d}",
                "source": "测试",
                "summary": "摘要",
                "keywords_matched": [],
                "score": 5,
                "priority": "P2",
                "fetched_at": "2026-05-25T10:00:00",
            })
        results = db.get_latest(limit=3)
        assert len(results) == 3

    def test_get_new_today(self, db):
        """测试获取今天新增的政策"""
        from utils import now_iso
        today_policy = {
            "title": "今日政策",
            "url": "https://example.com/today",
            "date": "2026-05-29",
            "source": "测试",
            "summary": "今日摘要",
            "keywords_matched": [],
            "score": 5,
            "priority": "P2",
            "fetched_at": now_iso(),  # 使用当前时间
        }
        db.insert(today_policy)
        results = db.get_new_today()
        assert len(results) >= 1
        urls = [r["url"] for r in results]
        assert today_policy["url"] in urls

    def test_get_recent_policies(self, db, sample_policy):
        """测试获取最近 N 天的政策"""
        db.insert(sample_policy)
        results = db.get_recent_policies(days=30)
        assert len(results) >= 1


# ============================================================
# 标记已分析
# ============================================================


class TestMarkAnalyzed:
    """测试标记已分析"""

    def test_mark_analyzed(self, db, sample_policy):
        """测试标记为已分析"""
        db.insert(sample_policy)
        h = url_hash(sample_policy["url"])
        db.mark_analyzed(h)

        # get_unanalyzed 不应包含这条
        unanalyzed = db.get_unanalyzed()
        urls = [r["url"] for r in unanalyzed]
        assert sample_policy["url"] not in urls

    def test_unanalyzed_policies(self, db, sample_policy):
        """测试获取未分析的高优先级政策"""
        db.insert(sample_policy)
        unanalyzed = db.get_unanalyzed()
        # sample_policy 是 P0，应该出现
        assert len(unanalyzed) >= 1


# ============================================================
# 匹配结果存储
# ============================================================


class TestMatchStorage:
    """测试企业匹配结果的存储"""

    def test_insert_match(self, db, sample_policy):
        """测试插入匹配结果"""
        db.insert(sample_policy)
        match = {
            "policy_url_hash": url_hash(sample_policy["url"]),
            "enterprise_id": "test_ent",
            "hard_conditions_pass": 1,
            "hard_conditions_detail": json.dumps({"注册地": {"通过": True}}),
            "score_tech": 4,
            "score_prod": 3,
            "score_mkt": 2,
            "score_cap": 3,
            "score_total": 12,
            "recommendation": "4/5 强烈推荐",
            "recommendation_score": 4,
            "urgency": "P0",
            "matched_at": "2026-05-25T12:00:00",
        }
        result = db.insert_match(match)
        assert result is True

    def test_insert_match_duplicate(self, db, sample_policy):
        """测试重复插入匹配结果"""
        db.insert(sample_policy)
        match = {
            "policy_url_hash": url_hash(sample_policy["url"]),
            "enterprise_id": "test_ent",
            "hard_conditions_pass": 1,
            "hard_conditions_detail": "{}",
            "score_tech": 4,
            "score_prod": 3,
            "score_mkt": 2,
            "score_cap": 3,
            "score_total": 12,
            "recommendation": "4/5 强烈推荐",
            "recommendation_score": 4,
            "urgency": "P0",
            "matched_at": "2026-05-25T12:00:00",
        }
        db.insert_match(match)
        result = db.insert_match(match)
        assert result is False

    def test_get_matches_for_enterprise(self, db, sample_policy, sample_policy_2):
        """测试获取某企业的全部匹配结果"""
        db.insert(sample_policy)
        db.insert(sample_policy_2)
        for p in [sample_policy, sample_policy_2]:
            match = {
                "policy_url_hash": url_hash(p["url"]),
                "enterprise_id": "test_ent",
                "hard_conditions_pass": 1,
                "hard_conditions_detail": "{}",
                "score_tech": 4,
                "score_prod": 3,
                "score_mkt": 2,
                "score_cap": 3,
                "score_total": 12,
                "recommendation": "4/5 强烈推荐",
                "recommendation_score": 4,
                "urgency": "P0",
                "matched_at": "2026-05-25T12:00:00",
            }
            db.insert_match(match)

        matches = db.get_matches_for_enterprise("test_ent")
        assert len(matches) == 2

    def test_get_matches_nonexistent_enterprise(self, db, sample_policy):
        """测试查询不存在企业的匹配结果"""
        db.insert(sample_policy)
        matches = db.get_matches_for_enterprise("nonexistent")
        assert len(matches) == 0

    def test_mark_brief_generated(self, db, sample_policy):
        """测试标记简报已生成"""
        db.insert(sample_policy)
        h = url_hash(sample_policy["url"])
        match = {
            "policy_url_hash": h,
            "enterprise_id": "test_ent",
            "hard_conditions_pass": 1,
            "hard_conditions_detail": "{}",
            "score_tech": 4,
            "score_prod": 3,
            "score_mkt": 2,
            "score_cap": 3,
            "score_total": 12,
            "recommendation": "4/5 强烈推荐",
            "recommendation_score": 4,
            "urgency": "P0",
            "matched_at": "2026-05-25T12:00:00",
        }
        db.insert_match(match)
        db.mark_brief_generated(h, "test_ent", "/path/to/brief.md")


# ============================================================
# Agent 运行日志
# ============================================================


class TestAgentRuns:
    """测试 Agent 运行日志"""

    def test_record_agent_run(self, db):
        """测试记录 Agent 运行"""
        run_id = db.record_agent_run("full")
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_finish_agent_run(self, db):
        """测试完成 Agent 运行"""
        run_id = db.record_agent_run("scan")
        db.finish_agent_run(
            run_id,
            status="completed",
            policies_scanned=10,
            policies_new=3,
            matches_found=5,
        )
        runs = db.get_recent_agent_runs()
        assert len(runs) >= 1
        run = runs[0]
        assert run["status"] == "completed"
        assert run["policies_scanned"] == 10

    def test_finish_agent_run_with_error(self, db):
        """测试 Agent 运行出错"""
        run_id = db.record_agent_run("match")
        db.finish_agent_run(
            run_id,
            status="error",
            error_message="Connection timeout",
        )
        runs = db.get_recent_agent_runs()
        run = runs[0]
        assert run["status"] == "error"
        assert run["error_message"] == "Connection timeout"

    def test_get_recent_agent_runs_limit(self, db):
        """测试获取最近运行记录的 limit"""
        for _ in range(5):
            db.record_agent_run("scan")
        runs = db.get_recent_agent_runs(limit=3)
        assert len(runs) == 3


# ============================================================
# 统计和导出
# ============================================================


class TestStatsAndExport:
    """测试统计和导出功能"""

    def test_stats_empty(self, db):
        """测试空数据库统计"""
        stats = db.stats()
        assert isinstance(stats, dict)
        assert stats.get("total", 0) == 0

    def test_stats_with_data(self, db, sample_policy):
        """测试有数据时的统计"""
        db.insert(sample_policy)
        stats = db.stats()
        assert stats["total"] >= 1

    def test_export_json(self, db, sample_policy):
        """测试 JSON 导出"""
        db.insert(sample_policy)
        db.export_json(limit=10)
        export_file = Path(db.export_dir) / "latest.json"
        assert export_file.exists()
        with open(export_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "policies" in data
        assert len(data["policies"]) >= 1

    def test_export_csv(self, db, sample_policy):
        """测试 CSV 导出"""
        db.insert(sample_policy)
        db.export_csv(limit=10)
        export_files = list(Path(db.export_dir).glob("*.csv"))
        assert len(export_files) >= 1

    def test_export_all(self, db, sample_policy):
        """测试同时导出 JSON + CSV"""
        db.insert(sample_policy)
        db.export_all()
        json_files = list(Path(db.export_dir).glob("*.json"))
        csv_files = list(Path(db.export_dir).glob("*.csv"))
        assert len(json_files) >= 1
        assert len(csv_files) >= 1


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """测试边界情况"""

    def test_insert_policy_missing_fields(self, db):
        """测试缺少字段的政策仍能插入"""
        policy = {
            "title": "最小化政策",
            "url": "https://example.com/min",
            # 缺少 date / source / summary 等字段
        }
        # 不应抛异常
        result = db.insert(policy)
        assert result is True

    def test_multiple_enterprises_same_policy(self, db, sample_policy):
        """测试同一条政策被多个企业匹配"""
        db.insert(sample_policy)
        h = url_hash(sample_policy["url"])
        for ent_id in ["ent_a", "ent_b", "ent_c"]:
            match = {
                "policy_url_hash": h,
                "enterprise_id": ent_id,
                "hard_conditions_pass": 1,
                "hard_conditions_detail": "{}",
                "score_tech": 3,
                "score_prod": 3,
                "score_mkt": 3,
                "score_cap": 3,
                "score_total": 12,
                "recommendation": "3/5 推荐",
                "recommendation_score": 3,
                "urgency": "P1",
                "matched_at": "2026-05-25T12:00:00",
            }
            db.insert_match(match)

        assert len(db.get_matches_for_enterprise("ent_a")) == 1
        assert len(db.get_matches_for_enterprise("ent_b")) == 1
        assert len(db.get_matches_for_enterprise("ent_c")) == 1
