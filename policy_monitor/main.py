# -*- coding: utf-8 -*-
"""
政策监控系统 - 入口脚本
用法：
  python main.py run                         运行一次抓取（国家级）
  python main.py run --region 湖北            抓取国家级 + 湖北省
  python main.py run --industry strategic_emerging   按产业分类抓取/筛选
  python main.py stats                       显示数据库统计
  python main.py export                      导出最新数据
  python main.py list-regions                列出已配置省市
  python main.py list-industries             列出产业分类
"""

import sys
import os
import logging
import argparse
from pathlib import Path

import yaml

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import SafeFetcher
from database import PolicyDatabase
from matcher import KeywordMatcher, IndustryMatcher, combined_match
from notifier import Notifier
from region_loader import get_sources_for_region, list_all_regions
from parsers import parse_rss, parse_html, parse_sitemap, parse_api
from utils import now_iso, today_str

# ============================================================
# 配置
# ============================================================

BASE_DIR = Path(__file__).parent.parent  # project root
CONFIG_PATH = Path(__file__).parent / "config.yaml"
INDUSTRIES_PATH = Path(__file__).parent / "industries.yaml"
DATA_DIR = BASE_DIR / "policy_data"
DB_PATH = DATA_DIR / "policies.db"
ALERTS_DIR = DATA_DIR / "alerts"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("policy_monitor")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_fetch(config: dict, region: str = None, industry: str = None):
    """运行一次完整的政策抓取

    Args:
        config: 配置字典
        region: 可选，指定省市名称（如 "湖北"、"恩施"）
        industry: 可选，指定产业分类（如 "strategic_emerging"）
    """
    fetcher = SafeFetcher(config)
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))
    kw_matcher = KeywordMatcher(config)
    ind_matcher = IndustryMatcher(str(INDUSTRIES_PATH))
    notifier = Notifier(str(ALERTS_DIR))

    # 产业分类筛选
    target_industry = None
    if industry:
        # 验证产业 ID 是否存在
        all_ids = ind_matcher.get_industry_ids()
        matches = [i for i in all_ids if i.startswith(industry)]
        if not matches:
            prefixes = ind_matcher.get_industry_prefixes()
            if industry in prefixes:
                target_industry = industry
                logger.info(f"产业筛选: {prefixes[industry]} ({industry})")
            else:
                logger.warning(f"未找到产业分类 '{industry}'，可用: {', '.join(prefixes.keys())}")
        else:
            target_industry = industry

    # 加载数据源
    if region:
        regions_config = config.get("regions", {})
        regions_dir = Path(__file__).parent / regions_config.get("dir", "regions")
        national_sources = [s for s in config.get("sources", []) if s.get("enabled", True)]
        include_national = regions_config.get("include_national", True)

        result = get_sources_for_region(
            region_name=region,
            regions_dir=str(regions_dir),
            include_national=include_national,
            national_sources=national_sources,
        )

        if result.get("error"):
            logger.error(result["error"])
            return []

        chain = result["region_chain"]
        enabled_sources = [s for s in result["sources"] if s.get("enabled", True)]
        logger.info(f"地区模式: {' -> '.join(chain)}")
    else:
        sources = config.get("sources", [])
        enabled_sources = [s for s in sources if s.get("enabled", True)]

    all_new_policies = []

    logger.info(f"开始抓取，共 {len(enabled_sources)} 个数据源" +
                (f"，产业筛选: {target_industry}" if target_industry else ""))

    for i, source in enumerate(enabled_sources):
        source_name = source["name"]
        source_url = source["url"]
        source_type = source.get("type", "html")
        selectors = source.get("selectors", {})

        logger.info(f"\n[{i+1}/{len(enabled_sources)}] 正在处理: {source_name} ({source_type})")

        try:
            # 抓取页面
            if source_type == "api":
                html = fetcher.fetch(source_url)
                policies = parse_api(source_url, html, source_name) if html else []
            elif source_type == "rss":
                html = fetcher.fetch(source_url)
                policies = parse_rss(source_url, source_name, html) if html else []
            elif source_type == "sitemap":
                content = fetcher.fetch_bytes(source_url)
                policies = parse_sitemap(source_url, content.decode("utf-8", errors="replace"), source_name) if content else []
            else:
                html = fetcher.fetch(source_url)
                policies = parse_html(source_url, html, source_name, selectors) if html else []

            # 组合匹配：全局关键词 + 产业分类
            for p in policies:
                result = combined_match(
                    p["title"],
                    p.get("summary", ""),
                    kw_matcher,
                    ind_matcher,
                    target_industry,
                )
                p["keywords_matched"] = result["keywords_matched"]
                p["score"] = result["total_score"]
                p["priority"] = result["final_priority"]

                # 附加产业匹配信息
                if result["industry_matched"]:
                    top_industry = result["industry_matched"][0]
                    p["industry"] = f"{top_industry['category']} > {top_industry['name']}"
                    p["industry_keywords"] = top_industry["keywords"]

            # 存入数据库
            new_count = db.insert_batch(policies)
            new_in_this_source = [p for p in policies if p.get("score", 0) > 0]

            logger.info(f"  {source_name}: 抓取 {len(policies)} 条，新增 {new_count} 条，相关 {len(new_in_this_source)} 条")

            all_new_policies.extend(new_in_this_source)

        except Exception as e:
            logger.error(f"  {source_name} 处理失败: {e}")
            continue

    # 导出数据
    logger.info("\n导出数据...")
    db.export_all()

    # 生成通知
    if all_new_policies:
        alert_path = notifier.generate_daily_alert(all_new_policies)
        notifier.print_summary(all_new_policies)
    else:
        logger.info("本次运行无相关新增政策")

    # 打印统计
    stats = db.stats()
    logger.info(f"\n数据库统计: 总计 {stats['total']} 条 | P0: {stats['P0']} | P1: {stats['P1']} | P2: {stats['P2']}")

    fetcher.close()
    db.close()

    return all_new_policies


def show_stats(config: dict):
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))
    stats = db.stats()

    print(f"\n{'='*50}")
    print(f"  Policy Database Statistics")
    print(f"{'='*50}")
    print(f"  Total: {stats['total']}")
    print(f"  P0 Critical: {stats['P0']}")
    print(f"  P1 Important: {stats['P1']}")
    print(f"  P2 Monitor: {stats['P2']}")
    print(f"\n  By source:")
    for source, count in stats["by_source"].items():
        print(f"    {source}: {count}")
    print(f"{'='*50}\n")

    db.close()


def export_data(config: dict):
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))
    db.export_all()
    print(f"Data exported to: {DATA_DIR}")
    db.close()


def list_regions(config: dict):
    regions_config = config.get("regions", {})
    regions_dir = Path(__file__).parent / regions_config.get("dir", "regions")
    regions = list_all_regions(str(regions_dir))

    if not regions:
        print("\n  No regions configured.")
        return

    print(f"\n{'='*60}")
    print(f"  Configured Regions ({len(regions)} total)")
    print(f"{'='*60}")
    print(f"  {'Region':<10} {'Aliases':<20} {'Sources':<8} {'Parent'}")
    print(f"  {'-'*10} {'-'*20} {'-'*8} {'-'*10}")
    for r in regions:
        aliases = ", ".join(r["aliases"][:3])
        parent = r.get("parent_province") or "-"
        print(f"  {r['name']:<10} {aliases:<20} {r['source_count']:<8} {parent}")
    print(f"\n  Usage: python main.py run --region <region_name>")
    print(f"  Example: python main.py run --region Hubei")
    print(f"{'='*60}\n")


def list_industries():
    """列出所有产业分类"""
    ind_matcher = IndustryMatcher(str(INDUSTRIES_PATH))
    prefixes = ind_matcher.get_industry_prefixes()
    profiles = ind_matcher.list_industries()

    print(f"\n{'='*60}")
    print(f"  Industry Classification ({len(profiles)} sub-industries)")
    print(f"{'='*60}")

    # Group by category
    by_category = {}
    for p in profiles:
        cat = p["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)

    for prefix, cat_name in prefixes.items():
        items = by_category.get(cat_name, [])
        print(f"\n  [{prefix}] {cat_name} ({len(items)} sub-industries)")
        for item in items:
            sub_prefix = item["id"].split(".", 1)[1] if "." in item["id"] else item["id"]
            print(f"    - {item['name']:<16} departments: {item['dept_count']}")

    print(f"\n{'='*60}")
    print(f"  Usage:")
    print(f"    python main.py run --industry strategic_emerging")
    print(f"    python main.py run --industry future_industries")
    print(f"    python main.py run --industry traditional_manufacturing")
    print(f"    python main.py run --industry infrastructure")
    print(f"    python main.py run --industry three_industries")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Policy Monitor - Crawl national/provincial policy feeds with industry classification matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                                      National sources only
  python main.py run --region Hubei                       National + Hubei province
  python main.py run --industry strategic_emerging        Strategic emerging industries
  python main.py run --region Enshi --industry three_industries  Hubei Enshi + three industries
  python main.py stats                                    Show database statistics
  python main.py export                                   Export latest data
  python main.py list-regions                             List all configured regions
  python main.py list-industries                          List industry classification
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Run one crawl")
    run_parser.add_argument(
        "--region", "-r",
        type=str, default=None,
        help="Specify region (e.g. Hubei, Enshi, Hainan)",
    )
    run_parser.add_argument(
        "--industry", "-i",
        type=str, default=None,
        help="Specify industry (e.g. strategic_emerging, future_industries)",
    )

    # stats subcommand
    subparsers.add_parser("stats", help="Show database statistics")

    # export subcommand
    subparsers.add_parser("export", help="Export latest data")

    # list-regions subcommand
    subparsers.add_parser("list-regions", help="List all configured regions")

    # list-industries subcommand
    subparsers.add_parser("list-industries", help="List industry classification")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = load_config()

    if args.command == "run":
        run_fetch(config, region=args.region, industry=args.industry)
    elif args.command == "stats":
        show_stats(config)
    elif args.command == "export":
        export_data(config)
    elif args.command == "list-regions":
        list_regions(config)
    elif args.command == "list-industries":
        list_industries()
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
