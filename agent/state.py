# -*- coding: utf-8 -*-
"""
Agent 运行状态管理

使用 JSON 文件持久化 Agent 的运行状态:
  - 最后扫描时间
  - 待处理简报
  - 已完成分析
  - 企业分析历史
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("agent.state")


class AgentState:
    """Agent 运行状态管理器"""

    def __init__(self, state_dir: str):
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "state.json"
        self._state = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"状态文件损坏，重新初始化: {e}")

        return {
            "last_scan_time": None,
            "total_scans": 0,
            "pending_briefs": [],
            "completed_analyses": [],
            "enterprise_stats": {},
        }

    def _save(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def record_scan(self, policies_scanned: int, policies_new: int):
        """记录一次扫描"""
        self._state["last_scan_time"] = datetime.now().isoformat()
        self._state["total_scans"] += 1
        self._save()
        logger.info(f"扫描记录已保存: {policies_scanned}条已扫描, {policies_new}条新增")

    def record_brief(self, brief_path: str, enterprise_id: str,
                     policy_title: str, recommendation_score: int):
        """记录一个生成的简报"""
        brief = {
            "path": brief_path,
            "enterprise_id": enterprise_id,
            "policy_title": policy_title,
            "recommendation_score": recommendation_score,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        }
        self._state["pending_briefs"].append(brief)

        # 更新企业统计
        if enterprise_id not in self._state["enterprise_stats"]:
            self._state["enterprise_stats"][enterprise_id] = {
                "total_briefs": 0,
                "completed_analyses": 0,
            }
        self._state["enterprise_stats"][enterprise_id]["total_briefs"] += 1
        self._save()

    def complete_analysis(self, brief_path: str, report_path: str):
        """标记简报的分析已完成"""
        for brief in self._state["pending_briefs"]:
            if brief["path"] == brief_path:
                brief["status"] = "completed"
                self._state["completed_analyses"].append({
                    "brief_path": brief_path,
                    "report_path": report_path,
                    "enterprise_id": brief["enterprise_id"],
                    "policy_title": brief["policy_title"],
                    "completed_at": datetime.now().isoformat(),
                })
                # 更新企业统计
                eid = brief["enterprise_id"]
                if eid in self._state["enterprise_stats"]:
                    self._state["enterprise_stats"][eid]["completed_analyses"] += 1
                break

        self._state["pending_briefs"] = [
            b for b in self._state["pending_briefs"] if b["path"] != brief_path
        ]
        self._save()

    def list_pending(self) -> list:
        """列出待处理简报"""
        return self._state["pending_briefs"]

    def list_completed(self) -> list:
        """列出已完成分析"""
        return self._state["completed_analyses"]

    def get_status(self) -> dict:
        """获取系统状态摘要"""
        return {
            "last_scan": self._state["last_scan_time"],
            "total_scans": self._state["total_scans"],
            "pending_briefs": len(self._state["pending_briefs"]),
            "completed_analyses": len(self._state["completed_analyses"]),
            "enterprise_stats": self._state["enterprise_stats"],
        }

    def print_status(self):
        """打印系统状态"""
        status = self.get_status()
        print(f"\n{'=' * 50}")
        print(f"  EcoPolicy Agent - System Status")
        print(f"{'=' * 50}")
        print(f"  Last scan: {status['last_scan'] or 'Never'}")
        print(f"  Total scans: {status['total_scans']}")
        print(f"  Pending briefs: {status['pending_briefs']}")
        print(f"  Completed analyses: {status['completed_analyses']}")
        if status["enterprise_stats"]:
            print(f"\n  Enterprise stats:")
            for eid, stats in status["enterprise_stats"].items():
                print(f"    {eid}: briefs {stats['total_briefs']} / analyzed {stats['completed_analyses']}")
        print(f"{'=' * 50}\n")
