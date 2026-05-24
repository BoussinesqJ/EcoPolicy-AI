# -*- coding: utf-8 -*-
"""
反馈管理模块

让系统从"单向输出"变为"闭环学习"：
  用户审阅简报 -> 记录采纳/拒绝 -> 追踪最终结果 -> 反馈打分 -> 积累数据

反馈流程:
  1. 用户收到简报后，记录是否采纳 (accepted/rejected)
  2. 采纳后，追踪最终结果 (submitted/approved/rejected/not_applicable)
  3. 事后打分：AI 推荐准确性 + 分析有用性 (1-5)
  4. 定期汇总：统计准确率，优化匹配权重
"""

import logging
from pathlib import Path

logger = logging.getLogger("agent.feedback")


class FeedbackManager:
    """反馈管理器"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "policy_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_db(self):
        """获取数据库连接"""
        import sys
        pm_dir = str(self.base_dir / "policy_monitor")
        if pm_dir not in sys.path:
            sys.path.insert(0, pm_dir)
        from database import PolicyDatabase
        return PolicyDatabase(
            str(self.data_dir / "policies.db"),
            str(self.data_dir),
        )

    def submit_action(self, policy_url_hash: str, enterprise_id: str,
                      action: str, detail: str = ""):
        """提交简报审阅反馈

        Args:
            policy_url_hash: 政策 URL hash
            enterprise_id: 企业 ID
            action: accepted / rejected / pending
            detail: 用户备注
        """
        db = self._get_db()
        try:
            db.submit_feedback(policy_url_hash, enterprise_id, action, detail)
            logger.info(f"反馈已提交: {enterprise_id} - {action}")
            print(f"\n  Feedback recorded: {action}")
            print(f"  Enterprise: {enterprise_id}")
            print(f"  Policy: {policy_url_hash[:12]}...")
            if detail:
                print(f"  Notes: {detail}")
        finally:
            db.close()

    def update_outcome(self, policy_url_hash: str, enterprise_id: str,
                       outcome: str, detail: str = ""):
        """更新最终结果

        Args:
            outcome: submitted / approved / rejected / not_applicable
            detail: 结果详情
        """
        db = self._get_db()
        try:
            db.update_outcome(policy_url_hash, enterprise_id, outcome, detail)
            logger.info(f"结果已更新: {enterprise_id} - {outcome}")
            print(f"\n  Outcome updated: {outcome}")
            if detail:
                print(f"  Detail: {detail}")
        finally:
            db.close()

    def submit_scores(self, policy_url_hash: str, enterprise_id: str,
                      accuracy: int, usefulness: int, notes: str = ""):
        """提交事后评分

        Args:
            accuracy: AI 推荐准确性 1-5
            usefulness: 分析有用性 1-5
            notes: 用户反馈备注
        """
        if not (1 <= accuracy <= 5 and 1 <= usefulness <= 5):
            print("  Scores must be between 1-5")
            return

        db = self._get_db()
        try:
            db.submit_feedback_scores(
                policy_url_hash, enterprise_id,
                accuracy, usefulness, notes,
            )
            logger.info(f"评分已提交: accuracy={accuracy}, usefulness={usefulness}")
            print(f"\n  Scores recorded:")
            print(f"  AI accuracy: {accuracy}/5")
            print(f"  Usefulness:  {usefulness}/5")
            if notes:
                print(f"  Notes: {notes}")
        finally:
            db.close()

    def list_feedback(self, enterprise_id: str = None):
        """列出反馈记录"""
        db = self._get_db()
        try:
            records = db.get_feedback(enterprise_id)
            if not records:
                print("\n  No feedback records\n")
                return

            print(f"\n{'=' * 60}")
            print(f"  Feedback Records ({len(records)} total)")
            print(f"{'=' * 60}")

            for r in records:
                action_icon = {
                    "accepted": "[+]",
                    "rejected": "[-]",
                    "pending": "[?]",
                }.get(r["action"], "[?]")

                outcome_icon = {
                    "pending": "...",
                    "submitted": "[>]",
                    "approved": "[OK]",
                    "rejected": "[X]",
                    "not_applicable": "[-]",
                }.get(r["outcome"], "...")

                title = (r.get("policy_title") or "")[:40]
                enterprise = r["enterprise_id"]

                print(f"\n  {action_icon} {title}")
                print(f"     Enterprise: {enterprise}")
                print(f"     Action: {r['action']} | Outcome: {outcome_icon} {r['outcome']}")

                if r.get("accuracy_score"):
                    print(f"     Scores: accuracy {r['accuracy_score']}/5"
                          f" | usefulness {r['usefulness_score']}/5")

                if r.get("feedback_notes"):
                    print(f"     Notes: {r['feedback_notes']}")

                print(f"     Time: {r['created_at']}")

            print(f"\n{'=' * 60}\n")
        finally:
            db.close()

    def show_stats(self):
        """显示反馈统计"""
        db = self._get_db()
        try:
            stats = db.get_feedback_stats()
            if stats["total"] == 0:
                print("\n  No feedback data available for statistics\n")
                return

            acceptance_rate = (
                round(stats["accepted"] / stats["total"] * 100, 1)
                if stats["total"] > 0 else 0
            )
            approval_rate = (
                round(stats["approved"] / stats["accepted"] * 100, 1)
                if stats["accepted"] > 0 else 0
            )

            print(f"\n{'=' * 50}")
            print(f"  Feedback Statistics")
            print(f"{'=' * 50}")
            print(f"  Total feedback:   {stats['total']}")
            print(f"  Accepted:         {stats['accepted']} ({acceptance_rate}%)")
            print(f"  Rejected:         {stats['rejected']}")
            print(f"  Pending:          {stats['pending']}")
            print(f"  Submitted:        {stats['submitted']}")
            print(f"  Approved:         {stats['approved']} ({approval_rate}%)")
            print(f"  AI accuracy avg:  {stats['avg_accuracy']}/5")
            print(f"  Usefulness avg:   {stats['avg_usefulness']}/5")
            print(f"{'=' * 50}\n")
        finally:
            db.close()
