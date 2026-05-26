# -*- coding: utf-8 -*-
"""
EcoPolicy AI — 定时调度器

使用 schedule 库实现定时任务，支持：
- 每日定时抓取 + 匹配
- 每周定时抓取 + 匹配
- 手动触发

用法：
  # 启动调度器（前台运行）
  python scheduler.py run

  # 启动调度器（后台运行）
  python scheduler.py run --daemon

  # 查看调度状态
  python scheduler.py status

  # 手动触发一次
  python scheduler.py trigger
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 确保能找到同目录下的模块
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import yaml

# 使用统一日志配置
from log_config import setup_logging, get_logger, LOGGER_SCHEDULER
from exceptions import SchedulerError

setup_logging(level="INFO")
logger = get_logger("scheduler")


def load_config() -> dict:
    """加载调度器配置"""
    config_path = BASE_DIR / "policy_monitor" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("scheduler", {})


def run_scan(enterprise_id: str, region: str = None, industry: str = None, 
             auto_report: bool = True):
    """执行一次抓取 + 匹配"""
    logger.info(f"开始定时任务: enterprise={enterprise_id}, region={region}, industry={industry}")

    # Step 1: 运行网络抓取爬虫与基础匹配
    cmd = [
        sys.executable,
        str(BASE_DIR / "policy_matcher_cli.py"),
        "scan",
        "--enterprise", enterprise_id,
    ]

    if region:
        cmd.extend(["--region", region])
    if industry:
        cmd.extend(["--industry", industry])
    if auto_report:
        cmd.append("--report")

    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=False)
        if result.returncode == 0:
            logger.info("爬虫抓取与基础匹配完成")
        else:
            logger.warning(f"爬虫抓取可能有错误（返回码: {result.returncode}）")
    except Exception as e:
        logger.error(f"爬虫抓取与基础匹配失败: {e}")
        return

    # Step 2: 如果开启了自动报告，调用 AI Agent 自动驾驶分析流对今天抓取到的新政策生成深度报告
    if auto_report:
        logger.info("已开启自动报告，开始启动 AI Agent 进行自动驾驶深度分析报告生成...")
        agent_cmd = [
            sys.executable,
            str(BASE_DIR / "policy_matcher_cli.py"),
            "agent-scan",
            "--enterprise", enterprise_id,
            "--days", "1"  # 仅扫描分析今天新抓取的政策
        ]
        try:
            result = subprocess.run(agent_cmd, cwd=str(BASE_DIR), capture_output=False)
            if result.returncode == 0:
                logger.info("AI Agent 自动分析完成")
            else:
                logger.warning(f"AI Agent 自动分析运行异常（返回码: {result.returncode}）")
        except Exception as e:
            logger.error(f"AI Agent 自动分析启动失败: {e}")


def setup_schedule(config: dict):
    """设置定时任务"""
    try:
        import schedule
    except ImportError:
        logger.error("需要安装 schedule 库: pip install schedule")
        sys.exit(1)

    enterprise_id = config.get("enterprise_id")
    if not enterprise_id:
        logger.error("未配置 enterprise_id，请在 config.yaml 中设置 scheduler.enterprise_id")
        sys.exit(1)

    region = config.get("region")
    industry = config.get("industry")
    auto_report = config.get("auto_report", True)
    schedule_type = config.get("schedule_type", "daily_8am")

    # 设置调度
    if schedule_type == "daily_8am":
        schedule.every().day.at("08:00").do(
            run_scan, enterprise_id=enterprise_id, region=region,
            industry=industry, auto_report=auto_report
        )
        logger.info("调度设置: 每天 08:00 执行")
    elif schedule_type == "weekly_monday":
        schedule.every().monday.at("08:00").do(
            run_scan, enterprise_id=enterprise_id, region=region,
            industry=industry, auto_report=auto_report
        )
        logger.info("调度设置: 每周一 08:00 执行")
    elif schedule_type == "daily_18pm":
        schedule.every().day.at("18:00").do(
            run_scan, enterprise_id=enterprise_id, region=region,
            industry=industry, auto_report=auto_report
        )
        logger.info("调度设置: 每天 18:00 执行")
    else:
        logger.warning(f"未知调度类型: {schedule_type}，使用默认 daily_8am")
        schedule.every().day.at("08:00").do(
            run_scan, enterprise_id=enterprise_id, region=region,
            industry=industry, auto_report=auto_report
        )

    return schedule


def cmd_run(args):
    """启动调度器"""
    config = load_config()

    if not config.get("enabled", False):
        logger.error("调度器未启用，请在 config.yaml 中设置 scheduler.enabled: true")
        sys.exit(1)

    schedule = setup_schedule(config)

    logger.info("调度器已启动，按 Ctrl+C 停止")
    logger.info(f"企业: {config.get('enterprise_id')}")
    logger.info(f"地区: {config.get('region', '全国')}")
    logger.info(f"产业: {config.get('industry', '全部')}")

    if args.daemon:
        logger.info("后台模式运行...")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("调度器已停止")


def cmd_status(args):
    """显示调度状态"""
    config = load_config()

    print(f"\n{'='*60}")
    print(f"  EcoPolicy AI 调度器状态")
    print(f"{'='*60}")
    enabled = config.get('enabled', False)
    print(f"  启用状态: {'[ON] 已启用' if enabled else '[OFF] 未启用'}")
    print(f"  企业 ID:  {config.get('enterprise_id', '未配置')}")
    print(f"  地区:     {config.get('region', '全国')}")
    print(f"  产业:     {config.get('industry', '全部')}")
    print(f"  调度类型: {config.get('schedule_type', 'daily_8am')}")
    auto_report = config.get('auto_report', True)
    print(f"  自动报告: {'是' if auto_report else '否'}")
    print(f"{'='*60}")

    if not enabled:
        print(f"\n  要启用调度器，请编辑 config.yaml:")
        print(f"  scheduler:")
        print(f"    enabled: true")
        print(f"    enterprise_id: \"your_enterprise_id\"")

    print(f"\n  启动调度器: python scheduler.py run")
    print(f"  手动触发:   python scheduler.py trigger")
    print()


def cmd_trigger(args):
    """手动触发一次"""
    config = load_config()

    enterprise_id = config.get("enterprise_id")
    if not enterprise_id:
        logger.error("未配置 enterprise_id")
        sys.exit(1)

    region = config.get("region")
    industry = config.get("industry")
    auto_report = config.get("auto_report", True)

    run_scan(enterprise_id, region, industry, auto_report)


def main():
    parser = argparse.ArgumentParser(
        description="EcoPolicy AI 定时调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scheduler.py status          查看调度状态
  python scheduler.py run             启动调度器（前台）
  python scheduler.py run --daemon    启动调度器（后台）
  python scheduler.py trigger         手动触发一次

配置文件: policy_monitor/config.yaml (scheduler 部分)
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="启动调度器")
    run_parser.add_argument("--daemon", "-d", action="store_true", help="后台运行")

    # status 命令
    subparsers.add_parser("status", help="查看调度状态")

    # trigger 命令
    subparsers.add_parser("trigger", help="手动触发一次")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "trigger":
        cmd_trigger(args)
    else:
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
