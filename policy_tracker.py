# -*- coding: utf-8 -*-
"""
政策历史版本对比模块

功能:
  1. 记录政策快照（标题/摘要/关键词），追踪修订变化
  2. 检测同一政策 URL 的标题变更或内容更新
  3. 生成变更对比报告 (.md)
  4. 支持按企业/行业/日期范围筛选变更

用法:
  from policy_tracker import PolicyTracker
  tracker = PolicyTracker(db_path, output_dir)
  tracker.record_snapshots(policies)     # 记录当前快照
  changes = tracker.detect_changes()      # 检测变更
  tracker.generate_change_report(changes) # 生成报告
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from enterprise_matcher import _hash_url

logger = logging.getLogger("policy_tracker")

# ============================================================
# 数据库 Schema 扩展
# ============================================================

TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    keywords_matched TEXT,       -- JSON array
    score INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'P2',
    source TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(url_hash, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_hash ON policy_snapshots(url_hash);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON policy_snapshots(recorded_at);

-- 政策变更记录表
CREATE TABLE IF NOT EXISTS policy_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT NOT NULL,
    policy_title TEXT,
    change_type TEXT NOT NULL,     -- "new" / "title_changed" / "summary_changed" / "keywords_changed" / "score_changed"
    old_value TEXT,
    new_value TEXT,
    detected_at TEXT NOT NULL,
    notified INTEGER DEFAULT 0    -- 0=未通知, 1=已通知
);

CREATE INDEX IF NOT EXISTS idx_changes_hash ON policy_changes(url_hash);
CREATE INDEX IF NOT EXISTS idx_changes_type ON policy_changes(change_type);
"""


class PolicyTracker:
    """政策历史版本追踪器"""

    def __init__(self, db_path: str, output_dir: str):
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(TRACKER_SCHEMA)
        self._conn.commit()
        logger.info(f"PolicyTracker initialized: {db_path}")

    def record_snapshots(self, policies: list[dict]) -> dict:
        """记录当前政策快照

        对于每条政策，检查是否已存在相同快照（标题+摘要未变则跳过）。
        如果有变化，记录新快照并标记为变更。

        Args:
            policies: 政策列表

        Returns:
            {"new_snapshots": int, "changes_detected": int, "new_policies": int}
        """
        stats = {"new_snapshots": 0, "changes_detected": 0, "new_policies": 0}
        now = datetime.now().isoformat()

        for policy in policies:
            url = policy.get("url", "")
            if not url:
                continue

            h = _hash_url(url)
            title = policy.get("title", "")
            summary = policy.get("summary", "")
            keywords = json.dumps(
                policy.get("keywords_matched", []), ensure_ascii=False
            )
            score = policy.get("score", 0)
            priority = policy.get("priority", "P2")
            source = policy.get("source", "")

            # 检查是否为全新政策
            existing = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM policy_snapshots WHERE url_hash = ?",
                (h,),
            ).fetchone()["cnt"]

            if existing == 0:
                # 全新政策 -> 记录快照 + 标记为 new
                self._insert_snapshot(
                    h, title, summary, keywords, score, priority, source, now
                )
                self._insert_change(
                    h, title, "new", "", title, now
                )
                stats["new_policies"] += 1
                stats["new_snapshots"] += 1
                continue

            # 已有政策 -> 对比最新快照
            latest = self._conn.execute(
                """SELECT * FROM policy_snapshots
                   WHERE url_hash = ?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (h,),
            ).fetchone()

            if not latest:
                continue

            has_change = False

            # 对比标题
            if latest["title"] != title:
                self._insert_change(
                    h, title, "title_changed",
                    latest["title"], title, now
                )
                has_change = True

            # 对比摘要
            if latest["summary"] != summary:
                self._insert_change(
                    h, title, "summary_changed",
                    latest["summary"][:200] if latest["summary"] else "",
                    summary[:200] if summary else "",
                    now,
                )
                has_change = True

            # 对比关键词
            if latest["keywords_matched"] != keywords:
                self._insert_change(
                    h, title, "keywords_changed",
                    latest["keywords_matched"], keywords, now
                )
                has_change = True

            # 对比评分
            if latest["score"] != score:
                self._insert_change(
                    h, title, "score_changed",
                    str(latest["score"]), str(score), now
                )
                has_change = True

            # 记录新快照
            if has_change:
                self._insert_snapshot(
                    h, title, summary, keywords, score, priority, source, now
                )
                stats["changes_detected"] += 1
                stats["new_snapshots"] += 1

        self._conn.commit()
        logger.info(
            f"Snapshots recorded: +{stats['new_snapshots']} new, "
            f"{stats['changes_detected']} changed, "
            f"{stats['new_policies']} new policies"
        )
        return stats

    def detect_changes(
        self,
        date_from: str = None,
        date_to: str = None,
        change_type: str = None,
        limit: int = 100,
    ) -> list:
        """检测政策变更

        Args:
            date_from: 起始日期 YYYY-MM-DD
            date_to: 截止日期 YYYY-MM-DD
            change_type: 指定变更类型 (new/title_changed/summary_changed/...)
            limit: 最多返回条数

        Returns:
            变更列表 [{"url_hash", "policy_title", "change_type", "old_value", "new_value", "detected_at"}]
        """
        conditions = []
        params = []

        if date_from:
            conditions.append("detected_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("detected_at <= ?")
            params.append(date_to + "T23:59:59")
        if change_type:
            conditions.append("change_type = ?")
            params.append(change_type)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM policy_changes{where} ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def detect_unnotified_changes(self) -> list:
        """获取未通知的变更"""
        rows = self._conn.execute(
            """SELECT * FROM policy_changes
               WHERE notified = 0
               ORDER BY detected_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_notified(self, change_ids: list[int]):
        """标记变更已通知"""
        if not change_ids:
            return
        placeholders = ",".join("?" * len(change_ids))
        self._conn.execute(
            f"UPDATE policy_changes SET notified = 1 WHERE id IN ({placeholders})",
            tuple(change_ids),
        )
        self._conn.commit()

    def get_policy_history(self, url: str) -> list:
        """获取某条政策的完整历史"""
        h = _hash_url(url)
        rows = self._conn.execute(
            """SELECT * FROM policy_snapshots
               WHERE url_hash = ?
               ORDER BY recorded_at ASC""",
            (h,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_change_stats(self) -> dict:
        """获取变更统计"""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM policy_changes"
        ).fetchone()[0]

        by_type = self._conn.execute(
            "SELECT change_type, COUNT(*) as cnt FROM policy_changes GROUP BY change_type"
        ).fetchall()

        unnotified = self._conn.execute(
            "SELECT COUNT(*) FROM policy_changes WHERE notified = 0"
        ).fetchone()[0]

        total_snapshots = self._conn.execute(
            "SELECT COUNT(DISTINCT url_hash) FROM policy_snapshots"
        ).fetchone()[0]

        return {
            "total_tracked_policies": total_snapshots,
            "total_changes": total,
            "by_type": {r["change_type"]: r["cnt"] for r in by_type},
            "unnotified": unnotified,
        }

    def generate_change_report(
        self,
        changes: list = None,
        title: str = None,
    ) -> str:
        """生成变更对比报告 (.md)

        Args:
            changes: 变更列表（None 则自动检测未通知的变更）
            title: 报告标题

        Returns:
            报告文件路径
        """
        if changes is None:
            changes = self.detect_unnotified_changes()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = self.output_dir / f"policy_changes_{date_str}.md"

        stats = self.get_change_stats()

        lines = []
        lines.append("---")
        lines.append(f'title: "{title or "政策变更追踪报告"}"')
        lines.append(f'date: "{date_str}"')
        lines.append(f'author: "EcoPolicy PolicyTracker"')
        lines.append(f"type: 政策变更追踪")
        lines.append("---")
        lines.append("")
        lines.append("# 政策变更追踪报告")
        lines.append("")
        lines.append(
            f"> 系统追踪 **{stats['total_tracked_policies']}** 条政策，"
            f"累计检测到 **{stats['total_changes']}** 次变更，"
            f"其中 **{stats['unnotified']}** 条未通知。"
        )
        lines.append("")

        if not changes:
            lines.append("---")
            lines.append("")
            lines.append("## 无新变更")
            lines.append("")
            lines.append("自上次检查以来，未发现政策变更。")
        else:
            lines.append("---")
            lines.append("")
            lines.append(f"## 本次变更 ({len(changes)} 条)")
            lines.append("")

            # 按变更类型分组
            by_type = {}
            for c in changes:
                ct = c.get("change_type", "unknown")
                if ct not in by_type:
                    by_type[ct] = []
                by_type[ct].append(c)

            type_labels = {
                "new": "新增政策",
                "title_changed": "标题变更",
                "summary_changed": "摘要/内容变更",
                "keywords_changed": "关键词变更",
                "score_changed": "评分变更",
            }

            for ct, items in by_type.items():
                label = type_labels.get(ct, ct)
                lines.append(f"### {label} ({len(items)} 条)")
                lines.append("")

                if ct == "new":
                    for c in items:
                        lines.append(f"- **{c.get('policy_title', 'N/A')}**")
                        lines.append(f"  - 变更时间: {c.get('detected_at', '')[:19]}")
                        lines.append("")
                else:
                    lines.append("| 政策 | 旧值 | 新值 | 时间 |")
                    lines.append("|:------|:------|:------|:--|")
                    for c in items:
                        old_val = (c.get("old_value") or "")[:40]
                        new_val = (c.get("new_value") or "")[:40]
                        title_short = (c.get("policy_title") or "")[:30]
                        time_str = (c.get("detected_at") or "")[:16]
                        lines.append(
                            f"| {title_short} | {old_val} | {new_val} | {time_str} |"
                        )
                    lines.append("")

            lines.append("---")
            lines.append("")

        # 变更统计
        lines.append("## 变更统计")
        lines.append("")
        lines.append("| 维度 | 数值 |")
        lines.append("|:------|:--:|")
        lines.append(f"| 追踪政策数 | {stats['total_tracked_policies']} |")
        lines.append(f"| 累计变更数 | {stats['total_changes']} |")
        lines.append(f"| 未通知数 | {stats['unnotified']} |")
        lines.append("")
        lines.append("### 按类型统计")
        lines.append("")
        lines.append("| 变更类型 | 次数 |")
        lines.append("|:------|:--:|")
        for ct, cnt in stats.get("by_type", {}).items():
            label = type_labels.get(ct, ct)
            lines.append(f"| {label} | {cnt} |")
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            f"*本报告由 EcoPolicy PolicyTracker 自动生成于 {now}*"
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Change report generated: {report_path}")
        return str(report_path)

    # ============================================================
    # 内部方法
    # ============================================================

    def _insert_snapshot(
        self, url_hash, title, summary, keywords, score, priority, source, now
    ):
        """插入快照（忽略重复）"""
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO policy_snapshots
                   (url_hash, title, summary, keywords_matched, score,
                    priority, source, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (url_hash, title, summary, keywords, score, priority, source, now),
            )
        except sqlite3.IntegrityError:
            pass

    def _insert_change(self, url_hash, title, change_type, old_value, new_value, now):
        """插入变更记录"""
        try:
            self._conn.execute(
                """INSERT INTO policy_changes
                   (url_hash, policy_title, change_type, old_value,
                    new_value, detected_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url_hash, title, change_type, old_value, new_value, now),
            )
        except sqlite3.IntegrityError:
            pass

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
