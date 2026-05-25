# -*- coding: utf-8 -*-
"""
政策监控系统 - 入口脚本
用法：
  python main.py scan --url "https://..."     Analyze a single policy URL
  python main.py scan --file policy.pdf       Analyze a local policy file
  python main.py match --enterprise example   Match policies against an enterprise
  python main.py run                          Batch crawl all sources
  python main.py run --source "国务院"        Crawl a single named source
  python main.py run --limit 10               Crawl first 10 sources only
  python main.py run --region 湖北            Crawl national + Hubei
  python main.py stats                        Show database statistics
  python main.py export                       Export latest data
  python main.py list-regions                 List configured regions
  python main.py list-industries              List industry classification
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
from parsers import parse_html, parse_api
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
    failed_sources = []
    success_count = 0

    # 每个 API 源抓取多页（默认 3 页）
    max_pages = config.get("safety", {}).get("max_pages_per_source", 3)

    logger.info(f"Starting crawl: {len(enabled_sources)} sources" +
                (f", industry filter: {target_industry}" if target_industry else ""))

    for i, source in enumerate(enabled_sources):
        source_name = source["name"]
        source_url = source["url"]
        source_type = source.get("type", "html")
        selectors = source.get("selectors", {})

        logger.info(f"\n[{i+1}/{len(enabled_sources)}] Processing: {source_name} ({source_type})")

        try:
            all_policies = []

            if source_type == "api":
                # API 源：支持分页抓取多页
                for page in range(max_pages):
                    # 构建分页 URL（国务院 API 的 n 参数控制每页条数，p 参数控制页码）
                    page_url = source_url
                    if "n=20" in page_url and page > 0:
                        page_url = page_url.replace("n=20", f"n=20&p={page}")
                    elif "?" in page_url:
                        page_url += f"&p={page}"

                    html = fetcher.fetch(page_url, source_type="api")
                    if not html:
                        break
                    page_policies = parse_api(page_url, html, source_name)
                    if not page_policies:
                        break
                    all_policies.extend(page_policies)
                    logger.info(f"  Page {page + 1}: {len(page_policies)} policies")
            else:
                # HTML 源：单页抓取
                html = fetcher.fetch(source_url, source_type="html")
                all_policies = parse_html(source_url, html, source_name, selectors) if html else []

            # 组合匹配：全局关键词 + 产业分类（summary 作为全文匹配）
            for p in all_policies:
                result = combined_match(
                    p["title"],
                    p.get("summary", ""),
                    kw_matcher,
                    ind_matcher,
                    target_industry,
                    full_text=p.get("summary", ""),
                )
                p["keywords_matched"] = result["keywords_matched"]
                p["score"] = result["total_score"]
                p["priority"] = result["final_priority"]

                if result["industry_matched"]:
                    top_industry = result["industry_matched"][0]
                    p["industry"] = f"{top_industry['category']} > {top_industry['name']}"
                    p["industry_keywords"] = top_industry["keywords"]

            # 存入数据库
            new_count = db.insert_batch(all_policies)
            new_in_this_source = [p for p in all_policies if p.get("score", 0) > 0]

            logger.info(f"  {source_name}: fetched {len(all_policies)}, new {new_count}, relevant {len(new_in_this_source)}")

            all_new_policies.extend(new_in_this_source)
            success_count += 1

        except Exception as e:
            logger.error(f"  {source_name} FAILED: {e}")
            failed_sources.append(source_name)
            continue

    # 导出数据
    logger.info("\nExporting data...")
    db.export_all()

    # 生成通知
    if all_new_policies:
        alert_path = notifier.generate_daily_alert(all_new_policies)
        notifier.print_summary(all_new_policies)
    else:
        logger.info("No new relevant policies found")

    # 打印统计
    stats = db.stats()
    logger.info(f"\nDatabase: {stats['total']} total | P0: {stats['P0']} | P1: {stats['P1']} | P2: {stats['P2']}")
    logger.info(f"Sources: {success_count} success, {len(failed_sources)} failed")
    if failed_sources:
        logger.info(f"Failed: {', '.join(failed_sources)}")

    fetcher.close()
    db.close()

    return all_new_policies


def scan_url(config: dict, url: str):
    """按需分析：抓取单个政策 URL 并生成摘要"""
    from parsers import parse_html, parse_api

    fetcher = SafeFetcher(config)
    kw_matcher = KeywordMatcher(config)
    ind_matcher = IndustryMatcher(str(INDUSTRIES_PATH))
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))

    logger.info(f"Fetching: {url}")

    # 判断是 API 还是 HTML
    source_type = "api" if "gov.cn/search-gov" in url else "html"
    html = fetcher.fetch(url, source_type=source_type)

    if not html:
        logger.error("Failed to fetch URL")
        fetcher.close()
        return []

    if source_type == "api":
        policies = parse_api(url, html, "scan-url")
    else:
        policies = parse_html(url, html, "scan-url", {})

    if not policies:
        logger.warning("No policies found in URL")
        fetcher.close()
        return []

    # 匹配关键词
    for p in policies:
        result = combined_match(
            p["title"], p.get("summary", ""),
            kw_matcher, ind_matcher, None,
            full_text=p.get("summary", ""),
        )
        p["keywords_matched"] = result["keywords_matched"]
        p["score"] = result["total_score"]
        p["priority"] = result["final_priority"]
        if result["industry_matched"]:
            top = result["industry_matched"][0]
            p["industry"] = f"{top['category']} > {top['name']}"
            p["industry_keywords"] = top["keywords"]

    # 存入数据库
    new_count = db.insert_batch(policies)

    # 输出结果
    print(f"\n{'='*60}")
    print(f"  Scan Result: {url}")
    print(f"{'='*60}")
    print(f"  Found: {len(policies)} policies")
    print(f"  New:   {new_count}")
    print(f"  Matching policies (score > 0):")
    relevant = [p for p in policies if p.get("score", 0) > 0]
    if relevant:
        for p in relevant:
            print(f"    [{p['priority']}] {p['title']} (score={p['score']})")
            if p.get("industry"):
                print(f"         Industry: {p['industry']}")
    else:
        print("    No matching policies found")
    print(f"{'='*60}\n")

    fetcher.close()
    db.close()
    return policies


def scan_file(config: dict, file_path: str):
    """按需分析：解析本地政策文件并生成摘要"""
    import re

    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return []

    text = path.read_text(encoding="utf-8", errors="ignore")

    kw_matcher = KeywordMatcher(config)
    ind_matcher = IndustryMatcher(str(INDUSTRIES_PATH))
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))

    # 简单解析：按段落拆分，提取标题
    lines = text.strip().split("\n")
    title = lines[0].strip() if lines else path.stem
    summary = "\n".join(lines[1:100]) if len(lines) > 1 else ""

    policies = [{
        "title": title[:200],
        "url": f"file://{path.absolute()}",
        "date": "",
        "source": f"file:{path.name}",
        "summary": summary[:2000],
    }]

    # 匹配关键词
    for p in policies:
        result = combined_match(
            p["title"], p.get("summary", ""),
            kw_matcher, ind_matcher, None,
            full_text=p.get("summary", ""),
        )
        p["keywords_matched"] = result["keywords_matched"]
        p["score"] = result["total_score"]
        p["priority"] = result["final_priority"]
        if result["industry_matched"]:
            top = result["industry_matched"][0]
            p["industry"] = f"{top['category']} > {top['name']}"
            p["industry_keywords"] = top["keywords"]

    new_count = db.insert_batch(policies)

    # 输出结果
    print(f"\n{'='*60}")
    print(f"  File Scan: {path.name}")
    print(f"{'='*60}")
    print(f"  Title:    {title[:100]}")
    print(f"  Keywords matched:")
    relevant = [p for p in policies if p.get("score", 0) > 0]
    if relevant:
        for p in relevant:
            print(f"    [{p['priority']}] Score: {p['score']}")
            if p.get("keywords_matched"):
                print(f"         Keywords: {', '.join(p['keywords_matched'][:10])}")
            if p.get("industry"):
                print(f"         Industry: {p['industry']}")
    else:
        print("    No matching policies found")
    print(f"{'='*60}\n")

    db.close()
    return policies


def match_enterprise(config: dict, enterprise_id: str):
    """匹配企业画像与政策数据库"""
    # 尝试加载企业画像
    enterprises_dir = BASE_DIR / "enterprises"
    profile_path = enterprises_dir / enterprise_id / "profile.yaml"
    if not profile_path.exists():
        logger.error(f"Enterprise not found: {enterprise_id}")
        print(f"\n  Available enterprises:")
        if enterprises_dir.exists():
            for d in enterprises_dir.iterdir():
                if d.is_dir() and (d / "profile.yaml").exists():
                    print(f"    - {d.name}")
        return

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)

    # 加载偏好
    prefs_path = enterprises_dir / enterprise_id / "preferences.yaml"
    preferences = None
    if prefs_path.exists():
        with open(prefs_path, "r", encoding="utf-8") as f:
            preferences = yaml.safe_load(f)

    enterprise = {"id": enterprise_id, "profile": profile}
    if preferences:
        enterprise["preferences"] = preferences

    # 加载数据库政策
    db = PolicyDatabase(str(DB_PATH), str(DATA_DIR))
    stats = db.stats()

    if stats["total"] == 0:
        logger.warning("Database is empty. Run 'python main.py run' first.")
        db.close()
        return

    print(f"\n{'='*60}")
    print(f"  Match: {profile.get('company_name', enterprise_id)}")
    print(f"  DB: {stats['total']} policies ({stats['P0']} P0, {stats['P1']} P1, {stats['P2']} P2)")
    print(f"{'='*60}")

    # 简单匹配：遍历数据库所有政策
    try:
        from enterprise_matcher import EnterpriseMatcher
        matcher = EnterpriseMatcher(str(enterprises_dir))
        policies = db.get_latest(limit=500)
        results = matcher.match_policies(policies, enterprise_id=enterprise_id)
        if results:
            for r in results[:10]:
                print(f"  [{r.recommendation}] {r.policy_title[:60]} (score={r.score_total})")
        else:
            print("  No matching policies found")
    except ImportError:
        logger.warning("enterprise_matcher.py not found, using keyword matching only")
        # Fallback: use keyword matcher
        kw_matcher = KeywordMatcher(config)
        all_policies = db.get_all()
        matched = []
        for p in all_policies:
            result = kw_matcher.match(p["title"], p.get("summary", ""))
            if result["score"] > 0:
                matched.append((p, result))
        matched.sort(key=lambda x: x[1]["score"], reverse=True)
        if matched:
            for p, r in matched[:10]:
                print(f"  [{r['priority']}] {p['title'][:60]} (score={r['score']})")
        else:
            print("  No matching policies found")

    print(f"{'='*60}\n")
    db.close()


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


def run_fetch_limit(config: dict, region: str = None, industry: str = None,
                     limit: int = None, source: str = None):
    """Wrapper around run_fetch with limit and source filters"""
    if limit or source:
        # Filter sources before fetching
        sources = config.get("sources", [])
        enabled = [s for s in sources if s.get("enabled", True)]

        if source:
            enabled = [s for s in enabled if source.lower() in s.get("name", "").lower()]
            logger.info(f"Filtered to {len(enabled)} source(s) matching '{source}'")

        if limit:
            enabled = enabled[:limit]
            logger.info(f"Limited to {len(enabled)} source(s)")

        # Temporarily override config
        modified_config = dict(config)
        modified_config["sources"] = enabled
        run_fetch(modified_config, region=region, industry=industry)
    else:
        run_fetch(config, region=region, industry=industry)


def main():
    parser = argparse.ArgumentParser(
        description="Policy Monitor - Policy analysis and monitoring system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # On-demand analysis (recommended)
  python main.py scan --url "https://www.gov.cn/..."
  python main.py scan --file policy.pdf
  python main.py match --enterprise example

  # Batch crawl
  python main.py run                                       All sources
  python main.py run --source "国务院"                     Single source
  python main.py run --limit 10                            First 10 sources
  python main.py run --region Hubei                        National + Hubei
  python main.py run --industry strategic_emerging         Filter by industry

  # Utilities
  python main.py stats                                     Database statistics
  python main.py export                                    Export data
  python main.py list-regions                              List regions
  python main.py list-industries                           List industries
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # scan subcommand
    scan_parser = subparsers.add_parser("scan", help="Scan a single policy URL or file")
    scan_parser.add_argument("--url", type=str, help="Policy URL to scan")
    scan_parser.add_argument("--file", type=str, help="Local policy file path")

    # match subcommand
    match_parser = subparsers.add_parser("match", help="Match policies against an enterprise")
    match_parser.add_argument("--enterprise", "-e", type=str, required=True, help="Enterprise ID")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Batch crawl policy sources")
    run_parser.add_argument("--region", "-r", type=str, default=None, help="Region (e.g. Hubei)")
    run_parser.add_argument("--industry", "-i", type=str, default=None, help="Industry filter")
    run_parser.add_argument("--limit", "-l", type=int, default=None, help="Max sources to crawl")
    run_parser.add_argument("--source", "-s", type=str, default=None, help="Source name filter (e.g. '国务院')")

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

    if args.command == "scan":
        if args.url:
            scan_url(config, args.url)
        elif args.file:
            scan_file(config, args.file)
        else:
            print("Error: --url or --file required")
            sys.exit(1)
    elif args.command == "match":
        match_enterprise(config, args.enterprise)
    elif args.command == "run":
        run_fetch_limit(config, region=args.region, industry=args.industry,
                       limit=args.limit, source=args.source)
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
