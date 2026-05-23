# -*- coding: utf-8 -*-
"""
EcoPolicy Agent - 主编排器

协调扫描器、匹配器、报告生成器、通知器完成端到端流程。

用法:
  python -m agent.agent run                    完整流程（扫描+匹配+简报+通知）
  python -m agent.agent scan                   仅扫描
  python -m agent.agent match                  仅匹配（使用已有政策数据）
  python -m agent.agent deep <policy_hash>     生成深度分析请求
  python -m agent.agent status                 查看系统状态
  python -m agent.agent enterprises            列出已注册企业
  python -m agent.agent interactive            交互模式
"""

import sys
import os
import logging
import argparse
from datetime import datetime
from pathlib import Path

import yaml

# 确保能找到同目录和 policy_monitor 模块
AGENT_DIR = Path(__file__).parent
BASE_DIR = AGENT_DIR.parent
PM_DIR = BASE_DIR / "policy_monitor"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(PM_DIR) not in sys.path:
    sys.path.insert(0, str(PM_DIR))

from scanner import PolicyScanner
from enterprise_matcher import EnterpriseMatcher
from report_generator import ReportGenerator
from agent_notifier import AgentNotifier
from state import AgentState

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agent")


def load_agent_config() -> dict:
    config_path = AGENT_DIR / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class PolicyAgent:
    """EcoPolicy Agent 主编排器"""

    def __init__(self):
        self.config = load_agent_config()
        self.scanner = PolicyScanner(str(BASE_DIR))
        self.matcher = EnterpriseMatcher(str(BASE_DIR / "enterprises"))
        self.reporter = ReportGenerator(str(BASE_DIR))
        self.notifier = AgentNotifier(str(BASE_DIR))
        self.state = AgentState(str(BASE_DIR / "agent"))

    def run(self, mode: str = "full", region: str = None, industry: str = None):
        """运行 Agent

        Args:
            mode: full | scan | match | digest
            region: 扫描地区
            industry: 产业分类
        """
        run_id = None
        try:
            from database import PolicyDatabase
            data_dir = BASE_DIR / "policy_data"
            db = PolicyDatabase(str(data_dir / "policies.db"), str(data_dir))
            run_id = db.record_agent_run(mode)
            db.close()
        except Exception:
            pass

        try:
            if mode == "full":
                result = self._run_full(region, industry)
            elif mode == "scan":
                result = self._run_scan(region, industry)
            elif mode == "match":
                result = self._run_match()
            elif mode == "digest":
                result = self._run_digest()
            else:
                logger.error(f"未知模式: {mode}")
                return

            # 记录运行完成
            if run_id:
                try:
                    from database import PolicyDatabase
                    data_dir = BASE_DIR / "policy_data"
                    db = PolicyDatabase(str(data_dir / "policies.db"), str(data_dir))
                    db.finish_agent_run(
                        run_id, status="completed",
                        policies_scanned=result.get("scanned", 0),
                        policies_new=result.get("new", 0),
                        matches_found=result.get("matches", 0),
                        briefs_generated=result.get("briefs", 0),
                    )
                    db.close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Agent 运行失败: {e}")
            if run_id:
                try:
                    from database import PolicyDatabase
                    data_dir = BASE_DIR / "policy_data"
                    db = PolicyDatabase(str(data_dir / "policies.db"), str(data_dir))
                    db.finish_agent_run(run_id, status="error", error_message=str(e))
                    db.close()
                except Exception:
                    pass
            raise

    def _run_full(self, region=None, industry=None) -> dict:
        """完整流程: 扫描 → 匹配 → 简报 → 通知"""
        scan_cfg = self.config.get("scan", {})
        regions = [region] if region else scan_cfg.get("regions", [])

        # Step 1: 扫描
        logger.info("=" * 50)
        logger.info("Step 1/4: 政策扫描")
        new_policies = self.scanner.scan(regions=regions)
        logger.info(f"扫描完成: {len(new_policies)} 条 P0/P1 政策")

        # 如果扫描没返回结果，也获取数据库中未分析的
        if not new_policies:
            logger.info("获取数据库中未分析的政策...")
            new_policies = self.scanner.get_unanalyzed()
            logger.info(f"未分析政策: {len(new_policies)} 条")

        # Step 2: 匹配
        logger.info("Step 2/4: 企业匹配")
        all_policies = self.scanner.get_all_policies("P1")
        if not all_policies:
            all_policies = new_policies

        matches = self.matcher.match_policies(all_policies)
        logger.info(f"匹配完成: {len(matches)} 条有效结果")

        # Step 3: 生成简报
        logger.info("Step 3/4: 生成简报")
        brief_count = 0
        if self.config.get("matching", {}).get("auto_brief", True):
            for match in matches:
                if match.recommendation_score >= self.config.get("matching", {}).get("min_recommendation_score", 3):
                    brief_path = self.reporter.generate_brief(match)
                    self.state.record_brief(
                        brief_path, match.enterprise_id,
                        match.policy_title, match.recommendation_score,
                    )
                    # 标记为已分析
                    if match.policy_url_hash:
                        self.scanner.mark_analyzed(match.policy_url_hash)
                    brief_count += 1

        # Step 4: 通知
        logger.info("Step 4/4: 发送通知")
        scan_stats = {
            "policies_scanned": len(all_policies),
            "policies_new": len(new_policies),
        }
        self.notifier.send_digest(matches, scan_stats)
        self.state.record_scan(len(all_policies), len(new_policies))

        return {
            "scanned": len(all_policies),
            "new": len(new_policies),
            "matches": len(matches),
            "briefs": brief_count,
        }

    def _run_scan(self, region=None, industry=None) -> dict:
        """仅扫描"""
        scan_cfg = self.config.get("scan", {})
        regions = [region] if region else scan_cfg.get("regions", [])

        new_policies = self.scanner.scan(regions=regions)
        self.state.record_scan(0, len(new_policies))
        print(f"\n扫描完成: {len(new_policies)} 条 P0/P1 政策\n")
        return {"scanned": 0, "new": len(new_policies), "matches": 0, "briefs": 0}

    def _run_match(self) -> dict:
        """仅匹配（使用已有政策数据）"""
        all_policies = self.scanner.get_all_policies("P1")
        if not all_policies:
            print("\n数据库中无 P0/P1 政策。请先运行 scan。\n")
            return {"scanned": 0, "new": 0, "matches": 0, "briefs": 0}

        matches = self.matcher.match_policies(all_policies)

        # 生成简报
        brief_count = 0
        for match in matches:
            if match.recommendation_score >= 3:
                brief_path = self.reporter.generate_brief(match)
                self.state.record_brief(
                    brief_path, match.enterprise_id,
                    match.policy_title, match.recommendation_score,
                )
                brief_count += 1

        self.notifier.send_digest(matches)
        return {"scanned": len(all_policies), "new": 0, "matches": len(matches), "briefs": brief_count}

    def _run_digest(self) -> dict:
        """仅生成通知摘要"""
        all_policies = self.scanner.get_all_policies("P1")
        matches = self.matcher.match_policies(all_policies)
        self.notifier.send_digest(matches)
        return {"scanned": len(all_policies), "new": 0, "matches": len(matches), "briefs": 0}

    def show_status(self):
        """显示系统状态"""
        self.state.print_status()

        # 显示数据库统计
        try:
            stats = self.scanner.get_stats()
            print(f"  政策数据库: {stats['total']} 条 (P0:{stats['P0']} P1:{stats['P1']} P2:{stats['P2']})")
            for source, count in stats.get("by_source", {}).items():
                print(f"    {source}: {count} 条")
        except Exception:
            print("  政策数据库: 无数据")

        # 显示已注册企业
        ent_ids = self.matcher.get_enterprise_ids()
        print(f"\n  已注册企业: {len(ent_ids)} 家")
        for eid in ent_ids:
            ent = self.matcher.enterprises[eid]
            name = ent["profile"].get("basic_info", {}).get("short_name", eid)
            sector = ent["profile"].get("industry", {}).get("primary_sector", "")
            print(f"    {eid}: {name} ({sector})")

    def list_enterprises(self):
        """列出已注册企业"""
        ent_ids = self.matcher.get_enterprise_ids()
        if not ent_ids:
            print("\n  暂无已注册企业。")
            print(f"  请在 enterprises/ 目录下创建子目录并放置 profile.yaml\n")
            return

        print(f"\n{'=' * 50}")
        print(f"  已注册企业（共 {len(ent_ids)} 家）")
        print(f"{'=' * 50}")
        for eid in ent_ids:
            ent = self.matcher.enterprises[eid]
            profile = ent["profile"]
            name = profile.get("basic_info", {}).get("short_name", eid)
            sector = profile.get("industry", {}).get("primary_sector", "")
            capital = profile.get("basic_info", {}).get("registered_capital", "")
            listed = profile.get("qualifications", {}).get("listed", False)
            listing = profile.get("qualifications", {}).get("listing_board", "")

            status = f" | 已挂牌 {listing}" if listed and listing else ""
            print(f"  {eid}: {name}")
            print(f"    行业: {sector} | 注册资本: {capital}万{status}")
        print(f"{'=' * 50}\n")

    def generate_deep_analysis(self, policy_url_hash: str):
        """为指定政策生成深度分析请求"""
        # 从数据库查找政策
        all_policies = self.scanner.get_all_policies("P2")
        target = None
        for p in all_policies:
            from database import url_hash
            if url_hash(p.get("url", "")) == policy_url_hash:
                target = p
                break

        if not target:
            print(f"\n未找到 hash 为 {policy_url_hash} 的政策\n")
            return

        # 与所有企业匹配
        matches = self.matcher.match_policies([target])
        if not matches:
            print(f"\n该政策与已注册企业均无有效匹配\n")
            return

        # 为最高分的企业生成
        best = matches[0]
        path = self.reporter.generate_deep_analysis_request(best)
        print(f"\n深度分析请求已生成: {path}")
        print(f"请将该文件发送给 AI 助手执行六步分析工作流\n")

    def interactive(self):
        """交互模式"""
        print(f"\n{'=' * 50}")
        print(f"  EcoPolicy Agent - 交互模式")
        print(f"{'=' * 50}")
        print(f"  命令:")
        print(f"    scan              - 扫描政策")
        print(f"    match             - 匹配已有政策")
        print(f"    full              - 完整流程")
        print(f"    list              - 列出企业")
        print(f"    briefs            - 列出待处理简报")
        print(f"    deep <hash>       - 生成深度分析请求")
        print(f"    status            - 系统状态")
        print(f"    quit              - 退出")
        print(f"{'=' * 50}\n")

        while True:
            try:
                cmd = input("agent> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见!")
                break

            if not cmd:
                continue
            elif cmd == "quit" or cmd == "exit":
                print("再见!")
                break
            elif cmd == "scan":
                self._run_scan()
            elif cmd == "match":
                self._run_match()
            elif cmd == "full":
                self._run_full()
            elif cmd == "list":
                self.list_enterprises()
            elif cmd == "briefs":
                pending = self.state.list_pending()
                if pending:
                    print(f"\n  待处理简报 ({len(pending)} 份):")
                    for b in pending:
                        print(f"    {b['enterprise_id']}: {b['policy_title'][:40]} "
                              f"({b['recommendation_score']}/5)")
                else:
                    print("\n  暂无待处理简报\n")
            elif cmd.startswith("deep "):
                hash_val = cmd.split(" ", 1)[1].strip()
                self.generate_deep_analysis(hash_val)
            elif cmd == "status":
                self.show_status()
            else:
                print(f"  未知命令: {cmd}")


def main():
    parser = argparse.ArgumentParser(
        description="EcoPolicy Agent - 经济政策智能分析 Agent 系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m agent.agent run                        完整流程
  python -m agent.agent run --region 湖北           指定地区
  python -m agent.agent scan                       仅扫描
  python -m agent.agent match                      仅匹配
  python -m agent.agent deep <hash>                深度分析请求
  python -m agent.agent status                     系统状态
  python -m agent.agent enterprises                列出企业
  python -m agent.agent interactive                交互模式
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # run
    run_parser = subparsers.add_parser("run", help="完整流程")
    run_parser.add_argument("--region", "-r", type=str, default=None, help="指定地区")
    run_parser.add_argument("--industry", "-i", type=str, default=None, help="指定产业")

    # scan
    scan_parser = subparsers.add_parser("scan", help="仅扫描")
    scan_parser.add_argument("--region", "-r", type=str, default=None)

    # match
    subparsers.add_parser("match", help="仅匹配")

    # digest
    subparsers.add_parser("digest", help="仅通知")

    # deep
    deep_parser = subparsers.add_parser("deep", help="深度分析请求")
    deep_parser.add_argument("hash", type=str, help="政策 URL hash")

    # status
    subparsers.add_parser("status", help="系统状态")

    # enterprises
    subparsers.add_parser("enterprises", help="列出已注册企业")

    # interactive
    subparsers.add_parser("interactive", help="交互模式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    agent = PolicyAgent()

    if args.command == "run":
        agent.run("full", region=args.region, industry=args.industry)
    elif args.command == "scan":
        agent.run("scan", region=args.region)
    elif args.command == "match":
        agent.run("match")
    elif args.command == "digest":
        agent.run("digest")
    elif args.command == "deep":
        agent.generate_deep_analysis(args.hash)
    elif args.command == "status":
        agent.show_status()
    elif args.command == "enterprises":
        agent.list_enterprises()
    elif args.command == "interactive":
        agent.interactive()
    else:
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
