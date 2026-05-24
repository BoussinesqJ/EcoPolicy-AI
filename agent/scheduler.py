# -*- coding: utf-8 -*-
"""
定时调度模块

支持两种调度方式:
  1. Python 内置 schedule 库（轻量级，适合个人电脑）
  2. 输出 Windows Task Scheduler / cron 命令（系统级，适合服务器）

用法:
  python -m agent.scheduler start           启动调度器（前台运行）
  python -m agent.scheduler status          查看调度状态
  python -m agent.scheduler setup-windows   生成 Windows 计划任务命令
  python -m agent.scheduler setup-cron      生成 Linux cron 命令
"""

import sys
import os
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("agent.scheduler")


def _get_agent():
    """延迟导入 Agent，避免循环依赖"""
    agent_dir = Path(__file__).parent
    base_dir = agent_dir.parent
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    from agent import PolicyAgent
    return PolicyAgent()


def run_scheduled_job(mode: str = "full", region: str = None, industry: str = None):
    """执行一次定时任务"""
    logger.info(f"[Scheduler] 开始执行定时任务: mode={mode}")
    try:
        agent = _get_agent()
        agent.run(mode=mode, region=region, industry=industry)
        logger.info(f"[Scheduler] 定时任务完成: mode={mode}")
    except Exception as e:
        logger.error(f"[Scheduler] 定时任务失败: {e}")


def start_scheduler(mode: str = "full", interval_hours: int = 6,
                    region: str = None, industry: str = None):
    """启动调度器（前台运行）

    Args:
        mode: 运行模式 (full/scan/match/digest)
        interval_hours: 运行间隔（小时）
        region: 地区
        industry: 产业分类
    """
    try:
        import schedule
    except ImportError:
        print("  schedule library required: pip install schedule")
        print("  Or use system-level scheduling (Windows Task Scheduler / cron)")
        return

    print(f"\n{'=' * 50}")
    print(f"  EcoPolicy Agent - Scheduler")
    print(f"{'=' * 50}")
    print(f"  Mode: {mode}")
    print(f"  Interval: every {interval_hours} hours")
    if region:
        print(f"  Region: {region}")
    if industry:
        print(f"  Industry: {industry}")
    print(f"  First run: immediately")
    print(f"  Stop: Ctrl+C")
    print(f"{'=' * 50}\n")

    # 立即运行一次
    run_scheduled_job(mode, region, industry)

    # 定时循环
    schedule.every(interval_hours).hours.do(
        run_scheduled_job, mode=mode, region=region, industry=industry
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        print("\n\n  Scheduler stopped\n")


def generate_windows_task_command(mode: str = "full", interval_hours: int = 6,
                                   region: str = None):
    """生成 Windows 计划任务命令"""
    base_dir = Path(__file__).parent.parent
    python_path = sys.executable
    script_path = str(base_dir / "agent" / "agent.py")

    cmd = f'python -m agent.agent {mode}'
    if region:
        cmd += f' --region {region}'

    # 计算重复间隔（秒）
    interval_seconds = interval_hours * 3600

    task_name = "EcoPolicy-Agent-PolicyScan"

    print(f"\n{'=' * 60}")
    print(f"  Windows Task Scheduler Configuration")
    print(f"{'=' * 60}")
    print(f"")
    print(f"  Method 1: Using schtasks command (run CMD as administrator)")
    print(f"")
    print(f"  schtasks /create /tn \"{task_name}\" /tr")
    print(f"    \"{python_path} -m agent.agent {mode}\"")
    print(f"    /sc daily /st 09:00 /ri {interval_hours * 60} /du 24:00")
    print(f"    /f")
    print(f"")
    print(f"  Method 2: Using PowerShell")
    print(f"")
    print(f"  $action = New-ScheduledTaskAction")
    print(f"    -Execute \"{python_path}\"")
    print(f"    -Argument \"-m agent.agent {mode}\"")
    print(f"    -WorkingDirectory \"{base_dir}\"")
    print(f"")
    print(f"  $trigger = New-ScheduledTaskTrigger")
    print(f"    -Daily -At 9:00AM")
    print(f"    -RepetitionInterval (New-TimeSpan -Hours {interval_hours})")
    print(f"    -RepetitionDuration (New-TimeSpan -Hours 24)")
    print(f"")
    print(f"  Register-ScheduledTask")
    print(f"    -TaskName \"{task_name}\"")
    print(f"    -Action $action")
    print(f"    -Trigger $trigger")
    print(f"    -Description \"EcoPolicy Agent policy scanning\"")
    print(f"")
    print(f"  Delete task: schtasks /delete /tn \"{task_name}\" /f")
    print(f"{'=' * 60}\n")


def generate_cron_command(mode: str = "full", interval_hours: int = 6,
                           region: str = None):
    """生成 Linux/macOS cron 命令"""
    base_dir = Path(__file__).parent.parent
    python_path = sys.executable

    cmd = f'cd {base_dir} && {python_path} -m agent.agent {mode}'
    if region:
        cmd += f' --region {region}'

    # cron 表达式
    if interval_hours == 1:
        cron_expr = "0 * * * *"
    elif interval_hours == 6:
        cron_expr = "0 */6 * * *"
    elif interval_hours == 12:
        cron_expr = "0 */12 * * *"
    elif interval_hours == 24:
        cron_expr = "0 9 * * *"
    else:
        cron_expr = f"0 */{interval_hours} * * *"

    print(f"\n{'=' * 60}")
    print(f"  Linux/macOS Cron Configuration")
    print(f"{'=' * 60}")
    print(f"")
    print(f"  1. Open crontab editor:")
    print(f"     crontab -e")
    print(f"")
    print(f"  2. Add the following line:")
    print(f"     {cron_expr} {cmd} >> /var/log/ecopolicy.log 2>&1")
    print(f"")
    print(f"  3. Save and exit")
    print(f"")
    print(f"  List tasks: crontab -l")
    print(f"  Delete task: crontab -e (remove the corresponding line)")
    print(f"{'=' * 60}\n")


def show_status():
    """显示调度状态"""
    import json
    agent_dir = Path(__file__).parent
    state_path = agent_dir / "state.json"

    print(f"\n{'=' * 50}")
    print(f"  EcoPolicy Agent - Scheduler Status")
    print(f"{'=' * 50}")

    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        last_scan = state.get("last_scan_time", "Never run")
        total_scans = state.get("total_scans", 0)
        pending = len(state.get("pending_briefs", []))
        completed = len(state.get("completed_analyses", []))

        print(f"  Last scan: {last_scan}")
        print(f"  Total scans: {total_scans}")
        print(f"  Pending briefs: {pending}")
        print(f"  Completed analyses: {completed}")
    else:
        print(f"  State file not found, Agent has never run")

    # 检查是否有 schedule 库
    try:
        import schedule
        print(f"  schedule library: installed")
    except ImportError:
        print(f"  schedule library: not installed (pip install schedule)")

    print(f"{'=' * 50}\n")


def main():
    parser = argparse.ArgumentParser(
        description="EcoPolicy Agent - Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.scheduler start                    Start scheduler (default every 6 hours)
  python -m agent.scheduler start --interval 12      Every 12 hours
  python -m agent.scheduler start --region Hubei     Specify region
  python -m agent.scheduler status                   View scheduler status
  python -m agent.scheduler setup-windows            Generate Windows scheduled task
  python -m agent.scheduler setup-cron               Generate cron command
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # start
    start_parser = subparsers.add_parser("start", help="Start scheduler")
    start_parser.add_argument("--mode", default="full", choices=["full", "scan", "match", "digest"])
    start_parser.add_argument("--interval", type=int, default=6, help="Run interval in hours")
    start_parser.add_argument("--region", type=str, default=None)
    start_parser.add_argument("--industry", type=str, default=None)

    # status
    subparsers.add_parser("status", help="View scheduler status")

    # setup-windows
    win_parser = subparsers.add_parser("setup-windows", help="Generate Windows scheduled task commands")
    win_parser.add_argument("--mode", default="full")
    win_parser.add_argument("--interval", type=int, default=6)
    win_parser.add_argument("--region", type=str, default=None)

    # setup-cron
    cron_parser = subparsers.add_parser("setup-cron", help="Generate cron command")
    cron_parser.add_argument("--mode", default="full")
    cron_parser.add_argument("--interval", type=int, default=6)
    cron_parser.add_argument("--region", type=str, default=None)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "start":
        start_scheduler(
            mode=args.mode,
            interval_hours=args.interval,
            region=args.region,
            industry=args.industry,
        )
    elif args.command == "status":
        show_status()
    elif args.command == "setup-windows":
        generate_windows_task_command(
            mode=args.mode,
            interval_hours=args.interval,
            region=args.region,
        )
    elif args.command == "setup-cron":
        generate_cron_command(
            mode=args.mode,
            interval_hours=args.interval,
            region=args.region,
        )


if __name__ == "__main__":
    main()
