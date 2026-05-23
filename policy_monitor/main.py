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
    print(f"  政策数据库统计")
    print(f"{'='*50}")
    print(f"  总计: {stats['total']} 条")
    print(f"  P0 紧急: {stats['P0']} 条")
    print(f"  P1 重要: {stats['P1']} 条")
    print(f"  P2 观察: {stats['P2']} 条")
    print(f"\n  按来源:")
    for source, count in stats["by_source"].items():
        print(f"    {source}: {count} 条")
    print(f"{'='*50}\n")

    db.close()


def export_data(config: dict):
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))
    db.export_all()
    print(f"数据已导出到: {DATA_DIR}")
    db.close()


def list_regions(config: dict):
    regions_config = config.get("regions", {})
    regions_dir = Path(__file__).parent / regions_config.get("dir", "regions")
    regions = list_all_regions(str(regions_dir))

    if not regions:
        print("\n  暂无已配置的省市地区。")
        return

    print(f"\n{'='*60}")
    print(f"  已配置的省市地区（共 {len(regions)} 个）")
    print(f"{'='*60}")
    print(f"  {'地区':<10} {'别名':<20} {'数据源数':<8} {'上级省份'}")
    print(f"  {'-'*10} {'-'*20} {'-'*8} {'-'*10}")
    for r in regions:
        aliases = ", ".join(r["aliases"][:3])
        parent = r.get("parent_province") or "-"
        print(f"  {r['name']:<10} {aliases:<20} {r['source_count']:<8} {parent}")
    print(f"\n  用法: python main.py run --region <地区名>")
    print(f"  示例: python main.py run --region 湖北")
    print(f"{'='*60}\n")


def list_industries():
    """列出所有产业分类"""
    ind_matcher = IndustryMatcher(str(INDUSTRIES_PATH))
    prefixes = ind_matcher.get_industry_prefixes()
    profiles = ind_matcher.list_industries()

    print(f"\n{'='*60}")
    print(f"  产业分类体系（共 {len(profiles)} 个子行业）")
    print(f"{'='*60}")

    # 按大类分组
    by_category = {}
    for p in profiles:
        cat = p["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)

    for prefix, cat_name in prefixes.items():
        items = by_category.get(cat_name, [])
        print(f"\n  [{prefix}] {cat_name}（{len(items)} 个子行业）")
        for item in items:
            sub_prefix = item["id"].split(".", 1)[1] if "." in item["id"] else item["id"]
            print(f"    - {item['name']:<16} 关键词关联部门: {item['dept_count']} 个")

    print(f"\n{'='*60}")
    print(f"  用法:")
    print(f"    python main.py run --industry strategic_emerging     战略性新兴产业")
    print(f"    python main.py run --industry future_industries     未来产业")
    print(f"    python main.py run --industry traditional_manufacturing  传统制造业")
    print(f"    python main.py run --industry infrastructure       基础设施")
    print(f"    python main.py run --industry three_industries     三次产业")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="政策监控系统 - 抓取国家/省市政策资讯，支持产业分类匹配",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py run                                      只抓国家级数据源
  python main.py run --region 湖北                        抓取国家级 + 湖北省
  python main.py run --industry strategic_emerging        只看战略性新兴产业
  python main.py run --region 恩施 --industry three_industries  湖北恩施 + 三次产业
  python main.py stats                                    显示数据库统计
  python main.py export                                   导出最新数据
  python main.py list-regions                             列出所有已配置省市
  python main.py list-industries                          列出产业分类体系
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # run 子命令
    run_parser = subparsers.add_parser("run", help="运行一次抓取")
    run_parser.add_argument(
        "--region", "-r",
        type=str, default=None,
        help="指定省市地区（如：湖北、恩施、海南）",
    )
    run_parser.add_argument(
        "--industry", "-i",
        type=str, default=None,
        help="指定产业分类（如：strategic_emerging、future_industries）",
    )

    # stats 子命令
    subparsers.add_parser("stats", help="显示数据库统计")

    # export 子命令
    subparsers.add_parser("export", help="导出最新数据")

    # list-regions 子命令
    subparsers.add_parser("list-regions", help="列出所有已配置省市")

    # list-industries 子命令
    subparsers.add_parser("list-industries", help="列出产业分类体系")

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
        print(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
