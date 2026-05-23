# -*- coding: utf-8 -*-
"""
企业级政策匹配器

基于 PolicyMatch Matrix 四维分析框架，将政策与企业画像进行深度匹配:
  Step 1: 硬性条件逐条比对（注册地/资本/行业/资质）
  Step 2: 行业框架选取（从 industries.yaml 匹配）
  Step 3: 四维评分（Tech/Prod/Mkt/Cap）
  Step 4: 推荐等级计算（5/5, 4/5, 3/5）

评分体系:
  Tech(技术端) + Prod(生产端) + Mkt(市场端) + Cap(资本端) = 总分/20
  17-20 → 5/5 首选推荐
  13-16 → 4/5 强烈推荐
   9-12 → 3/5 推荐
   5-8  → 2/5 不推荐
   1-4  → 1/5 不匹配
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("agent.matcher")


@dataclass
class MatchResult:
    """单条政策 x 单个企业的匹配结果"""
    policy_url_hash: str
    policy_title: str
    policy_url: str
    policy_source: str
    policy_date: str
    policy_summary: str
    enterprise_id: str
    enterprise_name: str

    # 硬性条件
    hard_conditions_pass: bool = False
    hard_conditions_detail: dict = field(default_factory=dict)

    # 四维评分
    score_tech: int = 0
    score_prod: int = 0
    score_mkt: int = 0
    score_cap: int = 0
    score_total: int = 0

    # 推荐等级
    recommendation: str = ""
    recommendation_score: int = 0   # 5, 4, 3, 2, 1

    # 紧迫度
    urgency: str = "P2"

    # 匹配的关键信息
    matched_keywords: list = field(default_factory=list)
    opportunities: list = field(default_factory=list)
    risks: list = field(default_factory=list)

    @property
    def matched_at(self) -> str:
        return datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "policy_url_hash": self.policy_url_hash,
            "policy_title": self.policy_title,
            "policy_url": self.policy_url,
            "policy_source": self.policy_source,
            "policy_date": self.policy_date,
            "policy_summary": self.policy_summary,
            "enterprise_id": self.enterprise_id,
            "enterprise_name": self.enterprise_name,
            "hard_conditions_pass": int(self.hard_conditions_pass),
            "hard_conditions_detail": self.hard_conditions_detail,
            "score_tech": self.score_tech,
            "score_prod": self.score_prod,
            "score_mkt": self.score_mkt,
            "score_cap": self.score_cap,
            "score_total": self.score_total,
            "recommendation": self.recommendation,
            "recommendation_score": self.recommendation_score,
            "urgency": self.urgency,
            "matched_keywords": self.matched_keywords,
            "opportunities": self.opportunities,
            "risks": self.risks,
            "matched_at": self.matched_at,
        }


# ============================================================
# 四维评分的行业关键词映射
# ============================================================

# 通用维度关键词（适用于所有行业）
UNIVERSAL_DIMENSIONS = {
    "tech": {
        "high": ["技术创新", "研发投入", "研发费用", "技术攻关", "卡脖子",
                 "自主知识产权", "核心技术", "专利", "科技成果转化"],
        "medium": ["技术改造", "设备更新", "智能制造", "数字化", "信息化",
                   "人工智能", "大数据", "云计算", "区块链"],
    },
    "prod": {
        "high": ["生产能力", "产能扩张", "生产基地", "产业化", "量产",
                 "制种基地", "生产线", "加工"],
        "medium": ["用地", "环评", "能耗", "水利", "基础设施",
                   "物流", "供应链", "安全生产"],
    },
    "mkt": {
        "high": ["市场准入", "补贴", "政府采购", "示范推广", "良种补贴",
                 "市场推广", "品牌建设", "渠道"],
        "medium": ["展会", "博览会", "行业协会", "标准制定",
                   "质量认证", "出口", "国际贸易"],
    },
    "cap": {
        "high": ["股权投资", "融资", "上市", "IPO", "北交所", "科创板",
                 "新三板", "挂牌", "股权", "拨改投"],
        "medium": ["税收优惠", "减税", "贷款贴息", "财政补贴",
                   "专项基金", "产业基金", "信用评级"],
    },
}

# 种业/农业行业特有关键词
INDUSTRY_DIMENSIONS = {
    "种业": {
        "tech": {
            "high": ["生物育种", "分子育种", "基因编辑", "种质资源",
                     "育种技术", "品种审定", "转基因", "生物技术"],
            "medium": ["品种选育", "杂交", "南繁", "育种圃",
                       "表型分析", "基因分型"],
        },
        "prod": {
            "high": ["制种基地", "种子加工", "种子生产", "种子储藏",
                     "南繁基地", "育繁推一体化"],
            "medium": ["良种繁育", "亲本繁殖", "种子检验", "种子包装",
                       "冷链仓储"],
        },
        "mkt": {
            "high": ["良种补贴", "品种推广", "示范种植", "种子市场",
                     "种业振兴", "种源安全"],
            "medium": ["经销商", "种植大户", "农户", "品种观摩会",
                       "农技推广"],
        },
        "cap": {
            "high": ["种业振兴", "南繁硅谷", "种业芯片", "种子法",
                     "品种权保护", "实质性派生品种"],
            "medium": ["种业基金", "农业保险", "制种保险",
                       "种业知识产权"],
        },
    },
}


def _hash_url(url: str) -> str:
    """生成 URL hash（与 database.py 一致）"""
    import hashlib
    cleaned = url.strip().rstrip("/")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


class EnterpriseMatcher:
    """企业级政策匹配器"""

    def __init__(self, enterprises_dir: str = None):
        self.enterprises_dir = Path(enterprises_dir)
        self.enterprises = {}
        self._load_enterprises()

    def _load_enterprises(self):
        """加载所有企业画像"""
        if not self.enterprises_dir.exists():
            logger.warning(f"企业目录不存在: {self.enterprises_dir}")
            return

        for entry in self.enterprises_dir.iterdir():
            if entry.is_dir() and entry.name != "_template":
                profile_path = entry / "profile.yaml"
                if profile_path.exists():
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            profile = yaml.safe_load(f)
                        self.enterprises[entry.name] = {
                            "id": entry.name,
                            "dir": entry,
                            "profile": profile,
                        }
                        name = profile.get("basic_info", {}).get("short_name", entry.name)
                        logger.info(f"已加载企业画像: {name} ({entry.name})")
                    except Exception as e:
                        logger.error(f"加载企业画像失败 {entry.name}: {e}")

    def get_enterprise_ids(self) -> list:
        return list(self.enterprises.keys())

    def match_policies(self, policies: list, enterprise_id: str = None) -> list:
        """将一批政策与指定企业（或所有企业）匹配

        Args:
            policies: 政策列表 (dict with title, url, summary, priority, score, etc.)
            enterprise_id: 指定企业 ID，None 表示所有企业

        Returns:
            list of MatchResult (过滤掉低分结果)
        """
        targets = []
        if enterprise_id:
            if enterprise_id in self.enterprises:
                targets.append(self.enterprises[enterprise_id])
            else:
                logger.error(f"未找到企业: {enterprise_id}")
                return []
        else:
            targets = list(self.enterprises.values())

        results = []
        for ent in targets:
            for policy in policies:
                result = self._match_single(policy, ent)
                if result and result.recommendation_score >= 3:
                    results.append(result)

        results.sort(key=lambda r: r.score_total, reverse=True)
        logger.info(f"匹配完成: {len(results)} 条有效结果 (>= 3/5)")
        return results

    def _match_single(self, policy: dict, enterprise: dict) -> Optional[MatchResult]:
        """单条政策 x 单个企业的匹配"""
        profile = enterprise["profile"]
        ent_id = enterprise["id"]
        ent_name = profile.get("basic_info", {}).get("short_name", ent_id)

        # Step 1: 硬性条件检查
        hard_pass, hard_detail = self._check_hard_conditions(policy, profile)

        # Step 2: 四维评分
        tech, prod, mkt, cap, matched_kw, opps, risks = self._score_dimensions(
            policy, profile
        )
        total = tech + prod + mkt + cap

        # Step 3: 推荐等级
        rec_score = self._calculate_recommendation(total)
        rec_text = self._recommendation_text(rec_score)

        # Step 4: 紧迫度
        urgency = policy.get("priority", "P2")

        # 硬性条件不通过时降低推荐等级
        if not hard_pass:
            rec_score = min(rec_score, 3)
            rec_text = self._recommendation_text(rec_score)

        url = policy.get("url", "")
        return MatchResult(
            policy_url_hash=_hash_url(url) if url else "",
            policy_title=policy.get("title", ""),
            policy_url=url,
            policy_source=policy.get("source", ""),
            policy_date=policy.get("date", ""),
            policy_summary=policy.get("summary", ""),
            enterprise_id=ent_id,
            enterprise_name=ent_name,
            hard_conditions_pass=hard_pass,
            hard_conditions_detail=hard_detail,
            score_tech=tech,
            score_prod=prod,
            score_mkt=mkt,
            score_cap=cap,
            score_total=total,
            recommendation=rec_text,
            recommendation_score=rec_score,
            urgency=urgency,
            matched_keywords=matched_kw,
            opportunities=opps,
            risks=risks,
        )

    def _check_hard_conditions(self, policy: dict, profile: dict) -> tuple:
        """硬性条件逐条比对

        Returns:
            (pass_bool, detail_dict)
        """
        detail = {}
        all_pass = True

        title = policy.get("title", "")
        summary = policy.get("summary", "")
        text = f"{title} {summary}"

        basic = profile.get("basic_info", {})
        industry = profile.get("industry", {})
        quals = profile.get("qualifications", {})
        regions = profile.get("regions", {})
        capital = profile.get("capital", {})

        # 条件1: 注册地检查
        registered_addr = basic.get("registered_address", "")
        region_match = self._check_region_match(text, registered_addr)
        detail["注册地"] = {"通过": region_match, "说明": registered_addr}
        if not region_match:
            # 非地域限定政策则通过
            if self._is_region_specific(text):
                all_pass = False

        # 条件2: 注册资本检查
        reg_cap = basic.get("registered_capital", 0)
        cap_requirement = self._extract_capital_requirement(text)
        detail["注册资本"] = {
            "通过": reg_cap >= cap_requirement if cap_requirement else True,
            "说明": f"要求 {cap_requirement} 万，实际 {reg_cap} 万" if cap_requirement else "无要求",
        }
        if cap_requirement and reg_cap < cap_requirement:
            all_pass = False

        # 条件3: 行业方向检查
        keywords = industry.get("industry_keywords", [])
        industry_match = any(kw in text for kw in keywords)
        detail["行业方向"] = {"通过": industry_match, "说明": f"关键词: {keywords[:3]}"}
        # 行业不匹配不一定是硬伤（通用政策也适用）

        # 条件4: 高企资质检查
        is_high_tech = quals.get("high_tech_enterprise", False)
        if "高新技术企业" in text and not is_high_tech:
            detail["高企资质"] = {"通过": False, "说明": "政策要求高企，企业不具备"}
            all_pass = False
        else:
            detail["高企资质"] = {"通过": True, "说明": "满足" if is_high_tech else "无要求"}

        return all_pass, detail

    def _is_region_specific(self, text: str) -> bool:
        """判断政策是否有地域限制"""
        region_patterns = ["湖北省", "恩施州", "武汉市", "海南省", "浙江省", "广东省",
                          "江苏省", "四川省", "重庆市", "云南省", "贵州省"]
        return any(r in text for r in region_patterns)

    def _check_region_match(self, text: str, registered_address: str) -> bool:
        """检查注册地是否匹配"""
        if not registered_address:
            return True
        # 如果政策提到该地区，或政策是全国性的
        province = registered_address[:3]  # 取省份前3字
        if province in text or "全国" in text:
            return True
        if not self._is_region_specific(text):
            return True  # 全国性政策
        return province in text

    def _extract_capital_requirement(self, text: str) -> int:
        """从政策文本中提取注册资本要求（万元）"""
        import re
        patterns = [
            r"注册资[本金].*?[不低小]?[于到至]*\s*(\d+)\s*[万元]",
            r"注册资[本金]\s*[不低小]?[于到至]*\s*(\d+)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return int(m.group(1))
        return 0

    def _score_dimensions(self, policy: dict, profile: dict) -> tuple:
        """四维评分

        Returns:
            (tech, prod, mkt, cap, matched_keywords, opportunities, risks)
        """
        title = policy.get("title", "")
        summary = policy.get("summary", "")
        text = f"{title} {summary}"

        # 确定行业维度关键词
        industry_sector = profile.get("industry", {}).get("primary_sector", "")
        industry_dims = {}
        for sector_key, dims in INDUSTRY_DIMENSIONS.items():
            if sector_key in industry_sector:
                industry_dims = dims
                break

        scores = {"tech": 0, "prod": 0, "mkt": 0, "cap": 0}
        matched_kw = []
        opportunities = []
        risks = []

        for dim in ["tech", "prod", "mkt", "cap"]:
            # 通用关键词
            universal = UNIVERSAL_DIMENSIONS.get(dim, {})
            # 行业关键词
            industry = industry_dims.get(dim, {})

            # 合并关键词
            high_kws = universal.get("high", []) + industry.get("high", [])
            medium_kws = universal.get("medium", []) + industry.get("medium", [])

            dim_score = 0
            for kw in high_kws:
                if kw in title:
                    dim_score += 5
                    matched_kw.append(kw)
                elif kw in text:
                    dim_score += 3
                    matched_kw.append(kw)

            for kw in medium_kws:
                if kw in title:
                    dim_score += 3
                    matched_kw.append(kw)
                elif kw in text:
                    dim_score += 1
                    matched_kw.append(kw)

            # 封顶 5 分
            scores[dim] = min(dim_score, 5)

            # 生成机会/风险标签
            if scores[dim] >= 4:
                dim_names = {"tech": "技术端", "prod": "生产端", "mkt": "市场端", "cap": "资本端"}
                opportunities.append(f"{dim_names[dim]}: 高度相关（{scores[dim]}/5）")
            elif scores[dim] <= 1:
                dim_names = {"tech": "技术端", "prod": "生产端", "mkt": "市场端", "cap": "资本端"}
                risks.append(f"{dim_names[dim]}: 关联度较低（{scores[dim]}/5）")

        # 去重
        matched_kw = list(dict.fromkeys(matched_kw))

        return (
            scores["tech"], scores["prod"], scores["mkt"], scores["cap"],
            matched_kw, opportunities, risks,
        )

    def _calculate_recommendation(self, total_score: int) -> int:
        """根据总分计算推荐等级（1-5）"""
        if total_score >= 17:
            return 5
        elif total_score >= 13:
            return 4
        elif total_score >= 9:
            return 3
        elif total_score >= 5:
            return 2
        else:
            return 1

    def _recommendation_text(self, score: int) -> str:
        """推荐等级文本"""
        mapping = {
            5: "5/5 首选推荐",
            4: "4/5 强烈推荐",
            3: "3/5 推荐",
            2: "2/5 不推荐",
            1: "1/5 不匹配",
        }
        return mapping.get(score, "未评估")
