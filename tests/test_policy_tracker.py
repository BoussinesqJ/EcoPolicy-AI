# -*- coding: utf-8 -*-
"""
policy_tracker.py 测试套件

测试政策变更追踪：
  - 快照记录 (record_snapshots)
  - 变更检测 (detect_changes)
  - 未通知变更 (detect_unnotified_changes)
  - 标记通知 (mark_notified)
  - 政策历史 (get_policy_history)
  - 变更统计 (get_change_stats)
  - 报告生成 (generate_change_report)
"""

import sys
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from policy_tracker import PolicyTracker


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def tracker(tmp_path):
    """创建临时 PolicyTracker"""
    db_path = str(tmp_path / "tracker.db")
    output_dir = str(tmp_path / "output")
    t = PolicyTracker(db_path, output_dir)
    yield t
    t.close()


@pytest.fixture
def sample_policies():
    """示例政策列表"""
    return [
        {
            "title": "关于加快推进人工智能产业发展的实施意见",
            "url": "https://www.example.gov.cn/policy/2026/001",
            "summary": "支持大模型、深度学习等关键技术研究。",
            "keywords_matched": ["人工智能", "大模型"],
            "score": 8,
            "priority": "P0",
            "source": "国务院-人工智能",
        },
        {
            "title": "关于促进新能源汽车产业发展通知",
            "url": "https://www.example.gov.cn/policy/2026/002",
            "summary": "支持动力电池回收利用。",
            "keywords_matched": ["新能源", "动力电池"],
            "score": 6,
            "priority": "P1",
            "source": "工信部-新能源",
        },
    ]


# ============================================================
# 快照记录
# ============================================================


class TestRecordSnapshots:
    """测试快照记录"""

    def test_record_new_policies(self, tracker, sample_policies):
        """记录全新政策"""
        stats = tracker.record_snapshots(sample_policies)
        assert stats["new_policies"] == 2
        assert stats["new_snapshots"] == 2
        assert stats["changes_detected"] == 0

    def test_record_same_policies_no_change(self, tracker, sample_policies):
        """重复记录相同政策无变更"""
        tracker.record_snapshots(sample_policies)
        stats = tracker.record_snapshots(sample_policies)
        assert stats["new_policies"] == 0
        assert stats["changes_detected"] == 0

    def test_detect_title_change(self, tracker, sample_policies):
        """检测标题变更"""
        tracker.record_snapshots(sample_policies)

        # 修改第一条的标题
        modified = sample_policies.copy()
        modified[0] = {**modified[0], "title": "关于加快推进人工智能产业发展的新实施意见"}
        stats = tracker.record_snapshots(modified)

        assert stats["changes_detected"] == 1

    def test_detect_summary_change(self, tracker, sample_policies):
        """检测摘要变更"""
        tracker.record_snapshots(sample_policies)

        modified = sample_policies.copy()
        modified[1] = {**modified[1], "summary": "全新的摘要内容。"}
        stats = tracker.record_snapshots(modified)

        assert stats["changes_detected"] == 1

    def test_detect_score_change(self, tracker, sample_policies):
        """检测评分变更"""
        tracker.record_snapshots(sample_policies)

        modified = sample_policies.copy()
        modified[0] = {**modified[0], "score": 10}
        stats = tracker.record_snapshots(modified)

        assert stats["changes_detected"] == 1

    def test_multiple_changes(self, tracker, sample_policies):
        """同时检测多个变更"""
        tracker.record_snapshots(sample_policies)

        modified = [
            {**sample_policies[0], "title": "新标题", "score": 10},
            {**sample_policies[1], "summary": "新摘要"},
        ]
        stats = tracker.record_snapshots(modified)
        assert stats["changes_detected"] == 2

    def test_empty_url_skipped(self, tracker):
        """空 URL 的政策被跳过"""
        policies = [{"title": "无URL政策", "url": "", "summary": "test"}]
        stats = tracker.record_snapshots(policies)
        assert stats["new_policies"] == 0


# ============================================================
# 变更检测
# ============================================================


class TestDetectChanges:
    """测试变更检测"""

    def test_detect_all_changes(self, tracker, sample_policies):
        """检测所有变更"""
        tracker.record_snapshots(sample_policies)
        modified = [{**sample_policies[0], "title": "新标题"}]
        tracker.record_snapshots(modified)

        changes = tracker.detect_changes()
        assert len(changes) >= 1
        types = [c["change_type"] for c in changes]
        assert "title_changed" in types

    def test_detect_by_type(self, tracker, sample_policies):
        """按类型筛选变更"""
        tracker.record_snapshots(sample_policies)
        modified = [
            {**sample_policies[0], "title": "新标题"},
            {**sample_policies[1], "score": 10},
        ]
        tracker.record_snapshots(modified)

        title_changes = tracker.detect_changes(change_type="title_changed")
        score_changes = tracker.detect_changes(change_type="score_changed")
        assert len(title_changes) == 1
        assert len(score_changes) == 1

    def test_detect_with_limit(self, tracker, sample_policies):
        """限制返回条数"""
        tracker.record_snapshots(sample_policies)
        modified = [
            {**sample_policies[0], "title": "新标题"},
            {**sample_policies[1], "score": 10},
        ]
        tracker.record_snapshots(modified)

        changes = tracker.detect_changes(limit=1)
        assert len(changes) == 1

    def test_new_policy_detected_as_change(self, tracker, sample_policies):
        """新政策也被记录为变更"""
        tracker.record_snapshots(sample_policies)
        changes = tracker.detect_changes()
        new_changes = [c for c in changes if c["change_type"] == "new"]
        assert len(new_changes) == 2


# ============================================================
# 未通知变更
# ============================================================


class TestUnnotifiedChanges:
    """测试未通知变更"""

    def test_unnotified_after_record(self, tracker, sample_policies):
        """记录后有未通知变更"""
        tracker.record_snapshots(sample_policies)
        unnotified = tracker.detect_unnotified_changes()
        assert len(unnotified) == 2  # 2 条 new

    def test_mark_notified(self, tracker, sample_policies):
        """标记已通知"""
        tracker.record_snapshots(sample_policies)
        unnotified = tracker.detect_unnotified_changes()
        ids = [c["id"] for c in unnotified[:1]]
        tracker.mark_notified(ids)

        remaining = tracker.detect_unnotified_changes()
        assert len(remaining) == 1


# ============================================================
# 政策历史
# ============================================================


class TestPolicyHistory:
    """测试政策历史"""

    def test_history_after_record(self, tracker, sample_policies):
        """记录后有历史"""
        tracker.record_snapshots(sample_policies)
        history = tracker.get_policy_history(sample_policies[0]["url"])
        assert len(history) >= 1

    def test_history_after_change(self, tracker, sample_policies):
        """变更后历史增长"""
        tracker.record_snapshots(sample_policies)
        tracker.record_snapshots([{**sample_policies[0], "title": "新标题"}])
        history = tracker.get_policy_history(sample_policies[0]["url"])
        assert len(history) >= 2

    def test_history_nonexistent_url(self, tracker):
        """不存在的 URL"""
        history = tracker.get_policy_history("https://nonexistent.com")
        assert len(history) == 0


# ============================================================
# 变更统计
# ============================================================


class TestChangeStats:
    """测试变更统计"""

    def test_stats_empty(self, tracker):
        """空库统计"""
        stats = tracker.get_change_stats()
        assert isinstance(stats, dict)
        assert stats.get("total_tracked_policies", 0) == 0

    def test_stats_with_data(self, tracker, sample_policies):
        """有数据时统计"""
        tracker.record_snapshots(sample_policies)
        stats = tracker.get_change_stats()
        assert stats["total_tracked_policies"] >= 2
        assert stats["total_changes"] >= 2


# ============================================================
# 报告生成
# ============================================================


class TestGenerateReport:
    """测试报告生成"""

    def test_generate_report(self, tracker, sample_policies):
        """生成变更报告"""
        tracker.record_snapshots(sample_policies)
        changes = tracker.detect_changes()
        report = tracker.generate_change_report(changes)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_report_default(self, tracker, sample_policies):
        """使用默认参数生成报告"""
        tracker.record_snapshots(sample_policies)
        report = tracker.generate_change_report()
        assert isinstance(report, str)

    def test_report_saved_to_file(self, tracker, sample_policies):
        """报告文件被保存"""
        tracker.record_snapshots(sample_policies)
        report = tracker.generate_change_report()
        # 检查 output 目录下是否有 .md 文件
        output_files = list(Path(tracker.output_dir).glob("*.md"))
        assert len(output_files) >= 1


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    """边界情况"""

    def test_record_empty_list(self, tracker):
        """空列表记录"""
        stats = tracker.record_snapshots([])
        assert stats["new_policies"] == 0

    def test_record_policy_missing_fields(self, tracker):
        """缺少字段的政策"""
        policy = {"url": "https://example.com/min"}
        stats = tracker.record_snapshots([policy])
        assert stats["new_policies"] == 1

    def test_consecutive_records(self, tracker, sample_policies):
        """连续多次记录"""
        for _ in range(3):
            tracker.record_snapshots(sample_policies)
        history = tracker.get_policy_history(sample_policies[0]["url"])
        assert len(history) >= 1
