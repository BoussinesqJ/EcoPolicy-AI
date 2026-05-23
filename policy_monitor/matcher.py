# -*- coding: utf-8 -*-
"""
关键词匹配 + 产业分类匹配 + 相关度评分

匹配机制（三层）：
  1. 全局关键词（global_keywords）：高/中/观察级
  2. 产业分类关键词（industries.yaml）：按行业自动加载
  3. 评分分级：>=6 P0, >=3 P1, <3 P2
"""

import logging
import os
from typing import Optional

import yaml

from utils import clean_text

logger = logging.getLogger("policy_monitor")


class IndustryMatcher:
    """从 industries.yaml 加载产业分类关键词"""

    def __init__(self, industries_path: str = None):
        self.industries = {}
        self._industry_flat = {}  # {行业ID: {keywords_high, keywords_medium, departments}}

        if industries_path and os.path.exists(industries_path):
            self._load(industries_path)

    def _load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 解析五大分类
        sections = [
            "strategic_emerging",
            "future_industries",
            "traditional_manufacturing",
            "infrastructure",
            "three_industries",
        ]

        for section in sections:
            category = data.get(section, {})
            if not category:
                continue

            category_name = category.get("name", section)
            subcats = category.get("subcategories", {})

            for sub_id, sub_info in subcats.items():
                if not isinstance(sub_info, dict):
                    continue
                key_high = sub_info.get("keywords_high", [])
                key_med = sub_info.get("keywords_medium", [])
                if key_high or key_med:
                    full_id = f"{section}.{sub_id}"
                    self._industry_flat[full_id] = {
                        "category": category_name,
                        "name": sub_info.get("name", sub_id),
                        "keywords_high": key_high,
                        "keywords_medium": key_med,
                        "departments": sub_info.get("departments", []),
                    }

            # 新兴支柱产业（strategic_emerging 下的 pillar_industries）
            pillars = category.get("pillar_industries", [])
            for pillar in pillars:
                if isinstance(pillar, dict):
                    full_id = f"{section}.pillar_{pillar.get('name', 'unknown')}"
                    self._industry_flat[full_id] = {
                        "category": category_name,
                        "name": pillar.get("name", ""),
                        "keywords_high": pillar.get("keywords_high", []),
                        "keywords_medium": pillar.get("keywords_medium", []),
                        "departments": [],
                    }

        # 传统制造业的稳定增长行业（扁平列表）
        trad = data.get("traditional_manufacturing", {})
        for item in trad.get("stable_growth", []):
            full_id = f"traditional_manufacturing.stable_{item}"
            self._industry_flat[full_id] = {
                "category": trad.get("name", "传统制造业"),
                "name": item,
                "keywords_high": [item],
                "keywords_medium": [],
                "departments": [],
            }

        logger.info(f"IndustryMatcher: loaded {len(self._industry_flat)} sub-industry profiles")

    def match(self, title: str, summary: str = "", target_industry: str = None) -> dict:
        """产业分类匹配

        Args:
            title: 政策标题
            summary: 政策摘要
            target_industry: 可选，指定目标行业分类（如 "strategic_emerging"）

        Returns:
            {
                "industry_matched": [{"category": ..., "name": ..., "keywords": [...]}],
                "industry_score": int
            }
        """
        title = clean_text(title)
        summary = clean_text(summary)

        matched_industries = []
        total_score = 0

        for ind_id, ind_info in self._industry_flat.items():
            # 如果指定了目标行业，只匹配该行业
            if target_industry and not ind_id.startswith(target_industry):
                continue

            ind_matched_kw = []
            ind_score = 0

            for kw in ind_info["keywords_high"]:
                if kw in title:
                    ind_matched_kw.append(kw)
                    ind_score += 4
                elif kw in summary:
                    ind_matched_kw.append(kw)
                    ind_score += 2

            for kw in ind_info["keywords_medium"]:
                if kw in title:
                    ind_matched_kw.append(kw)
                    ind_score += 2
                elif kw in summary:
                    ind_matched_kw.append(kw)
                    ind_score += 1

            if ind_matched_kw:
                matched_industries.append({
                    "category": ind_info["category"],
                    "name": ind_info["name"],
                    "keywords": list(dict.fromkeys(ind_matched_kw)),
                    "score": ind_score,
                    "departments": ind_info["departments"],
                })
                total_score += ind_score

        # 按得分排序
        matched_industries.sort(key=lambda x: x["score"], reverse=True)

        return {
            "industry_matched": matched_industries,
            "industry_score": total_score,
        }

    def list_industries(self) -> list:
        """列出所有已加载的产业分类"""
        result = []
        for ind_id, ind_info in self._industry_flat.items():
            result.append({
                "id": ind_id,
                "category": ind_info["category"],
                "name": ind_info["name"],
                "dept_count": len(ind_info["departments"]),
            })
        return result

    def get_industry_ids(self) -> list:
        """返回所有产业 ID"""
        return list(self._industry_flat.keys())

    def get_industry_prefixes(self) -> dict:
        """返回 {prefix: category_name} 映射，用于 --industry 参数"""
        prefixes = {}
        for ind_id in self._industry_flat:
            prefix = ind_id.split(".")[0]
            cat_name = self._industry_flat[ind_id]["category"]
            prefixes[prefix] = cat_name
        return prefixes


class KeywordMatcher:
    """关键词匹配器（全局关键词）"""

    def __init__(self, config: dict):
        keywords = config.get("global_keywords", {})
        self.high_priority = keywords.get("high_priority", [])
        self.medium_priority = keywords.get("medium_priority", [])
        self.watch = keywords.get("watch", [])

        scoring = config.get("scoring", {})
        self.p0_threshold = scoring.get("p0_threshold", 6)
        self.p1_threshold = scoring.get("p1_threshold", 3)

    def match(self, title: str, summary: str = "") -> dict:
        title = clean_text(title)
        summary = clean_text(summary)

        matched = []
        score = 0

        for kw in self.high_priority:
            if kw in title:
                matched.append(kw)
                score += 6
            elif kw in summary:
                matched.append(kw)
                score += 3

        for kw in self.medium_priority:
            if kw in title:
                matched.append(kw)
                score += 2
            elif kw in summary:
                matched.append(kw)
                score += 1

        for kw in self.watch:
            if kw in title or kw in summary:
                matched.append(f"[观察]{kw}")

        matched = list(dict.fromkeys(matched))

        if score >= self.p0_threshold:
            priority = "P0"
        elif score >= self.p1_threshold:
            priority = "P1"
        else:
            priority = "P2"

        return {
            "keywords_matched": matched,
            "score": score,
            "priority": priority,
        }

    def is_relevant(self, title: str, summary: str = "") -> bool:
        result = self.match(title, summary)
        return len([k for k in result["keywords_matched"] if not k.startswith("[观察]")]) > 0


def combined_match(
    title: str,
    summary: str,
    keyword_matcher: KeywordMatcher,
    industry_matcher: IndustryMatcher,
    target_industry: str = None,
) -> dict:
    """组合匹配：全局关键词 + 产业分类

    Returns:
        {
            # 全局关键词匹配结果
            "keywords_matched": [...],
            "global_score": int,
            "priority": "P0"/"P1"/"P2",
            # 产业分类匹配结果
            "industry_matched": [...],
            "industry_score": int,
            # 综合结果
            "total_score": int,
            "final_priority": "P0"/"P1"/"P2",
        }
    """
    # 全局关键词
    kw_result = keyword_matcher.match(title, summary)

    # 产业分类
    ind_result = industry_matcher.match(title, summary, target_industry)

    total = kw_result["score"] + ind_result["industry_score"]

    if total >= keyword_matcher.p0_threshold:
        final = "P0"
    elif total >= keyword_matcher.p1_threshold:
        final = "P1"
    else:
        final = "P2"

    return {
        "keywords_matched": kw_result["keywords_matched"],
        "global_score": kw_result["score"],
        "priority": kw_result["priority"],
        "industry_matched": ind_result["industry_matched"],
        "industry_score": ind_result["industry_score"],
        "total_score": total,
        "final_priority": final,
    }
