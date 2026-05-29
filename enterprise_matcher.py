# -*- coding: utf-8 -*-
"""
企业级政策匹配器 (v4.0 六层评分体系)

六层评价体系:
  Layer 1: 维度评分 — Tech/Prod/Mkt/Cap 四维各 0-5 分
  Layer 2: 可调权重 — 行业默认 + 用户偏好覆盖
  Layer 3: 成功概率 — 硬性条件 + 竞争 + 窗口 + 准备度
  Layer 4: ROI 量化 — 预期收益 x 成功概率 / 投入成本
  Layer 5: 提升路径 — 差距分析 + 难度 + 时间 + 成本
  Layer 6: 人工偏好 — 必选/可选/风险/时间/地域/排除
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from policy_monitor.matcher import _fuzzy_match

logger = logging.getLogger("agent.matcher")


@dataclass
class MatchResult:
    """单条政策 x 单个企业的匹配结果 (v4.0 六层评分)"""
    policy_url_hash: str
    policy_title: str
    policy_url: str
    policy_source: str
    policy_date: str
    policy_summary: str
    enterprise_id: str
    enterprise_name: str

    # Layer 1: 维度评分
    score_tech: int = 0
    score_prod: int = 0
    score_mkt: int = 0
    score_cap: int = 0
    score_total: int = 0

    # 硬性条件
    hard_conditions_pass: bool = False
    hard_conditions_detail: dict = field(default_factory=dict)

    # Layer 2: 加权总分
    weighted_score: float = 0.0       # 加权后的 0-5 分
    weights_used: dict = field(default_factory=dict)  # 实际使用的权重

    # Layer 3: 成功概率
    success_probability: float = 0.0  # 0-1
    hard_pass_rate: str = ""          # "X/Y 通过"
    probability_factors: list = field(default_factory=list)

    # Layer 4: ROI 量化
    roi_ratio: float = 0.0
    roi_verdict: str = ""
    roi_detail: dict = field(default_factory=dict)

    # Layer 5: 提升路径
    improvement_paths: list = field(default_factory=list)

    # Layer 6: 偏好过滤
    preference_match: bool = True     # 是否通过偏好过滤
    preference_notes: list = field(default_factory=list)

    # 推荐等级（综合六层后）
    recommendation: str = ""
    recommendation_score: int = 0   # 5, 4, 3, 2, 1

    # 紧迫度
    urgency: str = "P2"

    # P0: 不推荐原因（当 recommendation_score <= 2 时自动生成）
    rejection_reasons: list = field(default_factory=list)

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
            # Layer 1
            "score_tech": self.score_tech,
            "score_prod": self.score_prod,
            "score_mkt": self.score_mkt,
            "score_cap": self.score_cap,
            "score_total": self.score_total,
            "hard_conditions_pass": int(self.hard_conditions_pass),
            "hard_conditions_detail": self.hard_conditions_detail,
            # Layer 2
            "weighted_score": round(self.weighted_score, 2),
            "weights_used": self.weights_used,
            # Layer 3
            "success_probability": round(self.success_probability, 2),
            "hard_pass_rate": self.hard_pass_rate,
            "probability_factors": self.probability_factors,
            # Layer 4
            "roi_ratio": round(self.roi_ratio, 2),
            "roi_verdict": self.roi_verdict,
            "roi_detail": self.roi_detail,
            # Layer 5
            "improvement_paths": self.improvement_paths,
            # Layer 6
            "preference_match": self.preference_match,
            "preference_notes": self.preference_notes,
            # Final
            "recommendation": self.recommendation,
            "recommendation_score": self.recommendation_score,
            "urgency": self.urgency,
            "rejection_reasons": self.rejection_reasons,
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
    # v3.0 新增：制造业/高端装备
    "制造业": {
        "tech": {
            "high": ["智能制造", "工业母机", "首台套", "首批次", "首版次",
                     "工业机器人", "数控机床", "精密仪器", "工业软件"],
            "medium": ["技改", "设备更新", "数字化改造", "机器换人",
                       "柔性制造", "精益生产"],
        },
        "prod": {
            "high": ["产能扩张", "生产线", "产业园区", "工业用地",
                     "绿色工厂", "灯塔工厂"],
            "medium": ["环评", "能耗", "安全生产", "供应链",
                       "配套产业", "产业集群"],
        },
        "mkt": {
            "high": ["政府采购", "示范工厂", "智能制造示范",
                     "专精特新", "单项冠军", "产业链链主"],
            "medium": ["行业协会", "展会", "质量认证", "出口",
                       "品牌建设"],
        },
        "cap": {
            "high": ["制造业贷款", "技改贴息", "设备更新贷款",
                     "产业基金", "专精特新", "北交所"],
            "medium": ["税收优惠", "研发加计扣除", "固定资产加速折旧",
                       "信用担保"],
        },
    },
    # v3.0 新增：数字经济/AI/平台经济
    "数字经济": {
        "tech": {
            "high": ["人工智能", "大模型", "深度学习", "机器学习",
                     "计算机视觉", "自然语言处理", "自动驾驶", "AIGC"],
            "medium": ["大数据", "云计算", "区块链", "物联网",
                       "边缘计算", "数字孪生"],
        },
        "prod": {
            "high": ["算力中心", "数据中心", "智算中心", "云平台",
                     "数据标注", "模型训练"],
            "medium": ["服务器", "GPU", "网络带宽", "存储",
                       "数据治理", "数据清洗"],
        },
        "mkt": {
            "high": ["数据要素", "数据交易", "数据资产", "数字政务",
                     "智慧城市", "工业互联网平台"],
            "medium": ["SaaS", "API", "用户规模", "平台经济",
                       "数字消费", "场景应用"],
        },
        "cap": {
            "high": ["数字经济基金", "数据资产入表", "科技金融",
                     "科创板", "数字经济", "数据资产质押"],
            "medium": ["天使投资", "风险投资", "估值", "融资",
                       "知识产权质押"],
        },
    },
    # v3.0 新增：新能源/双碳
    "新能源": {
        "tech": {
            "high": ["光伏", "风电", "氢能", "新型储能", "核能",
                     "固态电池", "液流电池", "钙钛矿", "绿氢"],
            "medium": ["清洁能源", "可再生能源", "分布式能源",
                       "微电网", "虚拟电厂"],
        },
        "prod": {
            "high": ["电站建设", "光伏组件", "风电装机", "储能电站",
                     "充换电站", "氢能站"],
            "medium": ["并网", "消纳", "电力交易", "碳交易",
                       "绿证", "碳配额"],
        },
        "mkt": {
            "high": ["碳交易", "碳市场", "绿证", "碳中和",
                     "新能源补贴", "可再生能源配额"],
            "medium": ["碳足迹", "碳核查", "ESG", "绿色认证",
                       "绿色债券"],
        },
        "cap": {
            "high": ["绿色债券", "碳减排支持工具", "新能源基金",
                     "碳金融", "绿色信贷"],
            "medium": ["绿色保险", "碳资产", "绿电交易",
                       "可再生能源补贴"],
        },
    },
    # v3.0 新增：生物医药/创新药
    "生物医药": {
        "tech": {
            "high": ["创新药", "细胞治疗", "基因治疗", "CAR-T",
                     "ADC", "双抗", "mRNA", "基因编辑", "CRO"],
            "medium": ["仿制药", "一致性评价", "生物类似药",
                       "中药现代化", "精准医疗"],
        },
        "prod": {
            "high": ["GMP", "药品生产", "CDMO", "生物制品",
                     "临床试验", "中试放大"],
            "medium": ["洁净车间", "冷链运输", "药品储藏",
                       "质量控制", "药品检验"],
        },
        "mkt": {
            "high": ["医保目录", "集中采购", "DRG", "DIP",
                     "药品审批", "MAH", "出海"],
            "medium": ["医院准入", "药店渠道", "医药代表",
                       "学术推广", "真实世界研究"],
        },
        "cap": {
            "high": ["生物医药基金", "18A", "科创板", "License-out",
                     "BD合作", "医药并购"],
            "medium": ["研发投入", "临床费用", "药品定价",
                       "专利保护", "数据独占期"],
        },
    },
    # v3.0 新增：新材料
    "新材料": {
        "tech": {
            "high": ["碳纤维", "石墨烯", "稀土材料", "半导体材料",
                     "电池材料", "高温合金", "3D打印材料", "特种玻璃"],
            "medium": ["材料基因组", "计算材料", "表征技术",
                       "工艺优化", "国产替代"],
        },
        "prod": {
            "high": ["新材料生产", "材料加工", "中试线",
                     "批量化生产", "质量一致性"],
            "medium": ["原材料供应", "设备国产化", "检测认证",
                       "标准化", "规模化"],
        },
        "mkt": {
            "high": ["首批次", "新材料保险", "国产替代",
                     "进口替代", "军民融合"],
            "medium": ["下游验证", "客户导入", "供应链安全",
                       "标准制定", "行业认证"],
        },
        "cap": {
            "high": ["新材料基金", "军民融合基金", "进口替代补贴",
                     "首台套保险补偿"],
            "medium": ["研发补贴", "产业引导基金", "材料专项",
                       "科技成果转化"],
        },
    },
    # v4.0 新增：生态环保（独立维度，覆盖环保/生态/碳/水/土）
    "生态环保": {
        "tech": {
            "high": ["环境监测", "污染源监控", "碳核算", "碳足迹",
                     "环境大数据", "智慧环保", "环境遥感"],
            "medium": ["环保设备", "污染治理技术", "清洁生产技术",
                       "资源化利用", "循环经济"],
        },
        "prod": {
            "high": ["生态修复", "污染治理", "固废处理", "污水处理",
                     "大气治理", "土壤修复", "矿山修复"],
            "medium": ["环保工程", "环保运营", "危废处置",
                       "环境工程设计", "环保设施建设"],
        },
        "mkt": {
            "high": ["碳交易", "碳市场", "排污权交易", "用能权",
                     "生态产品价值", "GEP核算", "ESG"],
            "medium": ["环保督察", "环境影响评价", "排污许可",
                       "碳配额", "绿色认证"],
        },
        "cap": {
            "high": ["环保专项", "生态补偿", "碳减排支持",
                     "绿色债券", "ESG投资", "绿色基金"],
            "medium": ["环保补贴", "清洁生产补贴", "循环经济资金",
                       "生态修复资金", "水土保持补偿费"],
        },
    },
    # v3.0 新增：煤炭/能源/矿山/工程设计
    "煤炭能源": {
        "tech": {
            "high": ["煤矿智能化", "智慧矿山", "无人开采", "安全监控",
                     "矿山数字孪生", "自动化采掘", "瓦斯治理",
                     "煤矿机器人", "矿山物联网", "5G矿山"],
            "medium": ["煤矿设计", "矿井通风", "井下定位", "远程监控",
                       "矿山信息化", "工业互联网", "矿山大数据"],
        },
        "prod": {
            "high": ["生态修复", "生态治理", "生态恢复", "矿山修复", "矿山治理",
                     "矿区治理", "塌陷区修复", "沉陷区治理",
                     "绿色矿山", "矿井水处理", "煤矸石利用"],
            "medium": ["工程设计", "工程咨询", "工程总承包", "施工图审查",
                       "项目管理", "环境影响评价", "地质灾害治理",
                       "煤炭洗选", "煤质检测"],
        },
        "mkt": {
            "high": ["煤矿安全生产", "煤炭清洁利用", "碳减排",
                     "资源综合利用", "矿山生态修复", "土壤修复",
                     "水土保持", "植被恢复", "矿山环境治理"],
            "medium": ["煤炭交易", "煤化工", "煤电联营", "矿产资源",
                       "采矿权", "探矿权", "地质勘查",
                       "煤炭质量标准", "矿山安全评价"],
        },
        "cap": {
            "high": ["能源基金", "绿色发展基金", "生态修复资金",
                     "安全生产补贴", "煤炭转型升级",
                     "矿山生态补偿", "绿色债券",
                     "煤矿安全改造", "矿产资源法"],
            "medium": ["技改贴息", "设备更新贷款", "产业引导基金",
                       "科技创新补贴", "环保专项资金",
                       "矿山恢复治理基金", "土地复垦费"],
        },
    },
    # v3.0 新增：轻资产/平台型（适用于数字经济、咨询服务、SaaS等）
    "轻资产": {
        "tech": {
            "high": ["软件著作权", "算法", "模型", "平台架构",
                     "SaaS", "PaaS", "低代码", "开源"],
            "medium": ["技术团队", "研发投入占比", "知识产权",
                       "技术壁垒", "专利布局"],
        },
        "prod": {
            "high": ["用户规模", "月活", "日活", "GMV",
                     "API调用量", "数据资产", "平台交易额"],
            "medium": ["服务器", "带宽", "云服务", "运维",
                       "SLA", "可用性"],
        },
        "mkt": {
            "high": ["平台经济", "网络效应", "用户增长",
                     "获客成本", "市场份额", "生态建设"],
            "medium": ["转化率", "留存率", "客单价", "复购率",
                       "品牌影响力"],
        },
        "cap": {
            "high": ["估值", "融资轮次", "Pre-IPO", "科创板",
                     "数据资产入表", "知识产权质押"],
            "medium": ["天使轮", "A轮", "B轮", "风险投资",
                       "营收增长", "盈利模型"],
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
        """加载所有企业画像 + 偏好配置"""
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

                        # v4.0: 加载偏好配置
                        prefs = {}
                        prefs_path = entry / "preferences.yaml"
                        if prefs_path.exists():
                            with open(prefs_path, "r", encoding="utf-8") as f:
                                prefs = yaml.safe_load(f) or {}
                            logger.info(f"已加载企业偏好: {entry.name}")

                        self.enterprises[entry.name] = {
                            "id": entry.name,
                            "dir": entry,
                            "profile": profile,
                            "preferences": prefs,
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
        """单条政策 x 单个企业的匹配 (v4.0 六层评分)"""
        profile = enterprise["profile"]
        prefs = enterprise.get("preferences", {})
        ent_id = enterprise["id"]
        ent_name = profile.get("basic_info", {}).get("short_name", ent_id)

        url = policy.get("url", "")
        result = MatchResult(
            policy_url_hash=_hash_url(url) if url else "",
            policy_title=policy.get("title", ""),
            policy_url=url,
            policy_source=policy.get("source", ""),
            policy_date=policy.get("date", ""),
            policy_summary=policy.get("summary", ""),
            enterprise_id=ent_id,
            enterprise_name=ent_name,
            urgency=policy.get("priority", "P2"),
        )

        # Layer 1: 维度评分
        tech, prod, mkt, cap, matched_kw, opps, risks = self._score_dimensions(policy, profile)
        result.score_tech = tech
        result.score_prod = prod
        result.score_mkt = mkt
        result.score_cap = cap
        result.score_total = tech + prod + mkt + cap
        result.matched_keywords = matched_kw
        result.opportunities = opps
        result.risks = risks

        # 硬性条件检查
        hard_pass, hard_detail = self._check_hard_conditions(policy, profile)
        result.hard_conditions_pass = hard_pass
        result.hard_conditions_detail = hard_detail

        # Layer 2: 可调权重
        weights = self._get_weights(prefs, profile)
        result.weights_used = weights
        result.weighted_score = self._calculate_weighted_score(
            tech, prod, mkt, cap, weights
        )

        # P1: 快速淘汰 — 四维全零时跳过 L3-L6，直接给出不匹配结论
        if tech == 0 and prod == 0 and mkt == 0 and cap == 0:
            result.recommendation_score = 1
            result.recommendation = "1/5 不匹配"
            result.rejection_reasons = self._generate_rejection_reasons(result, policy, enterprise)
            return result

        # Layer 3: 成功概率
        prob, factors, pass_rate = self._estimate_success_probability(
            hard_pass, hard_detail, result.weighted_score, policy, profile
        )
        result.success_probability = prob
        result.probability_factors = factors
        result.hard_pass_rate = pass_rate

        # Layer 4: ROI 量化
        roi_ratio, roi_verdict, roi_detail = self._calculate_roi(
            policy, profile, prob
        )
        result.roi_ratio = roi_ratio
        result.roi_verdict = roi_verdict
        result.roi_detail = roi_detail

        # Layer 5: 提升路径
        result.improvement_paths = self._generate_improvement_paths(
            tech, prod, mkt, cap, weights, hard_detail
        )

        # Layer 6: 偏好过滤
        pref_match, pref_notes = self._check_preferences(policy, prefs, result)
        result.preference_match = pref_match
        result.preference_notes = pref_notes

        # 综合推荐等级（基于加权分 + 硬性条件 + 偏好）
        rec_score = self._calculate_recommendation_from_weighted(
            result.weighted_score, hard_pass, pref_match
        )
        result.recommendation_score = rec_score
        result.recommendation = self._recommendation_text(rec_score)

        # P0: 不推荐原因生成
        if result.recommendation_score <= 2:
            result.rejection_reasons = self._generate_rejection_reasons(result, policy, enterprise)

        # 偏好过滤：不匹配的降级
        if not pref_match:
            result.recommendation_score = min(result.recommendation_score, 2)
            result.recommendation = self._recommendation_text(result.recommendation_score)

        return result

    def _check_hard_conditions(self, policy: dict, profile: dict) -> tuple:
        """硬性条件逐条比对

        v3.0: 适配轻资产企业，跳过生产相关检查，降低注册资本门槛

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
        biz_model = profile.get("business_model", {})

        # v3.0: 判断是否为轻资产企业（排除有实体基地/重资产的服务型企业）
        has_base = biz_model.get("has_production_base", True)
        model_type = biz_model.get("model_type", "")
        is_asset_light = (
            model_type in ("平台型", "SaaS", "咨询", "轻资产")
            or (model_type == "服务型" and not has_base)
        )

        # 条件1: 注册地检查
        registered_addr = basic.get("registered_address", "")
        region_match = self._check_region_match(text, registered_addr)
        detail["注册地"] = {"通过": region_match, "说明": registered_addr}
        if not region_match:
            # 非地域限定政策则通过
            if self._is_region_specific(text):
                all_pass = False

        # 条件2: 注册资本检查
        # v3.0: 轻资产企业可能注册资本较低，对注册资本门槛政策降低权重
        reg_cap = basic.get("registered_capital", 0)
        cap_requirement = self._extract_capital_requirement(text)
        if is_asset_light and cap_requirement:
            # 轻资产企业：注册资本不足不视为硬伤，但降低推荐分数
            cap_pass = True  # 不作为硬性淘汰条件
            detail["注册资本"] = {
                "通过": True,
                "说明": f"要求 {cap_requirement} 万，实际 {reg_cap} 万（轻资产企业，已放宽）",
            }
        else:
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

        # v3.0 条件5: 生产资质检查（仅对重资产企业）
        if not is_asset_light:
            has_production = biz_model.get("has_production_base", True)
            if "生产基地" in text and not has_production:
                detail["生产能力"] = {"通过": False, "说明": "政策要求生产基地，企业不具备"}
                # 不作为硬伤，但记录
            else:
                detail["生产能力"] = {"通过": True, "说明": "满足"}

        return all_pass, detail

    def _is_region_specific(self, text: str) -> bool:
        """判断政策是否有地域限制"""
        region_patterns = [
            "北京市", "天津市", "上海市", "重庆市",
            "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
            "江苏省", "浙江省", "安徽省", "福建省", "江西省",
            "山东省", "河南省", "湖北省", "湖南省", "广东省",
            "海南省", "四川省", "贵州省", "云南省", "陕西省",
            "甘肃省", "青海省", "台湾省",
            "内蒙古自治区", "广西壮族自治区", "西藏自治区",
            "宁夏回族自治区", "新疆维吾尔自治区",
            # 主要城市
            "武汉市", "恩施州", "宜昌市", "襄阳市",
            "深圳市", "广州市", "杭州市", "南京市", "成都市",
            "西安市", "苏州市", "青岛市", "大连市", "厦门市",
        ]
        return any(r in text for r in region_patterns)

    def _check_region_match(self, text: str, registered_address: str) -> bool:
        """检查注册地是否匹配"""
        if not registered_address:
            return True
        # 政策是全国性的则通过
        if "全国" in text:
            return True
        if not self._is_region_specific(text):
            return True  # 全国性政策
        # 尝试匹配省份名（支持 2-6 字的省名，如"湖北""内蒙古""黑龙江"）
        province_prefixes = [
            "内蒙古自治区", "广西壮族自治区", "西藏自治区",
            "宁夏回族自治区", "新疆维吾尔自治区",
            "北京市", "天津市", "上海市", "重庆市",
            "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
            "江苏省", "浙江省", "安徽省", "福建省", "江西省",
            "山东省", "河南省", "湖北省", "湖南省", "广东省",
            "海南省", "四川省", "贵州省", "云南省", "陕西省",
            "甘肃省", "青海省", "台湾省",
        ]
        for prefix in province_prefixes:
            if registered_address.startswith(prefix):
                return prefix in text
        # 通用匹配：检查地址中的任何连续 2+ 字是否出现在政策文本中
        for length in range(min(6, len(registered_address)), 1, -1):
            candidate = registered_address[:length]
            if len(candidate) >= 2 and candidate in text:
                return True
        return False

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
        business_model = profile.get("business_model", {}).get("model_type", "")

        # v4.0 改进：支持模糊匹配 + 商业模式自动识别 + 9 个行业维度
        industry_dims = {}

        # 先检查是否为轻资产企业（排除有实体基地/重资产的服务型企业）
        has_base = profile.get("business_model", {}).get("has_production_base", True)
        is_truly_asset_light = (
            business_model in ("平台型", "SaaS", "咨询", "轻资产")
            or (business_model == "服务型" and not has_base)
        )
        if is_truly_asset_light:
            industry_dims = INDUSTRY_DIMENSIONS.get("轻资产", {})
        else:
            # 行业关键词模糊匹配（支持多个关键词命中）
            for sector_key, dims in INDUSTRY_DIMENSIONS.items():
                if sector_key == "轻资产":
                    continue
                # 支持多关键词匹配
                sector_keywords = [sector_key]
                if sector_key == "制造业":
                    sector_keywords.extend(["制造", "装备", "机械", "工厂", "工业", "生产"])
                elif sector_key == "数字经济":
                    sector_keywords.extend(["数字", "软件", "信息", "AI", "数据", "智能",
                                           "计算", "网络", "通信", "互联网"])
                elif sector_key == "新能源":
                    sector_keywords.extend(["光伏", "储能", "氢能", "风电", "碳", "清洁能源",
                                           "可再生能源", "电力", "核能", "生物质"])
                elif sector_key == "生物医药":
                    sector_keywords.extend(["医药", "制药", "生物", "医疗", "药", "健康",
                                           "诊断", "疫苗", "基因"])
                elif sector_key == "新材料":
                    sector_keywords.extend(["材料", "纤维", "合金", "复合材料", "陶瓷",
                                           "稀土", "高分子", "半导体材料"])
                elif sector_key == "种业":
                    sector_keywords.extend(["种业", "农业", "育种", "种子", "品种", "种植",
                                           "农学", "杂交", "粮食", "畜牧", "水产", "农机"])
                elif sector_key == "煤炭能源":
                    sector_keywords.extend(["煤", "矿", "能源", "工程设计", "工程咨询",
                                           "生态修复", "生态治理", "地质", "测绘",
                                           "矿山", "采掘", "石油", "天然气"])
                elif sector_key == "生态环保":
                    sector_keywords.extend(["环保", "生态", "环境", "污染", "碳", "水",
                                           "大气", "固废", "土壤", "修复", "治理"])

                if any(kw in industry_sector for kw in sector_keywords):
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
                if _fuzzy_match(kw, title):
                    dim_score += 5
                    matched_kw.append(kw)
                elif _fuzzy_match(kw, text):
                    dim_score += 3
                    matched_kw.append(kw)

            for kw in medium_kws:
                if _fuzzy_match(kw, title):
                    dim_score += 3
                    matched_kw.append(kw)
                elif _fuzzy_match(kw, text):
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

    def _generate_rejection_reasons(self, result: MatchResult, policy: dict, enterprise: dict) -> list:
        """当匹配度 <= 2/5 时，自动生成不推荐的具体原因

        P0 改进：从"不推荐"变为"为什么不推荐 + 什么企业才适合"
        """
        reasons = []
        profile = enterprise.get("profile", enterprise)
        industry = profile.get("industry", {})
        primary_sector = industry.get("primary_sector", "")
        quals = profile.get("qualifications", {})
        basic = profile.get("basic_info", {})

        # 1. 行业不匹配
        if result.score_total <= 4:
            reasons.append({
                "type": "行业不匹配",
                "detail": f"企业主业为「{primary_sector}」，该政策面向的行业领域与企业核心业务不直接相关",
                "suggestion": "此政策更适合对应行业的企业",
            })

        # 2. 硬性条件不通过
        if not result.hard_conditions_pass:
            failed = [k for k, v in result.hard_conditions_detail.items() if not v.get("通过", False)]
            if failed:
                reasons.append({
                    "type": "硬性条件不满足",
                    "detail": f"未满足：{', '.join(failed)}",
                    "suggestion": "需要先补齐相关资质或条件",
                })

        # 3. 各维度均为零分
        if result.score_tech == 0 and result.score_prod == 0 and result.score_mkt == 0 and result.score_cap == 0:
            reasons.append({
                "type": "全面无匹配",
                "detail": "政策文本中的关键词与企业画像在技术/生产/市场/资本四个维度均无交集",
                "suggestion": "企业与该政策方向存在本质差异，不建议投入资源申报",
            })
        else:
            # 4. 部分维度有分但太低
            zero_dims = []
            dim_names = {"tech": "技术端", "prod": "生产端", "mkt": "市场端", "cap": "资本端"}
            dim_scores = {"tech": result.score_tech, "prod": result.score_prod,
                         "mkt": result.score_mkt, "cap": result.score_cap}
            for dim, name in dim_names.items():
                if dim_scores[dim] == 0:
                    zero_dims.append(name)
            if zero_dims:
                reasons.append({
                    "type": "关键维度缺失",
                    "detail": f"{'、'.join(zero_dims)}与政策方向无关联",
                    "suggestion": "如需申报，需在这些维度补充实质性能力",
                })

        return reasons

    # ============================================================
    # Layer 2: 可调权重
    # ============================================================

    # 行业默认权重
    INDUSTRY_WEIGHTS = {
        "种业": {"tech": 0.25, "prod": 0.30, "mkt": 0.25, "cap": 0.20},
        "制造业": {"tech": 0.20, "prod": 0.35, "mkt": 0.25, "cap": 0.20},
        "数字经济": {"tech": 0.35, "prod": 0.10, "mkt": 0.25, "cap": 0.30},
        "新能源": {"tech": 0.25, "prod": 0.25, "mkt": 0.25, "cap": 0.25},
        "生物医药": {"tech": 0.30, "prod": 0.15, "mkt": 0.25, "cap": 0.30},
        "新材料": {"tech": 0.30, "prod": 0.25, "mkt": 0.25, "cap": 0.20},
        "煤炭能源": {"tech": 0.25, "prod": 0.30, "mkt": 0.25, "cap": 0.20},
        "轻资产": {"tech": 0.30, "prod": 0.10, "mkt": 0.30, "cap": 0.30},
        "通用": {"tech": 0.25, "prod": 0.25, "mkt": 0.25, "cap": 0.25},
    }

    def _get_weights(self, prefs: dict, profile: dict) -> dict:
        """获取最终权重：用户偏好 > 行业默认 > 通用默认"""
        # 1. 用户偏好覆盖
        user_weights = prefs.get("weights", {})
        if user_weights and all(k in user_weights for k in ["tech", "prod", "mkt", "cap"]):
            total = sum(user_weights.values())
            if total > 0:
                return {k: v / total for k, v in user_weights.items()}

        # 2. 行业默认
        sector = profile.get("industry", {}).get("primary_sector", "")
        for industry_key, industry_weights in self.INDUSTRY_WEIGHTS.items():
            if industry_key in sector or sector in industry_key:
                return industry_weights.copy()

        # 3. 通用默认
        return self.INDUSTRY_WEIGHTS["通用"].copy()

    def _calculate_weighted_score(self, tech, prod, mkt, cap, weights) -> float:
        """计算加权总分（0-5 分制）"""
        raw = (tech * weights["tech"] + prod * weights["prod"]
               + mkt * weights["mkt"] + cap * weights["cap"])
        return round(raw, 2)

    # ============================================================
    # Layer 3: 成功概率
    # ============================================================

    def _estimate_success_probability(self, hard_pass, hard_detail, weighted_score, policy, profile):
        """估算成功概率（v4.0 动态化）

        改进点:
          - 企业资质评估从固定3项扩展为8项（含专利数/团队规模/成立年限等）
          - 竞争度从固定值改为动态估算（根据政策级别+行业热度）
          - 评分上限从62%提升到95%
          - 每项因素的贡献更合理
        """
        factors = []

        # 因素1: 硬性条件通过率（权重 30%）
        total_conditions = len(hard_detail) if hard_detail else 1
        passed_conditions = sum(1 for v in hard_detail.values() if v.get("通过", False))
        hard_rate = passed_conditions / total_conditions if total_conditions > 0 else 0
        factors.append(f"硬性条件: {passed_conditions}/{total_conditions} 通过 ({hard_rate:.0%})")

        # 因素2: 匹配分数（权重 25%）
        score_factor = min(1.0, weighted_score / 4.0)
        factors.append(f"匹配分数: {weighted_score:.1f}/5 (权重因子: {score_factor:.0%})")

        # 因素3: 企业资质储备（权重 25%）— v4.0 扩展为 8 项评估
        quals = profile.get("qualifications", {})
        basic = profile.get("basic_info", {})
        innovation = profile.get("innovation", {})
        qual_score = 0

        # 基础资质
        if quals.get("high_tech_enterprise"):
            qual_score += 0.08
            factors.append("高企认定: +8%")
        if quals.get("specialized_new"):
            qual_score += 0.08
            factors.append("专精特新: +8%")
        if quals.get("listed"):
            qual_score += 0.05
            factors.append("已挂牌/上市: +5%")

        # 知识产权（v4.0 新增）
        # 兼容两种格式：嵌套 dict {invention: N} 或模板扁平字段 invention_patents
        patents = innovation.get("patents", {})
        if isinstance(patents, dict):
            invention = patents.get("invention", 0)
            utility = patents.get("utility_model", 0)
            total_patents = invention + utility
        elif isinstance(patents, int):
            total_patents = patents
        else:
            # 兼容模板扁平字段格式
            invention = innovation.get("invention_patents", 0)
            utility = innovation.get("utility_patents", 0)
            sw_copyrights = innovation.get("software_copyrights", 0)
            total_patents = invention + utility + sw_copyrights

        if total_patents >= 10:
            qual_score += 0.06
            factors.append(f"知识产权({total_patents}项): +6%")
        elif total_patents >= 3:
            qual_score += 0.04
            factors.append(f"知识产权({total_patents}项): +4%")
        elif total_patents >= 1:
            qual_score += 0.02
            factors.append(f"知识产权({total_patents}项): +2%")

        # 团队规模（v4.0 新增）
        employees = basic.get("employee_count", 0)
        if employees >= 200:
            qual_score += 0.03
            factors.append(f"团队规模({employees}人): +3%")
        elif employees >= 50:
            qual_score += 0.02
            factors.append(f"团队规模({employees}人): +2%")

        # 成立年限（v4.0 新增）
        # 兼容两种格式：整数 founded_year 或日期字符串 establishment_date
        founded = basic.get("founded_year", 0)
        if not founded:
            est_date = basic.get("establishment_date", "")
            if est_date and len(str(est_date)) >= 4:
                try:
                    founded = int(str(est_date)[:4])
                except (ValueError, TypeError):
                    founded = 0
        if founded > 0:
            years = 2026 - founded
            if years >= 5:
                qual_score += 0.03
                factors.append(f"成立{years}年: +3%")
            elif years >= 3:
                qual_score += 0.02
                factors.append(f"成立{years}年: +2%")

        qual_score = min(0.30, qual_score)  # 上限 30%

        # 因素4: 竞争度估算（权重 20%）— v4.0 动态化
        title = policy.get("title", "")
        competition_factor = 1.0

        # 政策级别
        if "国家重点" in title or "国家级" in title or "国务院" in title:
            competition_factor *= 0.75
            factors.append("国家级政策: 竞争度高 (-25%)")
        elif "省级" in title or "省厅" in title:
            competition_factor *= 0.85
            factors.append("省级政策: 竞争度中 (-15%)")
        elif "市级" in title or "州级" in title:
            competition_factor *= 0.92
            factors.append("市州级政策: 竞争度低 (-8%)")
        else:
            competition_factor *= 0.90
            factors.append("政策级别: 一般竞争度 (-10%)")

        # 政策热度（根据关键词判断是否为热门领域）
        hot_keywords = ["人工智能", "芯片", "集成电路", "新能源", "生物医药",
                       "量子", "低空经济", "储能", "氢能", "数据要素"]
        hot_count = sum(1 for kw in hot_keywords if kw in title)
        if hot_count >= 2:
            competition_factor *= 0.85
            factors.append("热门领域: 竞争度额外增加 (-15%)")
        elif hot_count == 1:
            competition_factor *= 0.92
            factors.append("较热门领域: 竞争度略增 (-8%)")

        # 综合概率（v4.0: 权重调整，上限提升到 95%）
        base_probability = 0.35  # 基准 35%（降低基准，让企业资质发挥更大作用）
        probability = (
            base_probability * 0.25           # 基准
            + hard_rate * 0.30                # 硬性条件
            + score_factor * 0.25             # 匹配分数
            + qual_score * 0.20               # 企业资质（权重提升）
        ) * competition_factor

        # 限制范围
        probability = max(0.05, min(0.95, probability))

        return round(probability, 2), factors, f"{passed_conditions}/{total_conditions}"

    # ============================================================
    # Layer 4: ROI 量化 (集成 roi_calculator.py)
    # ============================================================

    def _calculate_roi(self, policy, profile, success_probability):
        """计算 ROI"""
        try:
            from roi_calculator import ROICalculator, format_roi_report

            industry = profile.get("industry", {}).get("primary_sector", "通用")
            calc = ROICalculator(industry=industry)
            financials = calc.estimate_financials(policy, profile)
            result = calc.calculate(financials, success_probability)

            return result.roi_ratio, result.verdict, result.to_dict()
        except Exception as e:
            logger.warning(f"ROI 计算失败: {e}")
            return 0.0, "ROI 计算不可用", {}

    # ============================================================
    # Layer 5: 提升路径
    # ============================================================

    def _generate_improvement_paths(self, tech, prod, mkt, cap, weights, hard_detail):
        """根据差距分析生成提升路径"""
        paths = []
        dim_names = {"tech": "技术端", "prod": "生产端", "mkt": "市场端", "cap": "资本端"}
        dim_scores = {"tech": tech, "prod": prod, "mkt": mkt, "cap": cap}

        # 按差距从大到小排序（5 - 当前分）
        gaps = sorted(dim_scores.items(), key=lambda x: 5 - x[1], reverse=True)

        for dim, score in gaps:
            if score >= 4:
                continue  # 已经很好，不需要提升
            gap = 5 - score
            weight = weights.get(dim, 0.25)
            importance = weight * 5  # 权重越大越重要

            # 生成具体建议
            suggestions = self._get_dim_suggestions(dim, score)

            difficulty = "容易" if gap <= 1 else "中等" if gap <= 2 else "困难"
            time_est = f"{gap * 2}个月" if gap <= 2 else f"{gap * 3}个月"

            paths.append({
                "dimension": dim_names[dim],
                "current_score": f"{score}/5",
                "gap": gap,
                "importance": f"{importance:.1f}",
                "difficulty": difficulty,
                "estimated_time": time_est,
                "suggestions": suggestions,
            })

        return paths

    def _get_dim_suggestions(self, dim: str, score: int) -> list:
        """根据维度和当前分数生成具体建议"""
        suggestions_map = {
            "tech": {
                0: ["加强技术研发投入", "引进高层次技术人才", "建立产学研合作"],
                1: ["申报科技计划项目", "申请专利/软著", "参加技术标准制定"],
                2: ["申报高新技术企业认定", "建立研发机构", "加大研发投入占比"],
                3: ["冲刺省级科技奖", "参与国家重点研发", "建设省级以上创新平台"],
            },
            "prod": {
                0: ["建设或租赁生产基地", "取得生产许可证", "建立质量管理体系"],
                1: ["扩大产能规模", "获取ISO认证", "建设标准化产线"],
                2: ["申请绿色工厂/灯塔工厂", "提升自动化水平", "完善供应链"],
                3: ["建设智能工厂", "申报产能示范项目", "拓展产能覆盖区域"],
            },
            "mkt": {
                0: ["建立销售渠道", "参加行业展会", "申请产品认证"],
                1: ["拓展区域市场", "建立品牌体系", "争取政府采购资质"],
                2: ["进入行业目录/名录", "申报示范项目", "建立战略客户关系"],
                3: ["争创行业标杆/单项冠军", "拓展国际市场", "建设行业生态"],
            },
            "cap": {
                0: ["规范财务管理", "建立融资渠道", "申请基础性补贴"],
                1: ["引入天使/VC投资", "申请高企税收优惠", "建立信用评级"],
                2: ["冲刺区域股权市场挂牌", "申请产业基金", "建立投资者关系"],
                3: ["准备北交所/科创板IPO", "引入战略投资者", "设计股权激励"],
            },
        }
        dim_map = suggestions_map.get(dim, {})
        return dim_map.get(score, dim_map.get(0, ["待补充具体建议"]))

    # ============================================================
    # Layer 6: 人工偏好过滤
    # ============================================================

    def _check_preferences(self, policy, prefs, result):
        """检查偏好过滤条件

        Returns:
            (pass_bool, notes_list)
        """
        if not prefs:
            return True, []

        notes = []
        text = f"{policy.get('title', '')} {policy.get('summary', '')}"

        # 必选条件
        must_haves = prefs.get("must_have", [])
        for condition in must_haves:
            if condition not in text:
                notes.append(f"未满足必选: {condition}")
                return False, notes

        # 排除条件
        excludes = prefs.get("exclude", [])
        for exc in excludes:
            if exc in text:
                notes.append(f"命中排除条件: {exc}")
                return False, notes

        # 可选加分
        nice_to_haves = prefs.get("nice_to_have", [])
        nice_count = sum(1 for n in nice_to_haves if n in text)
        if nice_count > 0:
            notes.append(f"命中加分项: {nice_count}/{len(nice_to_haves)}")

        # ROI 阈值
        min_roi = prefs.get("min_roi_ratio", 0)
        if min_roi > 0 and result.roi_ratio < min_roi:
            notes.append(f"ROI {result.roi_ratio:.1f}x 低于阈值 {min_roi}x")
            return False, notes

        return True, notes

    def _calculate_recommendation_from_weighted(self, weighted_score, hard_pass, pref_match):
        """基于加权分数计算推荐等级"""
        if not hard_pass:
            weighted_score = min(weighted_score, 3.0)
        if not pref_match:
            weighted_score = min(weighted_score, 2.0)

        if weighted_score >= 4.0:
            return 5
        elif weighted_score >= 3.0:
            return 4
        elif weighted_score >= 2.0:
            return 3
        elif weighted_score >= 1.0:
            return 2
        else:
            return 1
