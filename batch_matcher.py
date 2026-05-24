# -*- coding: utf-8 -*-
"""
批量匹配模块

功能:
  1. 一次性扫描数据库中所有政策，与所有企业画像批量匹配
  2. 按企业分组输出匹配结果排行
  3. 生成汇总报告 (.md)
  4. 支持按企业/行业/日期范围/最低分筛选

用法:
  from batch_matcher import BatchMatcher
  bm = BatchMatcher(db_path, enterprises_dir, output_dir)
  report = bm.run()                    # 全量匹配
  report = bm.run(enterprise_id="jyuh") # 指定企业
  report = bm.run(min_score=9)          # 只输出 >= 3/5 的结果
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from enterprise_matcher import EnterpriseMatcher, _hash_url

logger = logging.getLogger("batch_matcher")


class BatchMatcher:
    """批量匹配引擎"""

    def __init__(self, db_path: str, enterprises_dir: str, output_dir: str):
        self.db_path = Path(db_path)
        self.enterprises_dir = Path(enterprises_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.matcher = EnterpriseMatcher(str(enterprises_dir))
        self._conn = None

    def _get_conn(self):
        """延迟加载数据库连接"""
        if self._conn is None:
            import sqlite3
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def run(
        self,
        enterprise_id: str = None,
        min_score: int = 5,
        date_from: str = None,
        date_to: str = None,
        source: str = None,
        limit: int = 500,
    ) -> dict:
        """执行批量匹配

        Args:
            enterprise_id: 指定企业 ID，None 表示所有企业
            min_score: 最低总分过滤（默认 5，即 1/5 以上）
            date_from: 起始日期 YYYY-MM-DD
            date_to: 截止日期 YYYY-MM-DD
            source: 指定数据源
            limit: 最多加载政策数

        Returns:
            {
                "total_policies": int,
                "total_matches": int,
                "enterprises": {ent_id: {profile, matches: [...]}},
                "generated_at": str,
                "report_path": str,
            }
        """
        # 加载企业
        enterprises = list(self.matcher.enterprises.keys())
        if not enterprises:
            logger.warning("No enterprises found in enterprises/")
            return {"error": "No enterprises registered"}

        if enterprise_id and enterprise_id not in self.matcher.enterprises:
            logger.error(f"Enterprise not found: {enterprise_id}")
            return {"error": f"Enterprise not found: {enterprise_id}"}

        # 加载政策
        policies = self._load_policies(date_from, date_to, source, limit)
        if not policies:
            logger.warning("No policies in database")
            return {"error": "No policies in database"}

        logger.info(
            f"Batch matching: {len(policies)} policies x "
            f"{len(self.matcher.enterprises)} enterprises"
        )

        # 执行匹配
        target_ids = [enterprise_id] if enterprise_id else enterprises
        results_by_enterprise = {}

        for eid in target_ids:
            ent = self.matcher.enterprises.get(eid)
            if not ent:
                continue

            matches = []
            for policy in policies:
                result = self.matcher._match_single(policy, ent)
                if result and result.score_total >= min_score:
                    matches.append(result)

            # 按总分降序排列
            matches.sort(key=lambda r: r.score_total, reverse=True)

            results_by_enterprise[eid] = {
                "profile": ent["profile"],
                "matches": matches,
                "total_matched": len(matches),
            }

        # 生成报告
        total_matches = sum(
            len(v["matches"]) for v in results_by_enterprise.values()
        )
        report_data = {
            "total_policies": len(policies),
            "total_matches": total_matches,
            "enterprises": results_by_enterprise,
            "generated_at": datetime.now().isoformat(),
        }

        report_path = self._generate_report(report_data)
        report_data["report_path"] = str(report_path)

        logger.info(
            f"Batch match complete: {total_matches} matches "
            f"from {len(policies)} policies"
        )
        return report_data

    def _load_policies(
        self,
        date_from: str = None,
        date_to: str = None,
        source: str = None,
        limit: int = 500,
    ) -> list:
        """从数据库加载政策"""
        conn = self._get_conn()

        conditions = []
        params = []

        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)
        if source:
            conditions.append("source = ?")
            params.append(source)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM policies{where} ORDER BY date DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()

        # 解析 keywords_matched JSON
        policies = []
        for row in rows:
            p = dict(row)
            if isinstance(p.get("keywords_matched"), str):
                try:
                    p["keywords_matched"] = json.loads(p["keywords_matched"])
                except json.JSONDecodeError:
                    p["keywords_matched"] = []
            policies.append(p)

        return policies

    def _generate_report(self, data: dict) -> Path:
        """生成批量匹配汇总报告 (.md)"""
        now = datetime.now().strftime("%Y-%m-%d")
        report_path = self.output_dir / f"batch_match_report_{now}.md"

        lines = []
        lines.append(f"---")
        lines.append(f'title: "批量匹配报告"')
        lines.append(f'date: "{now}"')
        lines.append(f'author: "EcoPolicy BatchMatcher"')
        lines.append(f"type: 批量匹配汇总")
        lines.append(f'---')
        lines.append("")
        lines.append("# 批量匹配报告")
        lines.append("")
        lines.append(
            f"> 共扫描 **{data['total_policies']}** 条政策，"
            f"产出 **{data['total_matches']}** 条匹配结果。"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        for eid, edata in data["enterprises"].items():
            profile = edata["profile"]
            matches = edata["matches"]
            ent_name = profile.get("basic_info", {}).get("short_name", eid)
            sector = profile.get("industry", {}).get("primary_sector", "N/A")

            lines.append(f"## {ent_name}")
            lines.append("")
            lines.append(f"- **行业**: {sector}")
            lines.append(f"- **匹配数**: {len(matches)} 条政策")
            lines.append("")

            if not matches:
                lines.append("> 未发现匹配度 >= 3/5 的政策。")
                lines.append("")
                lines.append("---")
                lines.append("")
                continue

            # 汇总表格
            lines.append("### 排行榜")
            lines.append("")
            lines.append("| 排名 | 政策 | 推荐 | 总分 | Tech | Prod | Mkt | Cap | 来源 | 日期 |")
            lines.append("|:--:|:------|:--:|:--:|:--:|:--:|:--:|:--:|:--|:--|")

            for i, m in enumerate(matches[:20], 1):
                title_short = m.policy_title[:35] + ("..." if len(m.policy_title) > 35 else "")
                lines.append(
                    f"| {i} "
                    f"| {title_short} "
                    f"| {m.recommendation} "
                    f"| {m.score_total}/20 "
                    f"| {m.score_tech} "
                    f"| {m.score_prod} "
                    f"| {m.score_mkt} "
                    f"| {m.score_cap} "
                    f"| {m.policy_source} "
                    f"| {m.policy_date} |"
                )

            lines.append("")

            # 5/5 首选推荐详情
            top_matches = [m for m in matches if m.recommendation_score >= 5]
            if top_matches:
                lines.append("### 5/5 首选推荐详情")
                lines.append("")
                for m in top_matches:
                    lines.append(f"#### {m.policy_title}")
                    lines.append("")
                    lines.append(f"- **来源**: {m.policy_source}")
                    lines.append(f"- **日期**: {m.policy_date}")
                    lines.append(f"- **链接**: [{m.policy_url[:60]}...]({m.policy_url})")
                    lines.append(f"- **推荐理由**: 总分 {m.score_total}/20")
                    if m.matched_keywords:
                        lines.append(
                            f"- **匹配关键词**: {', '.join(m.matched_keywords[:10])}"
                        )
                    if m.opportunities:
                        lines.append("- **机会**:")
                        for o in m.opportunities:
                            lines.append(f"  - {o}")
                    lines.append("")

            # 4/5 强烈推荐摘要
            strong_matches = [m for m in matches if m.recommendation_score == 4]
            if strong_matches:
                lines.append("### 4/5 强烈推荐摘要")
                lines.append("")
                lines.append("| 政策 | 总分 | 匹配关键词 |")
                lines.append("|:------|:--:|:------|")
                for m in strong_matches:
                    kws = ", ".join(m.matched_keywords[:5])
                    lines.append(f"| {m.policy_title[:40]} | {m.score_total}/20 | {kws} |")
                lines.append("")

            lines.append("---")
            lines.append("")

        # 结论
        lines.append("## 下一步建议")
        lines.append("")
        lines.append("1. 对 **5/5 首选推荐** 的政策执行六步深度分析")
        lines.append("2. 对 **4/5 强烈推荐** 的政策择优分析")
        lines.append("3. 关注 **P0 紧急** 政策的截止时间")
        lines.append("")
        lines.append(
            f"*本报告由 EcoPolicy BatchMatcher 自动生成于 "
            f"{data['generated_at'][:19]}*"
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Report generated: {report_path}")
        return report_path

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
