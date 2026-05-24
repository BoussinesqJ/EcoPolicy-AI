# -*- coding: utf-8 -*-
"""
通知推送
- 生成每日 Markdown 通知文件
- 控制台摘要输出
- 按 P0/P1/P2 分级展示
"""

import logging
from pathlib import Path

from utils import today_str, now_iso, truncate

logger = logging.getLogger("policy_monitor")


class Notifier:
    """政策通知推送"""

    def __init__(self, alerts_dir: str):
        self.alerts_dir = Path(alerts_dir)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_alert(self, new_policies: list[dict]) -> str:
        """
        生成每日通知 Markdown 文件。
        返回文件路径。
        """
        if not new_policies:
            logger.info("今日无新增政策，不生成通知文件")
            return ""

        today = today_str()
        out_path = self.alerts_dir / f"{today}.md"

        # 按优先级分组
        p0 = [p for p in new_policies if p.get("priority") == "P0"]
        p1 = [p for p in new_policies if p.get("priority") == "P1"]
        p2 = [p for p in new_policies if p.get("priority") == "P2"]

        lines = []
        lines.append(f"# 政策监控日报 - {today}")
        lines.append("")
        lines.append(f"> 自动生成时间：{now_iso()}")
        lines.append(f"> 新增政策：**{len(new_policies)}** 条")
        lines.append(f"> P0 紧急：**{len(p0)}** 条 | P1 重要：**{len(p1)}** 条 | P2 观察：**{len(p2)}** 条")
        lines.append("")
        lines.append("---")
        lines.append("")

        # P0 紧急
        if p0:
            lines.append("## P0 紧急（建议立即处理）")
            lines.append("")
            for p in p0:
                lines.append(f"### {p['title']}")
                lines.append("")
                lines.append(f"- 来源：{p.get('source', '-')}")
                lines.append(f"- 日期：{p.get('date', '-')}")
                lines.append(f"- 相关度：{p.get('score', 0)} 分")
                kw = p.get("keywords_matched", [])
                if isinstance(kw, list):
                    kw_str = ", ".join(kw)
                else:
                    kw_str = str(kw)
                lines.append(f"- 命中关键词：{kw_str}")
                lines.append(f"- 链接：{p.get('url', '-')}")
                if p.get("summary"):
                    lines.append(f"- 摘要：{truncate(p['summary'], 200)}")
                lines.append("")

        # P1 重要
        if p1:
            lines.append("## P1 重要（建议本周关注）")
            lines.append("")
            for p in p1:
                lines.append(f"### {p['title']}")
                lines.append("")
                lines.append(f"- 来源：{p.get('source', '-')}")
                lines.append(f"- 日期：{p.get('date', '-')}")
                lines.append(f"- 相关度：{p.get('score', 0)} 分")
                kw = p.get("keywords_matched", [])
                if isinstance(kw, list):
                    kw_str = ", ".join(kw)
                else:
                    kw_str = str(kw)
                lines.append(f"- 命中关键词：{kw_str}")
                lines.append(f"- 链接：{p.get('url', '-')}")
                lines.append("")

        # P2 观察（仅列出标题）
        if p2:
            lines.append("## P2 观察（仅记录）")
            lines.append("")
            lines.append("| 标题 | 来源 | 日期 |")
            lines.append("|:-----|:-----|:-----|")
            for p in p2:
                title = truncate(p['title'], 50)
                lines.append(f"| {title} | {p.get('source', '-')} | {p.get('date', '-')} |")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*本通知由政策监控系统自动生成，建议对 P0 政策启动完整分析。*")

        content = "\n".join(lines)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"通知文件已生成: {out_path}")
        return str(out_path)

    def print_summary(self, new_policies: list[dict]):
        """控制台输出摘要"""
        if not new_policies:
            print("\n[Policy Monitor] No new policies today")
            return

        p0 = [p for p in new_policies if p.get("priority") == "P0"]
        p1 = [p for p in new_policies if p.get("priority") == "P1"]
        p2 = [p for p in new_policies if p.get("priority") == "P2"]

        print(f"\n{'='*60}")
        print(f"  Policy Monitor Summary - {today_str()}")
        print(f"{'='*60}")
        print(f"  New: {len(new_policies)}  |  P0: {len(p0)}  |  P1: {len(p1)}  |  P2: {len(p2)}")
        print(f"{'='*60}")

        if p0:
            print("\n  [P0 Critical]")
            for p in p0:
                print(f"    -> [{p.get('score', 0)}] {p['title'][:60]}")
                print(f"       {p.get('url', '')}")

        if p1:
            print("\n  [P1 Important]")
            for p in p1:
                print(f"    -> [{p.get('score', 0)}] {p['title'][:60]}")

        if p2:
            print(f"\n  [P2 Monitor] {len(p2)} (omitted)")

        print(f"\n{'='*60}\n")
