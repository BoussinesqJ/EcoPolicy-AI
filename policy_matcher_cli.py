# -*- coding: utf-8 -*-
"""
EcoPolicy AI — 政策匹配工具

用法：
  # Phase A: 匹配用户上传政策
  python policy_matcher_cli.py match --enterprise jyuh --url "https://..."
  python policy_matcher_cli.py match --enterprise jyuh --file policy.pdf
  python policy_matcher_cli.py match --enterprise jyuh --text "政策内容..."

  # Phase B: 手动触发抓取 + 匹配
  python policy_matcher_cli.py scan --enterprise jyuh
  python policy_matcher_cli.py scan --enterprise jyuh --region 湖北
  python policy_matcher_cli.py scan --enterprise jyuh --industry strategic_emerging

  # Phase C: 定时任务管理
  python policy_matcher_cli.py schedule --show
  python policy_matcher_cli.py schedule --install
  python policy_matcher_cli.py schedule --remove

  # 列出已配置企业
  python policy_matcher_cli.py list
"""

import sys
import os
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 确保能找到同目录下的模块
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "policy_monitor"))

from policy_monitor.parsers.user_upload import parse_url, parse_file, parse_text
from enterprise_matcher import EnterpriseMatcher
from report_generator import ReportGenerator
from log_config import setup_logging, get_logger, LOGGER_MATCHER
from exceptions import EcoPolicyError, MatchError, FetchError, ParseError

# 使用统一日志配置
setup_logging(level="INFO")
logger = get_logger("cli")


# ============================================================
# 通用函数
# ============================================================

def list_enterprises(matcher: EnterpriseMatcher):
    """列出所有已配置的企业"""
    ids = matcher.get_enterprise_ids()
    if not ids:
        print("未找到已配置的企业画像。")
        print(f"请在 {matcher.enterprises_dir} 目录下创建企业画像。")
        print(f"参考模板: {matcher.enterprises_dir / '_template' / 'profile.yaml'}")
        return

    print(f"\n已配置的企业 ({len(ids)} 家):")
    print("-" * 50)
    print(f"  {'ID':<15} {'名称':<12} {'行业':<12} {'地区'}")
    print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*8}")
    for eid in ids:
        ent = matcher.enterprises[eid]
        profile = ent["profile"]
        name = profile.get("basic_info", {}).get("short_name", eid)
        sector = profile.get("industry", {}).get("primary_sector", "未知")
        region = profile.get("regions", {}).get("headquarters", "未知")
        print(f"  {eid:<15} {name:<12} {sector:<12} {region}")
    print()


def match_single_policy(matcher: EnterpriseMatcher, enterprise_id: str, policy: dict):
    """执行单条政策匹配并返回结果"""
    if enterprise_id not in matcher.get_enterprise_ids():
        print(f"错误: 未找到企业 '{enterprise_id}'")
        print(f"可用企业: {', '.join(matcher.get_enterprise_ids())}")
        sys.exit(1)

    results = matcher.match_policies([policy], enterprise_id)

    if not results:
        print("\n匹配结果: 该政策与企业画像不匹配（评分 < 3/5）")
        return None

    return results[0]


def print_match_summary(result):
    """打印匹配结果摘要"""
    print("\n" + "=" * 60)
    print(f"政策: {result.policy_title}")
    print(f"企业: {result.enterprise_name}")
    print("=" * 60)

    print(f"\n推荐等级: {result.recommendation}")
    print(f"综合评分: {result.score_total}/20")
    print(f"加权得分: {result.weighted_score:.1f}/5.0")

    print(f"\n四维评分:")
    print(f"  Tech (技术端): {result.score_tech}/5")
    print(f"  Prod (生产端): {result.score_prod}/5")
    print(f"  Mkt  (市场端): {result.score_mkt}/5")
    print(f"  Cap  (资本端): {result.score_cap}/5")

    status = "通过" if result.hard_conditions_pass else "未通过"
    print(f"\n硬性条件: {status}")

    if result.success_probability > 0:
        print(f"成功概率: {result.success_probability:.0%}")

    if result.roi_ratio > 0:
        print(f"ROI 评估: {result.roi_ratio:.1f}x ({result.roi_verdict})")

    print(f"紧迫度: {result.urgency}")

    if result.matched_keywords:
        print(f"匹配关键词: {', '.join(result.matched_keywords[:8])}")

    if result.rejection_reasons:
        print(f"\n不推荐原因:")
        for reason in result.rejection_reasons:
            print(f"  - {reason}")

    print()


def print_batch_summary(results: list):
    """打印批量匹配结果摘要"""
    if not results:
        print("\n未找到匹配的政策（所有政策评分 < 3/5）")
        return

    print(f"\n{'='*70}")
    print(f"  批量匹配结果（共 {len(results)} 条匹配政策）")
    print(f"{'='*70}")
    print(f"  {'序号':<4} {'推荐':<8} {'评分':<6} {'紧迫度':<6} {'政策名称'}")
    print(f"  {'-'*4} {'-'*8} {'-'*6} {'-'*6} {'-'*40}")

    for i, r in enumerate(results[:20], 1):  # 最多显示 20 条
        title = r.policy_title[:40] + "..." if len(r.policy_title) > 40 else r.policy_title
        print(f"  {i:<4} {r.recommendation[:6]:<8} {r.score_total:<6} {r.urgency:<6} {title}")

    if len(results) > 20:
        print(f"  ... 还有 {len(results) - 20} 条结果")

    print(f"\n  使用 --report 生成详细报告")
    print(f"{'='*70}\n")


# ============================================================
# Phase A: 匹配用户上传政策
# ============================================================

def cmd_match(args):
    """匹配用户上传的政策"""
    enterprises_dir = BASE_DIR / "enterprises"
    matcher = EnterpriseMatcher(str(enterprises_dir))

    if not args.enterprise:
        print("错误: 请指定企业 ID（--enterprise）")
        print(f"可用企业: {', '.join(matcher.get_enterprise_ids())}")
        sys.exit(1)

    # 解析政策
    try:
        if args.url:
            policy = parse_url(args.url)
            print(f"已抓取政策: {policy['title']}")
        elif args.file:
            policy = parse_file(args.file)
            print(f"已解析文件: {policy['title']}")
        elif args.text:
            policy = parse_text(args.text)
            print(f"已接收文本: {policy['title']}")
        else:
            print("错误: 请指定政策输入方式（--url / --file / --text）")
            sys.exit(1)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)

    # 执行匹配
    result = match_single_policy(matcher, args.enterprise, policy)
    if not result:
        sys.exit(0)

    # 打印摘要
    print_match_summary(result)

    # 生成报告
    if args.report:
        reporter = ReportGenerator(str(BASE_DIR))
        brief_path = reporter.generate_brief(result)
        print(f"报告已生成: {brief_path}")

        deep_path = reporter.generate_deep_analysis_request(result, brief_path)
        print(f"深度分析请求: {deep_path}")
        print("\n将深度分析请求文件发送给 AI 助手，可获得完整的六步工作流分析。")


# ============================================================
# Phase B: 手动触发抓取 + 匹配
# ============================================================

def cmd_scan(args):
    """手动触发政策抓取 + 企业匹配"""
    enterprises_dir = BASE_DIR / "enterprises"
    matcher = EnterpriseMatcher(str(enterprises_dir))

    if not args.enterprise:
        print("错误: 请指定企业 ID（--enterprise）")
        print(f"可用企业: {', '.join(matcher.get_enterprise_ids())}")
        sys.exit(1)

    enterprise_id = args.enterprise
    if enterprise_id not in matcher.get_enterprise_ids():
        print(f"错误: 未找到企业 '{enterprise_id}'")
        print(f"可用企业: {', '.join(matcher.get_enterprise_ids())}")
        sys.exit(1)

    # 构建抓取命令
    main_py = BASE_DIR / "policy_monitor" / "main.py"
    cmd = [sys.executable, str(main_py), "run"]

    if args.region:
        cmd.extend(["--region", args.region])
    if args.industry:
        cmd.extend(["--industry", args.industry])

    print(f"\n{'='*60}")
    print(f"  Phase 1: 政策抓取")
    print(f"{'='*60}")
    print(f"  企业: {enterprise_id}")
    print(f"  地区: {args.region or '全国'}")
    print(f"  产业: {args.industry or '全部'}")
    print(f"  命令: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    # 执行抓取
    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=False)
        if result.returncode != 0:
            print(f"\n警告: 抓取过程可能有错误（返回码: {result.returncode}）")
    except Exception as e:
        print(f"\n错误: 抓取失败 - {e}")
        sys.exit(1)

    # Phase 2: 匹配
    print(f"\n{'='*60}")
    print(f"  Phase 2: 企业匹配")
    print(f"{'='*60}\n")

    # 从数据库读取最新政策并匹配
    from policy_monitor.database import PolicyDatabase

    config_path = BASE_DIR / "policy_monitor" / "config.yaml"
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    db_path = BASE_DIR / "policy_data" / "policies.db"
    data_dir = BASE_DIR / "policy_data"

    if not db_path.exists():
        print("错误: 数据库不存在，请先运行抓取")
        sys.exit(1)

    db = PolicyDatabase(str(db_path), str(data_dir))

    # 获取最近 7 天的政策
    policies = db.get_recent_policies(days=7)
    db.close()

    if not policies:
        print("未找到最近 7 天的政策数据")
        return

    print(f"找到 {len(policies)} 条最近政策，开始匹配...")

    # 执行批量匹配
    results = matcher.match_policies(policies, enterprise_id)

    # 打印摘要
    print_batch_summary(results)

    # 生成报告
    if args.report and results:
        reporter = ReportGenerator(str(BASE_DIR))
        print(f"\n正在生成报告...")

        for i, r in enumerate(results[:5], 1):  # 最多生成 5 份报告
            brief_path = reporter.generate_brief(r)
            print(f"  [{i}] {brief_path}")

        print(f"\n共生成 {min(len(results), 5)} 份报告")


# ============================================================
# Phase C: 定时任务管理
# ============================================================

def get_schedule_config():
    """获取定时任务配置"""
    return {
        "task_name": "EcoPolicy-AI-Scan",
        "description": "EcoPolicy AI 政策定时抓取与匹配",
        "script_path": str(BASE_DIR / "policy_matcher_cli.py"),
        "python_path": sys.executable,
        "working_dir": str(BASE_DIR),
        "log_dir": str(BASE_DIR / "policy_data" / "logs"),
    }


def generate_windows_task_xml(config: dict, enterprise: str, region: str = None, 
                               industry: str = None, schedule: str = "daily_8am") -> str:
    """生成 Windows Task Scheduler XML"""
    # 构建命令参数
    args = f'"{config["script_path"]}" scan --enterprise {enterprise}'
    if region:
        args += f' --region {region}'
    if industry:
        args += f' --industry {industry}'
    args += ' --report'

    # 调度时间
    if schedule == "daily_8am":
        trigger_xml = """
    <Triggers>
      <CalendarTrigger>
        <StartBoundary>2026-01-01T08:00:00</StartBoundary>
        <Enabled>true</Enabled>
        <ScheduleByDay>
          <DaysInterval>1</DaysInterval>
        </ScheduleByDay>
      </CalendarTrigger>
    </Triggers>"""
    elif schedule == "weekly_monday":
        trigger_xml = """
    <Triggers>
      <CalendarTrigger>
        <StartBoundary>2026-01-01T08:00:00</StartBoundary>
        <Enabled>true</Enabled>
        <ScheduleByWeek>
          <DaysOfWeek>
            <Monday />
          </DaysOfWeek>
          <WeeksInterval>1</WeeksInterval>
        </ScheduleByWeek>
      </CalendarTrigger>
    </Triggers>"""
    else:  # daily_8am as default
        trigger_xml = """
    <Triggers>
      <CalendarTrigger>
        <StartBoundary>2026-01-01T08:00:00</StartBoundary>
        <Enabled>true</Enabled>
        <ScheduleByDay>
          <DaysInterval>1</DaysInterval>
        </ScheduleByDay>
      </CalendarTrigger>
    </Triggers>"""

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{config['description']}</Description>
  </RegistrationInfo>
  {trigger_xml}
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{config['python_path']}</Command>
      <Arguments>{args}</Arguments>
      <WorkingDirectory>{config['working_dir']}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
    return xml


def generate_linux_cron(config: dict, enterprise: str, region: str = None,
                         industry: str = None, schedule: str = "daily_8am") -> str:
    """生成 Linux crontab 条目"""
    args = f'--enterprise {enterprise}'
    if region:
        args += f' --region {region}'
    if industry:
        args += f' --industry {industry}'
    args += ' --report'

    script = f'{config["python_path"]} {config["script_path"]} scan {args}'
    log_file = f'{config["log_dir"]}/scan_$(date +\\%Y\\%m\\%d).log'

    if schedule == "daily_8am":
        cron = f"0 8 * * * {script} >> {log_file} 2>&1"
    elif schedule == "weekly_monday":
        cron = f"0 8 * * 1 {script} >> {log_file} 2>&1"
    else:
        cron = f"0 8 * * * {script} >> {log_file} 2>&1"

    return cron


def cmd_schedule(args):
    """定时任务管理"""
    config = get_schedule_config()

    # 确保日志目录存在
    Path(config["log_dir"]).mkdir(parents=True, exist_ok=True)

    if args.show:
        # 显示当前配置
        print(f"\n{'='*60}")
        print(f"  定时任务配置")
        print(f"{'='*60}")
        print(f"  任务名称: {config['task_name']}")
        print(f"  脚本路径: {config['script_path']}")
        print(f"  Python:   {config['python_path']}")
        print(f"  工作目录: {config['working_dir']}")
        print(f"  日志目录: {config['log_dir']}")
        print(f"{'='*60}")

        # 检查是否已安装
        if sys.platform == "win32":
            result = subprocess.run(
                ["schtasks", "/query", "/tn", config["task_name"]],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"\n  状态: 已安装")
                print(f"  查看详情: schtasks /query /tn {config['task_name']} /v")
            else:
                print(f"\n  状态: 未安装")
        else:
            # Linux: 检查 crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if config["task_name"] in result.stdout:
                print(f"\n  状态: 已安装")
            else:
                print(f"\n  状态: 未安装")

        print(f"\n  安装命令: python policy_matcher_cli.py schedule --install --enterprise <ID>")
        print(f"  删除命令: python policy_matcher_cli.py schedule --remove")
        print()

    elif args.install:
        # 安装定时任务
        if not args.enterprise:
            print("错误: 请指定企业 ID（--enterprise）")
            sys.exit(1)

        enterprise = args.enterprise
        schedule_type = args.schedule_type or "daily_8am"

        print(f"\n{'='*60}")
        print(f"  安装定时任务")
        print(f"{'='*60}")
        print(f"  企业: {enterprise}")
        print(f"  地区: {args.region or '全国'}")
        print(f"  产业: {args.industry or '全部'}")
        print(f"  调度: {schedule_type}")
        print(f"{'='*60}\n")

        if sys.platform == "win32":
            # Windows: 使用 schtasks
            xml = generate_windows_task_xml(
                config, enterprise, args.region, args.industry, schedule_type
            )
            xml_path = BASE_DIR / "policy_data" / "task_schedule.xml"
            xml_path.write_text(xml, encoding="utf-16")

            result = subprocess.run(
                ["schtasks", "/create", "/tn", config["task_name"], 
                 "/xml", str(xml_path), "/f"],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                print("✓ 定时任务已安装")
                print(f"  查看: schtasks /query /tn {config['task_name']} /v")
                print(f"  运行: schtasks /run /tn {config['task_name']}")
                print(f"  删除: schtasks /delete /tn {config['task_name']} /f")
            else:
                print(f"✗ 安装失败: {result.stderr}")
                sys.exit(1)
        else:
            # Linux: 使用 crontab
            cron_entry = generate_linux_cron(
                config, enterprise, args.region, args.industry, schedule_type
            )

            # 添加任务名称注释
            cron_block = f"\n# {config['task_name']}\n{cron_entry}\n"

            # 读取现有 crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            existing = result.stdout if result.returncode == 0 else ""

            # 移除旧的 EcoPolicy 任务
            lines = existing.split("\n")
            filtered = []
            skip = False
            for line in lines:
                if config["task_name"] in line:
                    skip = True
                elif skip and line.strip() == "":
                    skip = False
                    continue
                elif not skip:
                    filtered.append(line)

            # 添加新任务
            new_crontab = "\n".join(filtered) + cron_block

            # 写入 crontab
            proc = subprocess.run(["crontab", "-"], input=new_crontab, 
                                  capture_output=True, text=True)
            if proc.returncode == 0:
                print("✓ 定时任务已安装")
                print(f"  查看: crontab -l")
                print(f"  删除: crontab -l | grep -v '{config['task_name']}' | crontab -")
            else:
                print(f"✗ 安装失败: {proc.stderr}")
                sys.exit(1)

    elif args.remove:
        # 删除定时任务
        print(f"\n{'='*60}")
        print(f"  删除定时任务")
        print(f"{'='*60}\n")

        if sys.platform == "win32":
            result = subprocess.run(
                ["schtasks", "/delete", "/tn", config["task_name"], "/f"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✓ 定时任务已删除")
            else:
                print(f"  任务不存在或删除失败: {result.stderr}")
        else:
            # Linux: 从 crontab 移除
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                filtered = [l for l in lines if config["task_name"] not in l]
                new_crontab = "\n".join(filtered)

                proc = subprocess.run(["crontab", "-"], input=new_crontab,
                                      capture_output=True, text=True)
                if proc.returncode == 0:
                    print("✓ 定时任务已删除")
                else:
                    print(f"  删除失败: {proc.stderr}")
            else:
                print("  未找到已安装的定时任务")

    else:
        print("请指定操作: --show / --install / --remove")


# ============================================================
# Phase D: AI Agent 模式 (Interactive & Autopilot)
# ============================================================

def cmd_chat(args):
    """启动 AI Agent 交互对话"""
    from ai_agent.chat import start_chat_session
    start_chat_session(args.enterprise)


def cmd_agent_scan(args):
    """手动触发 AI Agent 自动驾驶扫描与分析"""
    enterprise_id = args.enterprise
    from ai_agent.analyst import PolicyAnalystAgent
    from policy_monitor.database import PolicyDatabase

    enterprises_dir = BASE_DIR / "enterprises"
    matcher = EnterpriseMatcher(str(enterprises_dir))
    if enterprise_id not in matcher.get_enterprise_ids():
        print(f"错误: 未找到企业 '{enterprise_id}'")
        sys.exit(1)

    db_path = BASE_DIR / "policy_data" / "policies.db"
    data_dir = BASE_DIR / "policy_data"

    if not db_path.exists():
        print("未检测到数据库，请先执行政策抓取以填充数据。")
        sys.exit(1)

    db = PolicyDatabase(str(db_path), str(data_dir))
    days = args.days or 7
    policies = db.get_recent_policies(days=days)
    db.close()

    if not policies:
        print(f"未找到最近 {days} 天的政策数据，建议先执行 scan 抓取最新政策。")
        return

    print(f"找到 {len(policies)} 条最近政策，开始比对匹配...")
    matches = matcher.match_policies(policies, enterprise_id)
    # 筛选推荐等级在 3/5分 及以上且未分析过的政策
    valid_matches = [m for m in matches if m.recommendation_score >= 3]

    if not valid_matches:
        print("未发现匹配度高(评分>=3)的经济政策。自动驾驶分析结束。")
        return

    print(f"发现 {len(valid_matches)} 条推荐政策。开始启动 AI 自动深度分析生成流...")
    
    agent = PolicyAnalystAgent()
    for idx, match in enumerate(valid_matches, 1):
        print(f"\n[{idx}/{len(valid_matches)}] 正在自动分析政策: {match.policy_title}")
        
        prompt = f"""
请针对企业 '{enterprise_id}' 和以下匹配到的经济政策，执行标准分析工作流，完成四维打分、财务ROI计算，并自动生成、保存报告：

政策名称：{match.policy_title}
发布单位/来源：{match.policy_source}
政策链接：{match.policy_url}
发布日期：{match.policy_date}
政策摘要：{match.policy_summary}

你需要：
1. 运行 match_enterprise_policy 确认四维匹配指标
2. 运行 calculate_policy_roi 获得精准的量化财务回报和投入产出比
3. 生成一份详细的 Markdown 政策分析报告，必须包含 YAML 前置元数据、一句话判断、目录、多维评分及雷达图、ROI量化评估、提升路径、行动清单
4. 将报告保存至企业工作区（格式为 policy_analysis_YYYY-MM-DD_简短描述.md），并通过 write_markdown_report 保存。
"""
        try:
            agent.run(prompt, enterprise_id=enterprise_id)
            print(f"[OK] 政策 '{match.policy_title[:20]}...' 自动深度分析与报告保存成功。")
        except Exception as e:
            print(f"[!] 政策 '{match.policy_title[:20]}...' 分析失败: {e}")


def cmd_server(args):
    """启动 Skill 模式 Web API 服务"""
    import uvicorn
    from skills_api.server import app
    host = args.host or "127.0.0.1"
    port = args.port or 8000
    print(f"\n[*] 正在启动 EcoPolicy-AI Skills API 服务...")
    print(f"[*] 监听地址: http://{host}:{port}")
    print(f"[*] 交互式 Swagger 文档已上线: http://{host}:{port}/docs\n")
    uvicorn.run(app, host=host, port=port)


def cmd_mcp(args):
    """启动 Skill 模式 Model Context Protocol (MCP) 服务"""
    from skills_api.mcp_server import run_mcp_loop
    run_mcp_loop()


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="EcoPolicy AI — 政策匹配工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # list 命令
    subparsers.add_parser("list", help="列出已配置企业")

    # match 命令 (Phase A)
    match_parser = subparsers.add_parser("match", help="匹配用户上传政策")
    match_parser.add_argument("--enterprise", "-e", required=True, help="企业 ID")
    match_parser.add_argument("--url", "-u", help="政策链接")
    match_parser.add_argument("--file", "-f", help="政策文件路径")
    match_parser.add_argument("--text", "-t", help="政策文本内容")
    match_parser.add_argument("--report", "-r", action="store_true", help="生成报告")

    # scan 命令 (Phase B)
    scan_parser = subparsers.add_parser("scan", help="手动触发抓取+匹配")
    scan_parser.add_argument("--enterprise", "-e", required=True, help="企业 ID")
    scan_parser.add_argument("--region", help="指定省市地区")
    scan_parser.add_argument("--industry", help="指定产业分类")
    scan_parser.add_argument("--report", "-r", action="store_true", help="生成报告")

    # schedule 命令 (Phase C)
    schedule_parser = subparsers.add_parser("schedule", help="定时任务管理")
    schedule_parser.add_argument("--show", action="store_true", help="显示当前配置")
    schedule_parser.add_argument("--install", action="store_true", help="安装定时任务")
    schedule_parser.add_argument("--remove", action="store_true", help="删除定时任务")
    schedule_parser.add_argument("--enterprise", "-e", help="企业 ID（安装时必填）")
    schedule_parser.add_argument("--region", help="指定省市地区")
    schedule_parser.add_argument("--industry", help="指定产业分类")
    schedule_parser.add_argument("--schedule-type", choices=["daily_8am", "weekly_monday"],
                                  default="daily_8am", help="调度类型")

    # chat 命令 (Phase D)
    chat_parser = subparsers.add_parser("chat", help="启动经济政策 AI Agent 交互终端")
    chat_parser.add_argument("--enterprise", "-e", help="可选。默认目标企业 ID")

    # agent-scan 命令 (Phase D)
    agent_scan_parser = subparsers.add_parser("agent-scan", help="AI Agent 自动驾驶扫描与分析模式")
    agent_scan_parser.add_argument("--enterprise", "-e", required=True, help="企业 ID")
    agent_scan_parser.add_argument("--days", "-d", type=int, default=7, help="扫描最近几天内的政策，默认 7 天")

    # server 命令 (Phase D - Skill Mode)
    server_parser = subparsers.add_parser("server", help="启动 EcoPolicy-AI Skills API 服务 (Skill 模式)")
    server_parser.add_argument("--host", default="127.0.0.1", help="绑定 Host，默认 127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8000, help="绑定 Port，默认 8000")

    # mcp 命令 (Phase D - Skill Mode MCP)
    subparsers.add_parser("mcp", help="启动 EcoPolicy-AI Skills MCP 服务 (MCP 模式)")

    # 全局选项
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 执行命令
    if args.command == "list":
        enterprises_dir = BASE_DIR / "enterprises"
        matcher = EnterpriseMatcher(str(enterprises_dir))
        list_enterprises(matcher)
    elif args.command == "match":
        cmd_match(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "chat":
        cmd_chat(args)
    elif args.command == "agent-scan":
        cmd_agent_scan(args)
    elif args.command == "server":
        cmd_server(args)
    elif args.command == "mcp":
        cmd_mcp(args)
    else:
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
