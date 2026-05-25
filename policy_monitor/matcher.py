# -*- coding: utf-8 -*-
"""
关键词匹配 + 产业分类匹配 + 相关度评分 + jieba 分词

匹配机制（五层）：
  1. 全局关键词（global_keywords）：高/中/观察级
  2. 同义词扩展（SYNONYM_MAP）：将行业术语自动展开
  3. jieba 分词匹配：将政策文本分词后匹配，解决"智能制造示范工厂"匹配"智能工厂"的问题
  4. 产业分类关键词（industries.yaml）：按行业自动加载
  5. 评分分级：>=6 P0, >=3 P1, <3 P2
"""

import logging
import os
from typing import Optional

import yaml

from utils import clean_text

# jieba 分词（可选依赖）
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
    # 静默模式
    jieba.setLogLevel(logging.WARNING)
except ImportError:
    JIEBA_AVAILABLE = False

logger = logging.getLogger("policy_monitor")

# ============================================================
# 扩展同义词映射表：覆盖五大产业分类的常用政策术语
# ============================================================
SYNONYM_MAP = {
    # --- 种业/农业 ---
    "种子": ["种业", "品种", "育种", "良种", "制种", "亲本"],
    "种业": ["种子", "育种", "品种审定", "良种", "制种", "种质资源", "种子法"],
    "育种": ["种业", "品种选育", "杂交", "分子育种", "基因编辑育种", "生物育种"],
    "农业": ["种植", "农学", "农艺", "耕地", "粮食", "乡村振兴", "农业现代化"],
    "粮食": ["粮食安全", "口粮", "谷物", "粮食生产", "粮食产量", "藏粮于地"],
    "转基因": ["生物育种", "基因编辑", "基因改造", "生物安全", "转基因品种"],
    "农机": ["农业机械", "农机装备", "智能农机", "机械化", "农业机械化"],
    "种质资源": ["种质库", "基因库", "遗传资源", "种质保存"],
    # --- 煤炭/能源 ---
    "煤矿": ["煤炭", "矿井", "采煤", "井工矿", "露天矿", "煤矿安全", "煤矿智能化"],
    "煤炭": ["煤矿", "采掘", "煤炭清洁利用", "煤化工", "煤炭产业", "煤炭清洁"],
    "能源": ["电力", "发电", "油气", "能源安全", "能源转型"],
    "光伏": ["太阳能", "光伏发电", "光伏组件", "光伏电站", "分布式光伏"],
    "风电": ["风力发电", "风机", "海上风电", "陆上风电"],
    "储能": ["新型储能", "电化学储能", "抽水蓄能", "储能电池", "储能技术"],
    "氢能": ["氢燃料", "制氢", "储氢", "燃料电池", "氢能产业"],
    "核能": ["核电", "核技术", "核聚变", "核安全"],
    "碳达峰": ["碳中和", "双碳", "碳排放", "温室气体", "碳交易", "碳金融"],
    # --- 生态/环保 ---
    "生态修复": ["生态治理", "生态恢复", "山水林田湖草", "矿山修复", "湿地修复",
                  "生态修复", "生态环保", "生态系统修复"],
    "环保": ["生态环境", "污染防治", "污染治理", "清洁生产", "环境保护"],
    "绿色发展": ["绿色制造", "循环经济", "资源综合利用", "节能减排", "绿色工厂"],
    "环境治理": ["大气治理", "水治理", "土壤修复", "固废处理", "垃圾处理"],
    # --- 制造业 ---
    "智能制造": ["智能工厂", "数字化车间", "灯塔工厂", "工业4.0", "智能制造示范"],
    "工业母机": ["数控机床", "机床", "加工中心", "五轴", "高端数控"],
    "机器人": ["工业机器人", "服务机器人", "人形机器人", "协作机器人", "机器人产业"],
    "高端装备": ["装备制造", "重大技术装备", "首台套", "装备国产化"],
    "专精特新": ["专精特新", "小巨人", "制造业单项冠军", "隐形冠军"],
    "技术改造": ["技改", "技改升级", "设备更新", "产线改造", "智能化改造"],
    # --- 数字经济 ---
    "人工智能": ["AI", "大模型", "机器学习", "深度学习", "智能体", "AIGC", "生成式AI"],
    "大数据": ["数据挖掘", "数据分析", "数据处理", "数据服务", "大数据产业"],
    "算力": ["算力中心", "智算", "超算", "算力网络", "算力基础设施"],
    "数据要素": ["数据资产", "数据交易", "数据流通", "数据入表", "数据要素化"],
    "集成电路": ["芯片", "半导体", "晶圆", "EDA", "集成电路产业"],
    "5G": ["5G网络", "5G应用", "5G基站", "新一代通信"],
    "物联网": ["IoT", "传感器", "工业互联网", "万物互联"],
    "区块链": ["区块链技术", "分布式账本", "联盟链"],
    "云计算": ["云服务", "SaaS", "PaaS", "IaaS", "上云"],
    "网络安全": ["信息安全", "数据安全", "网络安全", "密码技术"],
    # --- 生物医药 ---
    "创新药": ["新药", "原研药", "1类新药", "First-in-class", "创新药物"],
    "医疗器械": ["医疗设备", "体外诊断", "IVD", "高值耗材", "医疗器械"],
    "基因治疗": ["细胞治疗", "基因编辑", "CAR-T", "mRNA", "基因疗法"],
    "生物医药": ["生物技术", "生物制药", "生物产业", "生命科学"],
    "中药": ["中医药", "中药材", "中成药", "中药现代化"],
    # --- 新材料 ---
    "碳纤维": ["碳纤维复合材料", "碳基材料", "石墨烯", "碳纤维产业化"],
    "半导体": ["芯片", "集成电路", "晶圆", "EDA", "半导体材料"],
    "稀土": ["稀土材料", "稀土功能材料", "稀土永磁", "稀土资源"],
    "新材料": ["先进材料", "功能材料", "高性能材料", "材料创新"],
    "3D打印": ["增材制造", "3D打印技术", "增材制造技术"],
    # --- 航空航天/低空 ---
    "航空航天": ["航空", "航天", "卫星", "火箭", "商业航天", "航天技术"],
    "低空经济": ["无人机", "eVTOL", "低空飞行", "通用航空", "低空空域"],
    # --- 基础设施 ---
    "算力网": ["算力网络", "算力基础设施", "智算中心", "超算中心"],
    "电网": ["电力系统", "新型电力系统", "特高压", "智能电网"],
    "物流网": ["物流体系", "供应链", "智慧物流", "冷链物流"],
    # --- 金融/财税 ---
    "融资": ["贷款", "信贷", "债券", "股权融资", "融资担保"],
    "税收": ["税收优惠", "减免税", "退税", "税前列支", "研发加计扣除"],
    "补贴": ["补助", "资助", "扶持资金", "奖励资金", "专项资金"],
    "基金": ["产业基金", "引导基金", "创投基金", "母基金", "政府引导基金"],
    "拨改投": ["股权投资", "财政参股", "政府投资", "拨改投试点"],
    # --- 通用政策术语 ---
    "申报": ["申请", "报批", "报备", "申报材料", "申报指南"],
    "评审": ["评价", "评估", "审查", "认证", "专家评审"],
    "示范": ["试点", "标杆", "典型", "样板", "示范项目"],
    "产业链": ["供应链", "价值链", "产业集群", "产业生态", "产业链安全"],
    "高质量发展": ["转型升级", "提质增效", "结构调整", "新质生产力"],
    "新质生产力": ["创新驱动", "科技创新", "产业创新", "技术革命"],
}


def expand_synonyms(keywords: list) -> list:
    """将关键词列表通过同义词映射扩展"""
    expanded = set(keywords)
    for kw in keywords:
        if kw in SYNONYM_MAP:
            expanded.update(SYNONYM_MAP[kw])
    return list(expanded)


def _tokenize(text: str) -> set:
    """使用 jieba 分词，返回词集合"""
    if not JIEBA_AVAILABLE:
        return set(text)
    return set(jieba.cut(text))


def _fuzzy_match(keyword: str, text: str) -> bool:
    """增强匹配：子串 + 同义词 + jieba 分词交叉匹配"""
    if not text:
        return False

    # 1. 直接子串匹配（最快）
    if keyword in text:
        return True

    # 2. 同义词扩展匹配
    if keyword in SYNONYM_MAP:
        for syn in SYNONYM_MAP[keyword]:
            if syn in text:
                return True

    # 3. jieba 分词匹配：解决"智能制造示范工厂"匹配"智能工厂"等问题
    if JIEBA_AVAILABLE and len(keyword) >= 2:
        kw_tokens = set(jieba.cut(keyword))
        text_tokens = set(jieba.cut(text))
        # 如果关键词的分词结果与文本分词结果有 >= 70% 重叠，认为匹配
        if kw_tokens and len(kw_tokens & text_tokens) / len(kw_tokens) >= 0.7:
            return True

    return False


def _semantic_score(keyword: str, text: str) -> float:
    """语义相似度评分：基于分词重叠度，返回 0.0-1.0"""
    if not text or not keyword:
        return 0.0
    if keyword in text:
        return 1.0
    if not JIEBA_AVAILABLE:
        return 0.0

    kw_tokens = set(jieba.cut(keyword))
    text_tokens = set(jieba.cut(text))
    if not kw_tokens:
        return 0.0
    overlap = len(kw_tokens & text_tokens)
    return overlap / len(kw_tokens)


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
        """产业分类匹配（含同义词扩展）

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
                if _fuzzy_match(kw, title):
                    ind_matched_kw.append(kw)
                    ind_score += 4
                elif _fuzzy_match(kw, summary):
                    ind_matched_kw.append(kw)
                    ind_score += 2

            for kw in ind_info["keywords_medium"]:
                if _fuzzy_match(kw, title):
                    ind_matched_kw.append(kw)
                    ind_score += 2
                elif _fuzzy_match(kw, summary):
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
    """关键词匹配器（全局关键词 + 同义词扩展）"""

    def __init__(self, config: dict):
        keywords = config.get("global_keywords", {})
        raw_high = keywords.get("high_priority", [])
        raw_medium = keywords.get("medium_priority", [])
        raw_watch = keywords.get("watch", [])

        # 同义词扩展：每个关键词展开为包含同义词的列表
        self.high_priority = expand_synonyms(raw_high)
        self.medium_priority = expand_synonyms(raw_medium)
        self.watch = expand_synonyms(raw_watch)

        # 去重
        self.high_priority = list(dict.fromkeys(self.high_priority))
        self.medium_priority = list(dict.fromkeys(self.medium_priority))
        self.watch = list(dict.fromkeys(self.watch))

        scoring = config.get("scoring", {})
        self.p0_threshold = scoring.get("p0_threshold", 6)
        self.p1_threshold = scoring.get("p1_threshold", 3)

        logger.info(f"KeywordMatcher: high={len(self.high_priority)} medium={len(self.medium_priority)} watch={len(self.watch)} (after synonym expansion)")

    def match(self, title: str, summary: str = "", full_text: str = "") -> dict:
        """
        多字段匹配：title + summary + full_text（如果有）
        评分规则：
          - 高优词：标题命中 +6，摘要 +3，全文 +1.5
          - 中优词：标题 +2，摘要 +1，全文 +0.5
          - 观察词：任何字段命中均记录
        """
        title = clean_text(title)
        summary = clean_text(summary)
        full_text = clean_text(full_text) if full_text else ""
        # 全文取前 2000 字避免性能问题
        if len(full_text) > 2000:
            full_text = full_text[:2000]

        matched = []
        score = 0

        for kw in self.high_priority:
            if _fuzzy_match(kw, title):
                matched.append(kw)
                score += 6
            elif _fuzzy_match(kw, summary):
                matched.append(kw)
                score += 3
            elif full_text and _fuzzy_match(kw, full_text):
                matched.append(kw)
                score += 1.5

        for kw in self.medium_priority:
            if _fuzzy_match(kw, title):
                matched.append(kw)
                score += 2
            elif _fuzzy_match(kw, summary):
                matched.append(kw)
                score += 1
            elif full_text and _fuzzy_match(kw, full_text):
                matched.append(kw)
                score += 0.5

        for kw in self.watch:
            if _fuzzy_match(kw, title) or _fuzzy_match(kw, summary):
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
            "score": round(score, 1),
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
    full_text: str = "",
) -> dict:
    """组合匹配：全局关键词 + 产业分类（支持全文匹配）

    Returns:
        {
            "keywords_matched": [...],
            "global_score": float,
            "priority": "P0"/"P1"/"P2",
            "industry_matched": [...],
            "industry_score": int,
            "total_score": float,
            "final_priority": "P0"/"P1"/"P2",
        }
    """
    # 全局关键词（传入全文）
    kw_result = keyword_matcher.match(title, summary, full_text)

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
        "total_score": round(total, 1),
        "final_priority": final,
    }
