# -*- coding: utf-8 -*-
"""
政策扫描器

包装 policy_monitor 模块，提供 Agent 级别的扫描接口:
  - 扫描并返回 P0/P1 新增政策
  - 查询未分析的高优先级政策
  - 记录扫描历史
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# 确保能找到 policy_monitor 模块
AGENT_DIR = Path(__file__).parent
BASE_DIR = AGENT_DIR.parent
PM_DIR = BASE_DIR / "policy_monitor"

if str(PM_DIR) not in sys.path:
    sys.path.insert(0, str(PM_DIR))

logger = logging.getLogger("agent.scanner")


class PolicyScanner:
    """政策扫描器 - 包装 policy_monitor"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else BASE_DIR
        self.pm_dir = self.base_dir / "policy_monitor"

        # 延迟导入以避免循环依赖
        self._config = None
        self._db = None

    def _load_config(self) -> dict:
        """加载 policy_monitor 的配置"""
        if self._config is None:
            import yaml
            config_path = self.pm_dir / "config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        return self._config

    def _get_db(self):
        """获取数据库连接"""
        if self._db is None:
            from database import PolicyDatabase
            data_dir = self.base_dir / "policy_data"
            db_path = data_dir / "policies.db"
            self._db = PolicyDatabase(str(db_path), str(data_dir))
        return self._db

    def scan(self, regions: list = None, industries: list = None) -> list:
        """运行一次政策扫描，返回 P0/P1 新增政策

        Args:
            regions: 要扫描的地区列表 (如 ["湖北", "恩施"])
            industries: 要扫描的产业分类 (如 ["strategic_emerging"])

        Returns:
            list of P0/P1 policies (dict)
        """
        from main import run_fetch, load_config

        config = load_config()
        new_policies = []

        logger.info("开始政策扫描...")

        # 按地区扫描
        target_regions = regions or []
        if not target_regions:
            # 默认只扫国家级
            try:
                policies = run_fetch(config)
                new_policies.extend(policies)
            except Exception as e:
                logger.error(f"国家级扫描失败: {e}")
        else:
            for region in target_regions:
                try:
                    policies = run_fetch(config, region=region)
                    new_policies.extend(policies)
                except Exception as e:
                    logger.error(f"地区 {region} 扫描失败: {e}")

        # 过滤 P0/P1
        p0_p1 = [p for p in new_policies if p.get("priority") in ("P0", "P1")]

        logger.info(f"扫描完成: 总计 {len(new_policies)} 条相关, P0/P1: {len(p0_p1)} 条")
        return p0_p1

    def get_unanalyzed(self, min_priority: str = "P1") -> list:
        """获取数据库中未分析的高优先级政策"""
        db = self._get_db()
        rows = db.conn.execute(
            """SELECT * FROM policies
               WHERE analyzed = 0 AND priority IN ('P0', 'P1')
               ORDER BY score DESC, date DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_policies(self, min_priority: str = "P2") -> list:
        """获取所有政策（含已分析的）"""
        db = self._get_db()
        if min_priority == "P0":
            rows = db.conn.execute(
                "SELECT * FROM policies WHERE priority = 'P0' ORDER BY score DESC"
            ).fetchall()
        elif min_priority == "P1":
            rows = db.conn.execute(
                "SELECT * FROM policies WHERE priority IN ('P0', 'P1') ORDER BY score DESC"
            ).fetchall()
        else:
            rows = db.conn.execute(
                "SELECT * FROM policies ORDER BY score DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_analyzed(self, url_hash_val: str):
        """标记政策为已分析"""
        db = self._get_db()
        db.mark_analyzed(url_hash_val)

    def get_stats(self) -> dict:
        """获取数据库统计"""
        db = self._get_db()
        return db.stats()

    def close(self):
        if self._db:
            self._db.close()
            self._db = None
