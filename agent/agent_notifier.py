# -*- coding: utf-8 -*-
"""
Agent 通知器

多渠道通知:
  - 控制台输出
  - 文件（每日摘要 Markdown）
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("agent.notifier")


class AgentNotifier:
    """Agent 通知器"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.alerts_dir = self.base_dir / "policy_data" / "alerts"
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

    def send_digest(self, matches: list, scan_stats: dict = None):
        """生成并输出每日摘要

        Args:
            matches: MatchResult 列表
            scan_stats: 扫描统计 {policies_scanned, policies_new, ...}
        """
        if matches:
            self._print_digest(matches, scan_stats)
            self._save_digest(matches, scan_stats)
        else:
            logger.info("本次无新匹配结果")
            if scan_stats:
                print(f"\n  Scan complete: {scan_stats.get('policies_scanned', 0)} scanned, "
                      f"{scan_stats.get('policies_new', 0)} new")
                print(f"  No new high-match policies\n")

    def _print_digest(self, matches: list, scan_stats: dict = None):
        """控制台输出摘要"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        p0_count = sum(1 for m in matches if m.urgency == "P0")
        p1_count = sum(1 for m in matches if m.urgency == "P1")
        rec5 = sum(1 for m in matches if m.recommendation_score == 5)
        rec4 = sum(1 for m in matches if m.recommendation_score == 4)
        rec3 = sum(1 for m in matches if m.recommendation_score == 3)

        print(f"\n{'=' * 60}")
        print(f"  EcoPolicy Agent - Match Summary  {now}")
        print(f"{'=' * 60}")
        if scan_stats:
            print(f"  Scanned: {scan_stats.get('policies_scanned', 0)} | "
                  f"New: {scan_stats.get('policies_new', 0)}")
        print(f"  Matches: {len(matches)} (5/5: {rec5} | 4/5: {rec4} | 3/5: {rec3})")
        print(f"  Priority: P0={p0_count} | P1={p1_count}")
        print(f"{'-' * 60}")

        # 按推荐等级分组输出
        for level, label in [(5, "5/5 Top Pick"), (4, "4/5 Strongly Recommended"), (3, "3/5 Recommended")]:
            group = [m for m in matches if m.recommendation_score == level]
            if group:
                print(f"\n  [{label}]")
                for m in group:
                    print(f"    {m.enterprise_name}: {m.policy_title[:45]}")
                    print(f"      Score: {m.score_total}/20 "
                          f"(T{m.score_tech} P{m.score_prod} M{m.score_mkt} C{m.score_cap}) "
                          f"| {m.urgency}")

        print(f"\n{'=' * 60}\n")

    def _save_digest(self, matches: list, scan_stats: dict = None):
        """保存每日摘要到文件"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        filepath = self.alerts_dir / f"agent_{date_str}.md"

        lines = [
            f"# Agent 匹配日报 - {date_str}",
            f"",
            f"> 自动生成时间: {now_str}",
        ]

        if scan_stats:
            lines.extend([
                f"> 扫描: {scan_stats.get('policies_scanned', 0)} 条 | "
                f"新增: {scan_stats.get('policies_new', 0)} 条 | "
                f"匹配: {len(matches)} 条",
            ])

        lines.extend([
            f"",
            f"---",
            f"",
        ])

        # 按推荐等级分组
        for level, label in [(5, "5/5 首选推荐"), (4, "4/5 强烈推荐"), (3, "3/5 推荐")]:
            group = [m for m in matches if m.recommendation_score == level]
            if group:
                lines.append(f"## {label} ({len(group)} 条)")
                lines.append("")
                lines.append("| 企业 | 政策 | 评分 | 优先级 |")
                lines.append("|:------|:------|:--:|:--:|")
                for m in group:
                    lines.append(
                        f"| {m.enterprise_name} | {m.policy_title[:40]} | "
                        f"{m.score_total}/20 | {m.urgency} |"
                    )
                lines.append("")

        # 详细列表
        lines.extend([
            "---",
            "",
            "## 匹配详情",
            "",
        ])

        for i, m in enumerate(matches, 1):
            lines.extend([
                f"### {i}. {m.enterprise_name} x {m.policy_title[:40]}",
                "",
                f"- 推荐等级: {m.recommendation}",
                f"- 评分: {m.score_total}/20 (T{m.score_tech} P{m.score_prod} M{m.score_mkt} C{m.score_cap})",
                f"- 优先级: {m.urgency}",
                f"- 来源: {m.policy_source} | {m.policy_date}",
                f"- 硬性条件: {'全部通过' if m.hard_conditions_pass else '部分未通过'}",
                f"- 关键词: {', '.join(m.matched_keywords[:5])}",
                f"- 原文: [{m.policy_url[:50]}...]({m.policy_url})",
                "",
            ])

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"摘要已保存: {filepath}")
