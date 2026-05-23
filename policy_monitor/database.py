# -*- coding: utf-8 -*-
"""
SQLite 存储 + JSON/CSV 导出
- 去重：URL hash
- 结构化存储
- 导出最新政策
"""

import json
import csv
import sqlite3
import logging
from pathlib import Path

from utils import url_hash, today_str, now_iso

logger = logging.getLogger("policy_monitor")

SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    date TEXT,
    source TEXT,
    summary TEXT,
    keywords_matched TEXT,       -- JSON array
    score INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'P2',  -- P0 / P1 / P2
    fetched_at TEXT NOT NULL,
    analyzed INTEGER DEFAULT 0   -- 0=未分析, 1=已分析
);

CREATE INDEX IF NOT EXISTS idx_date ON policies(date);
CREATE INDEX IF NOT EXISTS idx_priority ON policies(priority);
CREATE INDEX IF NOT EXISTS idx_source ON policies(source);

-- Agent: 企业匹配结果表
CREATE TABLE IF NOT EXISTS enterprise_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_url_hash TEXT NOT NULL,
    enterprise_id TEXT NOT NULL,
    hard_conditions_pass INTEGER DEFAULT 0,
    hard_conditions_detail TEXT,       -- JSON: 各条件通过/未通过明细
    score_tech INTEGER DEFAULT 0,
    score_prod INTEGER DEFAULT 0,
    score_mkt INTEGER DEFAULT 0,
    score_cap INTEGER DEFAULT 0,
    score_total INTEGER DEFAULT 0,
    recommendation TEXT DEFAULT '',    -- "5/5 首选推荐" 等
    recommendation_score INTEGER DEFAULT 0,
    urgency TEXT DEFAULT 'P2',         -- P0/P1/P2
    brief_generated INTEGER DEFAULT 0,
    brief_path TEXT,
    matched_at TEXT NOT NULL,
    UNIQUE(policy_url_hash, enterprise_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_policy ON enterprise_matches(policy_url_hash);
CREATE INDEX IF NOT EXISTS idx_matches_enterprise ON enterprise_matches(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_matches_urgency ON enterprise_matches(urgency);

-- Agent: 运行日志表
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,             -- "full" / "scan" / "match"
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT DEFAULT 'running',     -- running / completed / error
    policies_scanned INTEGER DEFAULT 0,
    policies_new INTEGER DEFAULT 0,
    matches_found INTEGER DEFAULT 0,
    briefs_generated INTEGER DEFAULT 0,
    error_message TEXT
);
"""


class PolicyDatabase:
    """政策数据库"""

    def __init__(self, db_path: str, export_dir: str):
        self.db_path = db_path
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        logger.info(f"数据库已初始化: {db_path}")

    def insert(self, policy: dict) -> bool:
        """
        插入一条政策记录。
        返回 True 表示新记录，False 表示已存在（去重）。
        """
        h = url_hash(policy["url"])

        # 检查是否已存在
        row = self.conn.execute(
            "SELECT url_hash FROM policies WHERE url_hash = ?", (h,)
        ).fetchone()
        if row:
            logger.debug(f"已存在，跳过: {policy['title'][:40]}")
            return False

        self.conn.execute(
            """INSERT INTO policies
               (url_hash, title, url, date, source, summary,
                keywords_matched, score, priority, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                h,
                policy.get("title", ""),
                policy.get("url", ""),
                policy.get("date", ""),
                policy.get("source", ""),
                policy.get("summary", ""),
                json.dumps(policy.get("keywords_matched", []), ensure_ascii=False),
                policy.get("score", 0),
                policy.get("priority", "P2"),
                policy.get("fetched_at", now_iso()),
            ),
        )
        self.conn.commit()
        logger.info(f"新增: [{policy.get('priority', 'P2')}] {policy['title'][:50]}")
        return True

    def insert_batch(self, policies: list[dict]) -> int:
        """批量插入，返回新增数量"""
        new_count = 0
        for p in policies:
            if self.insert(p):
                new_count += 1
        return new_count

    def get_latest(self, limit: int = 100) -> list[dict]:
        """获取最新政策（按日期降序）"""
        rows = self.conn.execute(
            "SELECT * FROM policies ORDER BY date DESC, fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_new_today(self) -> list[dict]:
        """获取今天新抓取的政策"""
        today = today_str()
        rows = self.conn.execute(
            "SELECT * FROM policies WHERE fetched_at LIKE ? ORDER BY score DESC",
            (f"{today}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unanalyzed(self) -> list[dict]:
        """获取未分析的高优先级政策"""
        rows = self.conn.execute(
            "SELECT * FROM policies WHERE analyzed = 0 AND priority IN ('P0', 'P1') ORDER BY score DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_analyzed(self, url_hash_val: str):
        """标记为已分析"""
        self.conn.execute(
            "UPDATE policies SET analyzed = 1 WHERE url_hash = ?", (url_hash_val,)
        )
        self.conn.commit()

    def stats(self) -> dict:
        """统计信息"""
        total = self.conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        p0 = self.conn.execute("SELECT COUNT(*) FROM policies WHERE priority='P0'").fetchone()[0]
        p1 = self.conn.execute("SELECT COUNT(*) FROM policies WHERE priority='P1'").fetchone()[0]
        p2 = self.conn.execute("SELECT COUNT(*) FROM policies WHERE priority='P2'").fetchone()[0]
        sources = self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM policies GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total": total,
            "P0": p0,
            "P1": p1,
            "P2": p2,
            "by_source": {r["source"]: r["cnt"] for r in sources},
        }

    def export_json(self, limit: int = 200):
        """导出最新政策为 JSON"""
        policies = self.get_latest(limit)
        out_path = self.export_dir / "latest.json"

        # 解析 keywords_matched 字段
        for p in policies:
            if isinstance(p.get("keywords_matched"), str):
                try:
                    p["keywords_matched"] = json.loads(p["keywords_matched"])
                except json.JSONDecodeError:
                    p["keywords_matched"] = []

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {"exported_at": now_iso(), "count": len(policies), "policies": policies},
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"JSON 导出: {out_path} ({len(policies)} 条)")

    def export_csv(self, limit: int = 200):
        """导出最新政策为 CSV"""
        policies = self.get_latest(limit)
        out_path = self.export_dir / "latest.csv"

        fields = ["title", "url", "date", "source", "priority", "score", "keywords_matched", "summary", "fetched_at"]
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for p in policies:
                row = dict(p)
                km = row.get("keywords_matched", [])
                if isinstance(km, str):
                    row["keywords_matched"] = km
                elif isinstance(km, list):
                    row["keywords_matched"] = "; ".join(km)
                writer.writerow(row)

        logger.info(f"CSV 导出: {out_path} ({len(policies)} 条)")

    def export_all(self):
        """导出 JSON + CSV"""
        self.export_json()
        self.export_csv()

    # ============================================================
    # Agent: 企业匹配结果
    # ============================================================

    def insert_match(self, match: dict) -> bool:
        """插入一条企业匹配结果，返回 True 表示新增"""
        try:
            self.conn.execute(
                """INSERT INTO enterprise_matches
                   (policy_url_hash, enterprise_id, hard_conditions_pass,
                    hard_conditions_detail, score_tech, score_prod, score_mkt,
                    score_cap, score_total, recommendation, recommendation_score,
                    urgency, matched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    match["policy_url_hash"],
                    match["enterprise_id"],
                    match.get("hard_conditions_pass", 0),
                    json.dumps(match.get("hard_conditions_detail", {}), ensure_ascii=False),
                    match.get("score_tech", 0),
                    match.get("score_prod", 0),
                    match.get("score_mkt", 0),
                    match.get("score_cap", 0),
                    match.get("score_total", 0),
                    match.get("recommendation", ""),
                    match.get("recommendation_score", 0),
                    match.get("urgency", "P2"),
                    match.get("matched_at", now_iso()),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def mark_brief_generated(self, policy_url_hash: str, enterprise_id: str, brief_path: str):
        """标记简报已生成"""
        self.conn.execute(
            """UPDATE enterprise_matches
               SET brief_generated = 1, brief_path = ?
               WHERE policy_url_hash = ? AND enterprise_id = ?""",
            (brief_path, policy_url_hash, enterprise_id),
        )
        self.conn.commit()

    def get_matches_for_enterprise(self, enterprise_id: str) -> list[dict]:
        """获取某企业的所有匹配结果"""
        rows = self.conn.execute(
            """SELECT em.*, p.title as policy_title, p.url as policy_url,
                      p.source as policy_source, p.date as policy_date
               FROM enterprise_matches em
               JOIN policies p ON em.policy_url_hash = p.url_hash
               WHERE em.enterprise_id = ?
               ORDER BY em.score_total DESC""",
            (enterprise_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ============================================================
    # Agent: 运行日志
    # ============================================================

    def record_agent_run(self, run_type: str) -> int:
        """记录一次 Agent 运行，返回 run_id"""
        cursor = self.conn.execute(
            """INSERT INTO agent_runs (run_type, started_at, status)
               VALUES (?, ?, 'running')""",
            (run_type, now_iso()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def finish_agent_run(self, run_id: int, **kwargs):
        """完成一次 Agent 运行"""
        fields = []
        values = []
        fields.append("finished_at = ?")
        values.append(now_iso())
        fields.append("status = ?")
        values.append(kwargs.get("status", "completed"))
        for key in ["policies_scanned", "policies_new", "matches_found",
                     "briefs_generated", "error_message"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        values.append(run_id)
        self.conn.execute(
            f"UPDATE agent_runs SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        self.conn.commit()

    def get_recent_agent_runs(self, limit: int = 10) -> list[dict]:
        """获取最近的 Agent 运行记录"""
        rows = self.conn.execute(
            "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """关闭连接"""
        self.conn.close()
