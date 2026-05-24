# -*- coding: utf-8 -*-
"""
ROI 量化评估模块 v2.0

计算政策申报的投入产出比，为决策提供量化依据。

v2.0 改进:
  - 政策类型自动分类（拨改投/专项补贴/税收优惠/资质认定/项目审批）
  - 按类型自动匹配财务模型（不再依赖正则提取金额）
  - 收益模型扩展（资金+税收+品牌+市场+乘数效应）
  - 行业基准线对比（ROI 评级从"绝对值"改为"相对行业排名"）
  - 成本模型细化（申报+合规+机会成本+时间折现）

评估维度:
  Layer 4: ROI 量化
    - 预期收益估算（政策资金 + 税收优惠 + 品牌价值 + 市场准入 + 乘数效应）
    - 投入成本估算（申报成本 + 合规成本 + 机会成本）
    - 风险调整后收益 = 预期收益 x 成功概率
    - ROI = 风险调整后收益 / 总投入成本
    - 行业基准对比（优于/持平/低于行业平均）
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("agent.roi")


# ============================================================
# 政策类型分类器
# ============================================================

POLICY_TYPE_KEYWORDS = {
    "拨改投": ["拨改投", "股权投资", "政府参股", "增资扩股", "受托管理"],
    "专项补贴": ["专项资金", "补贴", "资助", "奖补", "扶持资金", "补助",
                   "专项资金支持", "财政补贴", "资金支持", "无偿资助"],
    "税收优惠": ["税收", "减税", "免税", "税率", "加计扣除", "研发费用",
                   "增值税", "所得税", "退税", "税收减免"],
    "资质认定": ["认定", "评审", "认证", "资质", "高企", "专精特新",
                   "企业认定", "实验室认定", "平台认定"],
    "项目审批": ["审批", "核准", "备案", "立项", "可行性研究", "项目评估"],
    "基金/投融资": ["基金", "投融资", "融资", "贷款贴息", "信贷",
                     "债券", "担保", "保险补偿"],
}


def classify_policy_type(title: str, summary: str = "") -> str:
    """根据标题和摘要自动分类政策类型

    Returns:
        政策类型字符串（拨改投/专项补贴/税收优惠/资质认定/项目审批/基金投融资/其他）
    """
    text = f"{title} {summary}"
    scores = {}
    for ptype, keywords in POLICY_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[ptype] = score

    if not scores:
        return "其他"

    return max(scores, key=scores.get)


# ============================================================
# 政策类型财务参数模板
# ============================================================

# 每种政策类型的典型财务参数（万元），按企业规模分级
POLICY_FINANCIAL_MODELS = {
    "拨改投": {
        # 拨改投: 政府以增资扩股方式投入，持股<=30%
        "funding_range": (300, 3000),        # 政府投资额范围
        "funding_duration_years": 3,          # 资金持续年限（运营期）
        "equity_dilution_range": (10, 30),    # 股权稀释比例范围 (%)
        "self_fund_ratio": 0.7,              # 企业自筹比例
        "application_cost": 30,               # 申报成本（可研+审计+律师+材料）
        "compliance_cost_annual": 15,         # 年合规成本（审计+信披+董事会）
        "compliance_years": 5,                # 合规期（投资+退出期）
        "application_months": 6,              # 申报周期
        "brand_value": 100,                   # 品牌/资质价值
        "market_value": 50,                   # 市场价值
        "indirect_benefits": {
            "policy_network": 80,             # 政策关系网络价值
            "talent_attraction": 30,          # 人才吸引力提升
            "follow_up_funding": 150,         # 后续跟投/贷款可能性
        },
    },
    "专项补贴": {
        # 专项补贴: 无偿拨款，金额相对较小
        "funding_range": (50, 500),
        "funding_duration_years": 1,
        "equity_dilution_range": (0, 0),
        "self_fund_ratio": 0,
        "application_cost": 15,               # 可研5+审计3+人工3+材料4
        "compliance_cost_annual": 3,
        "compliance_years": 2,
        "application_months": 3,
        "brand_value": 30,
        "market_value": 20,
        "indirect_benefits": {
            "policy_network": 20,
            "talent_attraction": 10,
            "follow_up_funding": 50,
        },
    },
    "税收优惠": {
        # 税收优惠: 持续性收益，取决于企业营收规模
        "funding_range": (0, 0),              # 无直接资金
        "funding_duration_years": 5,          # 通常持续3-5年
        "equity_dilution_range": (0, 0),
        "self_fund_ratio": 0,
        "application_cost": 5,                # 资质维护成本
        "compliance_cost_annual": 2,
        "compliance_years": 5,
        "application_months": 1,
        "brand_value": 20,
        "market_value": 0,
        "indirect_benefits": {
            "policy_network": 10,
            "talent_attraction": 5,
            "follow_up_funding": 0,
        },
    },
    "资质认定": {
        # 资质认定: 间接收益为主（品牌+准入+后续政策资格）
        "funding_range": (0, 100),            # 部分认定有配套奖励
        "funding_duration_years": 3,
        "equity_dilution_range": (0, 0),
        "self_fund_ratio": 0,
        "application_cost": 20,               # 申报材料+审计+答辩
        "compliance_cost_annual": 5,
        "compliance_years": 3,
        "application_months": 4,
        "brand_value": 80,                    # 资质本身的背书价值
        "market_value": 40,                   # 进入某些市场的准入门槛
        "indirect_benefits": {
            "policy_network": 30,
            "talent_attraction": 20,
            "follow_up_funding": 80,          # 有了资质才能申请后续政策
        },
    },
    "项目审批": {
        "funding_range": (0, 0),
        "funding_duration_years": 1,
        "equity_dilution_range": (0, 0),
        "self_fund_ratio": 1.0,              # 企业全额投资
        "application_cost": 25,               # 可研报告+环评+审批材料
        "compliance_cost_annual": 10,
        "compliance_years": 3,
        "application_months": 6,
        "brand_value": 10,
        "market_value": 30,                   # 获得建设/运营资格
        "indirect_benefits": {
            "policy_network": 15,
            "talent_attraction": 5,
            "follow_up_funding": 0,
        },
    },
    "基金/投融资": {
        "funding_range": (100, 2000),
        "funding_duration_years": 3,
        "equity_dilution_range": (5, 20),
        "self_fund_ratio": 0.5,
        "application_cost": 20,
        "compliance_cost_annual": 10,
        "compliance_years": 3,
        "application_months": 4,
        "brand_value": 50,
        "market_value": 30,
        "indirect_benefits": {
            "policy_network": 40,
            "talent_attraction": 15,
            "follow_up_funding": 100,
        },
    },
    "其他": {
        "funding_range": (20, 200),
        "funding_duration_years": 1,
        "equity_dilution_range": (0, 0),
        "self_fund_ratio": 0,
        "application_cost": 15,
        "compliance_cost_annual": 5,
        "compliance_years": 2,
        "application_months": 3,
        "brand_value": 20,
        "market_value": 10,
        "indirect_benefits": {
            "policy_network": 10,
            "talent_attraction": 5,
            "follow_up_funding": 20,
        },
    },
}

# 企业规模系数（根据注册资本调整资金规模）
SCALE_FACTORS = {
    "small": {       # < 1000 万
        "funding_multiplier": 0.5,
        "cost_multiplier": 0.7,
        "label": "小型企业",
    },
    "medium": {      # 1000-5000 万
        "funding_multiplier": 1.0,
        "cost_multiplier": 1.0,
        "label": "中型企业",
    },
    "large": {       # 5000 万 - 5 亿
        "funding_multiplier": 1.5,
        "cost_multiplier": 1.3,
        "label": "大型企业",
    },
    "xlarge": {      # > 5 亿
        "funding_multiplier": 2.0,
        "cost_multiplier": 1.5,
        "label": "特大型企业",
    },
}

# 行业 ROI 基准线 v3.0
# 覆盖 industries.yaml 全部五大产业分类 + 43 个子行业
# 新增字段: investment_level(资本密集度), subsidy_density(政策密度), risk_factor(风险因子)
# risk_factor: tech(技术风险) / market(市场风险) / policy(政策依赖) / combo(综合)

INDUSTRY_BENCHMARKS = {
    # ====================================================
    # 一、战略性新兴产业（9 个子行业 + 6 个新兴支柱）
    # ====================================================
    # --- 1. 新一代信息技术 ---
    "新一代信息技术": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "1-2年",
                       "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "信息技术": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "1-2年",
                 "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "集成电路": {"median_roi": 3.5, "top_quartile": 10.0, "typical_duration": "2-4年",
                 "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "芯片": {"median_roi": 3.5, "top_quartile": 10.0, "typical_duration": "2-4年",
             "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "tech"},

    # --- 2. 生物技术 ---
    "生物技术": {"median_roi": 3.0, "top_quartile": 9.0, "typical_duration": "2-4年",
                 "investment_level": "medium", "subsidy_density": "high", "risk_factor": "tech"},
    "种业": {"median_roi": 3.0, "top_quartile": 8.0, "typical_duration": "2-3年",
             "investment_level": "medium", "subsidy_density": "very_high", "risk_factor": "policy"},
    "合成生物学": {"median_roi": 4.5, "top_quartile": 15.0, "typical_duration": "2-5年",
                   "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "tech"},

    # --- 3. 新能源 ---
    "新能源": {"median_roi": 3.5, "top_quartile": 10.0, "typical_duration": "3-5年",
               "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "combo"},
    "光伏": {"median_roi": 3.5, "top_quartile": 8.0, "typical_duration": "2-4年",
             "investment_level": "high", "subsidy_density": "high", "risk_factor": "market"},
    "风电": {"median_roi": 3.0, "top_quartile": 7.0, "typical_duration": "3-5年",
             "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "combo"},
    "氢能": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "3-6年",
             "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},
    "新型储能": {"median_roi": 4.0, "top_quartile": 11.0, "typical_duration": "2-4年",
                 "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "核能": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "5-10年",
             "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "combo"},
    "生物质能": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "3-5年",
                 "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "market"},

    # --- 4. 新材料 ---
    "新材料": {"median_roi": 3.0, "top_quartile": 7.0, "typical_duration": "2-4年",
               "investment_level": "high", "subsidy_density": "high", "risk_factor": "tech"},
    "碳纤维": {"median_roi": 3.5, "top_quartile": 8.0, "typical_duration": "3-5年",
               "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},
    "石墨烯": {"median_roi": 4.0, "top_quartile": 10.0, "typical_duration": "2-4年",
               "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "tech"},
    "稀土材料": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-3年",
                 "investment_level": "high", "subsidy_density": "medium", "risk_factor": "policy"},

    # --- 5. 高端装备 ---
    "高端装备": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-4年",
                 "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "combo"},
    "工业母机": {"median_roi": 2.0, "top_quartile": 5.0, "typical_duration": "3-5年",
                 "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "工业机器人": {"median_roi": 3.0, "top_quartile": 8.0, "typical_duration": "2-3年",
                   "investment_level": "high", "subsidy_density": "high", "risk_factor": "market"},
    "智能制造": {"median_roi": 3.0, "top_quartile": 7.0, "typical_duration": "2-3年",
                 "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "combo"},

    # --- 6. 新能源汽车 ---
    "新能源汽车": {"median_roi": 3.0, "top_quartile": 8.0, "typical_duration": "2-4年",
                   "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "market"},
    "动力电池": {"median_roi": 3.5, "top_quartile": 9.0, "typical_duration": "2-4年",
                 "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "combo"},
    "智能网联": {"median_roi": 4.0, "top_quartile": 11.0, "typical_duration": "2-4年",
                 "investment_level": "high", "subsidy_density": "high", "risk_factor": "tech"},

    # --- 7. 绿色环保 ---
    "绿色环保": {"median_roi": 3.0, "top_quartile": 7.0, "typical_duration": "2-4年",
                 "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "policy"},
    "生态修复": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-4年",
                 "investment_level": "medium", "subsidy_density": "high", "risk_factor": "policy"},
    "碳交易": {"median_roi": 5.0, "top_quartile": 15.0, "typical_duration": "1-2年",
               "investment_level": "low", "subsidy_density": "medium", "risk_factor": "market"},
    "碳捕集": {"median_roi": 2.0, "top_quartile": 5.0, "typical_duration": "3-6年",
               "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},

    # --- 8. 航空航天 ---
    "航空航天": {"median_roi": 2.5, "top_quartile": 7.0, "typical_duration": "3-5年",
                 "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "combo"},
    "商业航天": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "3-5年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},
    "低空经济": {"median_roi": 5.0, "top_quartile": 15.0, "typical_duration": "1-3年",
                 "investment_level": "high", "subsidy_density": "very_high", "risk_factor": "combo"},

    # --- 9. 海洋装备 ---
    "海洋装备": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "3-5年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "combo"},

    # --- 新兴支柱产业（独立项） ---
    "生物医药": {"median_roi": 2.0, "top_quartile": 8.0, "typical_duration": "3-7年",
                 "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "tech"},
    "智能机器人": {"median_roi": 3.5, "top_quartile": 10.0, "typical_duration": "2-4年",
                   "investment_level": "high", "subsidy_density": "high", "risk_factor": "tech"},

    # ====================================================
    # 二、未来产业（6 个）
    # ====================================================
    "量子科技": {"median_roi": 3.0, "top_quartile": 10.0, "typical_duration": "5-10年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},
    "生物制造": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "3-5年",
                 "investment_level": "high", "subsidy_density": "medium", "risk_factor": "tech"},
    "绿色氢能": {"median_roi": 3.5, "top_quartile": 10.0, "typical_duration": "4-7年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},
    "脑机接口": {"median_roi": 3.0, "top_quartile": 10.0, "typical_duration": "5-10年",
                 "investment_level": "medium", "subsidy_density": "low", "risk_factor": "tech"},
    "具身智能": {"median_roi": 4.5, "top_quartile": 15.0, "typical_duration": "2-5年",
                 "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "tech"},
    "6G": {"median_roi": 3.0, "top_quartile": 8.0, "typical_duration": "5-8年",
           "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "tech"},

    # ====================================================
    # 三、传统制造业（7 个子行业）
    # ====================================================
    "石化化工": {"median_roi": 2.5, "top_quartile": 5.0, "typical_duration": "2-4年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "policy"},
    "钢铁": {"median_roi": 2.0, "top_quartile": 4.0, "typical_duration": "3-5年",
             "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "policy"},
    "有色": {"median_roi": 2.5, "top_quartile": 5.0, "typical_duration": "2-4年",
             "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "market"},
    "建材": {"median_roi": 2.5, "top_quartile": 5.0, "typical_duration": "2-3年",
             "investment_level": "high", "subsidy_density": "medium", "risk_factor": "market"},
    "机械": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-4年",
             "investment_level": "high", "subsidy_density": "high", "risk_factor": "market"},
    "轻工纺织": {"median_roi": 3.0, "top_quartile": 6.0, "typical_duration": "1-2年",
                 "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "market"},
    "制造业": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-4年",
               "investment_level": "high", "subsidy_density": "high", "risk_factor": "combo"},
    "汽车": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-4年",
             "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "market"},
    "电力装备": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "3-5年",
                 "investment_level": "very_high", "subsidy_density": "medium", "risk_factor": "policy"},

    # ====================================================
    # 四、基础设施产业（6 张网）
    # ====================================================
    "水网": {"median_roi": 2.0, "top_quartile": 4.0, "typical_duration": "3-7年",
             "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "policy"},
    "电网": {"median_roi": 2.5, "top_quartile": 5.0, "typical_duration": "3-5年",
             "investment_level": "very_high", "subsidy_density": "high", "risk_factor": "policy"},
    "算力网": {"median_roi": 4.0, "top_quartile": 10.0, "typical_duration": "1-3年",
               "investment_level": "very_high", "subsidy_density": "very_high", "risk_factor": "combo"},
    "新型通信网": {"median_roi": 3.5, "top_quartile": 8.0, "typical_duration": "2-4年",
                   "investment_level": "high", "subsidy_density": "high", "risk_factor": "combo"},
    "城市地下管网": {"median_roi": 2.0, "top_quartile": 4.0, "typical_duration": "3-5年",
                     "investment_level": "high", "subsidy_density": "medium", "risk_factor": "policy"},
    "物流网": {"median_roi": 3.0, "top_quartile": 7.0, "typical_duration": "2-4年",
               "investment_level": "high", "subsidy_density": "medium", "risk_factor": "market"},

    # ====================================================
    # 五、三次产业 + 基准行业
    # ====================================================
    "第一产业": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-3年",
                 "investment_level": "low", "subsidy_density": "very_high", "risk_factor": "policy"},
    "农业": {"median_roi": 2.5, "top_quartile": 6.0, "typical_duration": "2-3年",
             "investment_level": "low", "subsidy_density": "very_high", "risk_factor": "policy"},
    "第三产业": {"median_roi": 3.5, "top_quartile": 8.0, "typical_duration": "1-3年",
                 "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "market"},
    "服务业": {"median_roi": 3.5, "top_quartile": 8.0, "typical_duration": "1-3年",
               "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "market"},
    "煤炭能源": {"median_roi": 2.5, "top_quartile": 5.0, "typical_duration": "2-3年",
                 "investment_level": "high", "subsidy_density": "medium", "risk_factor": "policy"},

    # ====================================================
    # 兼容旧 key + 轻资产/通用兜底
    # ====================================================
    "数字经济": {"median_roi": 4.0, "top_quartile": 12.0, "typical_duration": "1-2年",
                 "investment_level": "medium", "subsidy_density": "high", "risk_factor": "tech"},
    "轻资产": {"median_roi": 5.0, "top_quartile": 15.0, "typical_duration": "1-2年",
               "investment_level": "low", "subsidy_density": "medium", "risk_factor": "market"},
    "通用": {"median_roi": 3.0, "top_quartile": 8.0, "typical_duration": "2-3年",
             "investment_level": "medium", "subsidy_density": "medium", "risk_factor": "combo"},
}


@dataclass
class PolicyFinancials:
    """政策的财务参数"""
    # 政策类型
    policy_type: str = "其他"

    # 预期收益
    max_funding: float = 0          # 最高资金支持（万元）
    tax_benefit_annual: float = 0   # 年税收优惠（万元）
    brand_value: float = 0          # 品牌/资质价值（万元，估算）
    market_value: float = 0         # 市场准入价值（万元，估算）
    follow_up_value: float = 0      # 后续跟投/政策价值（万元，估算）

    # 投入成本
    application_cost: float = 0     # 申报成本（万元）
    compliance_cost_annual: float = 0  # 年合规成本（万元）
    equity_dilution: float = 0      # 股权稀释比例（%）
    self_fund_ratio: float = 0      # 自筹资金比例（%）

    # 时间参数
    funding_duration_years: int = 1
    application_months: int = 3
    compliance_years: int = 3

    # 间接收益
    policy_network_value: float = 0
    talent_value: float = 0


@dataclass
class ROIResult:
    """ROI 评估结果"""
    # 收益
    total_benefit: float = 0
    risk_adjusted_benefit: float = 0

    # 成本
    total_cost: float = 0
    time_cost_months: int = 0

    # ROI 指标
    roi_ratio: float = 0
    payback_months: int = 0
    annual_return: float = 0

    # 风险调整
    success_probability: float = 0
    risk_level: str = "中"

    # 行业基准对比
    benchmark_status: str = ""      # "优于行业" / "持平行业" / "低于行业"
    benchmark_percentile: float = 0  # 百分位排名

    # 评估摘要
    verdict: str = ""
    key_factors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "policy_type": "",
            "total_benefit": round(self.total_benefit, 1),
            "risk_adjusted_benefit": round(self.risk_adjusted_benefit, 1),
            "total_cost": round(self.total_cost, 1),
            "roi_ratio": round(self.roi_ratio, 2),
            "payback_months": self.payback_months,
            "annual_return": round(self.annual_return, 1),
            "success_probability": round(self.success_probability, 2),
            "risk_level": self.risk_level,
            "benchmark_status": self.benchmark_status,
            "verdict": self.verdict,
        }


class ROICalculator:
    """ROI 量化评估器 v2.0"""

    def __init__(self, industry: str = "通用"):
        self.industry = industry
        self.benchmark = INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["通用"])

    def estimate_financials(self, policy: dict, profile: dict) -> PolicyFinancials:
        """根据政策文本和企业画像估算财务参数

        v2.0: 先分类政策类型，再按类型+企业规模匹配财务模型
        """
        title = policy.get("title", "")
        summary = policy.get("summary", "")
        text = f"{title} {summary}"

        basic = profile.get("basic_info", {})
        capital = profile.get("capital", {})
        quals = profile.get("qualifications", {})

        # Step 1: 分类政策类型
        policy_type = classify_policy_type(title, summary)
        model = POLICY_FINANCIAL_MODELS.get(policy_type, POLICY_FINANCIAL_MODELS["其他"])

        # Step 2: 估算企业规模系数
        reg_cap = basic.get("registered_capital", 3000)
        scale = self._get_scale(reg_cap)
        scale_factor = SCALE_FACTORS[scale]

        fin = PolicyFinancials()
        fin.policy_type = policy_type

        # Step 3: 估算预期收益（按政策类型模型 + 企业规模系数）
        funding_low, funding_high = model["funding_range"]
        # 尝试从文本提取具体金额，提取不到则用模型中位数
        extracted_amount = self._extract_funding_amount(text)
        if extracted_amount > 0:
            fin.max_funding = extracted_amount
        else:
            fin.max_funding = (funding_low + funding_high) / 2 * scale_factor["funding_multiplier"]

        # 税收优惠: 税收类政策特别计算
        if policy_type == "税收优惠":
            fin.tax_benefit_annual = self._estimate_tax_benefit_by_revenue(basic)
        elif "税收" in text or "减税" in text:
            fin.tax_benefit_annual = self._estimate_tax_benefit_by_revenue(basic) * 0.3
        else:
            fin.tax_benefit_annual = 0

        fin.brand_value = model["brand_value"] * scale_factor["funding_multiplier"]
        fin.market_value = model["market_value"] * scale_factor["funding_multiplier"]
        fin.follow_up_value = model["indirect_benefits"]["follow_up_funding"] * scale_factor["funding_multiplier"]
        fin.policy_network_value = model["indirect_benefits"]["policy_network"]
        fin.talent_value = model["indirect_benefits"]["talent_attraction"]

        # Step 4: 估算投入成本
        fin.application_cost = model["application_cost"] * scale_factor["cost_multiplier"]
        fin.compliance_cost_annual = model["compliance_cost_annual"] * scale_factor["cost_multiplier"]

        # 股权影响（拨改投/基金类）
        if policy_type in ("拨改投", "基金/投融资"):
            if reg_cap > 0:
                fin.equity_dilution = min(
                    30,
                    round(fin.max_funding / reg_cap * 100, 1)
                )
            fin.self_fund_ratio = model["self_fund_ratio"]

        # 时间参数
        fin.application_months = model["application_months"]
        fin.funding_duration_years = model["funding_duration_years"]
        fin.compliance_years = model["compliance_years"]

        return fin

    def calculate(self, financials: PolicyFinancials, success_probability: float) -> ROIResult:
        """计算 ROI（含行业基准对比）"""
        result = ROIResult()
        result.success_probability = success_probability

        # 1. 总预期收益（含间接收益）
        # P0 fix: 拨改投/基金/投融资 = 一次性投入，不乘以年数
        #         专项补贴/资质认定 = 一次性拨款
        #         税收优惠 = 年度持续收益
        if financials.policy_type in ("拨改投", "基金/投融资"):
            # 股权类投资: 一次性注入，价值 = 投资额本身（退出时可能增值）
            funding_benefit = financials.max_funding
        elif financials.policy_type in ("专项补贴", "资质认定", "项目审批"):
            # 一次性拨款/认定
            funding_benefit = financials.max_funding
        elif financials.policy_type == "税收优惠":
            # 税收优惠: 年度持续收益
            funding_benefit = financials.tax_benefit_annual * financials.funding_duration_years
        else:
            # 其他: 保守按一次性计算
            funding_benefit = financials.max_funding

        tax_benefit = financials.tax_benefit_annual * financials.compliance_years
        indirect_total = (financials.brand_value + financials.market_value
                         + financials.follow_up_value + financials.policy_network_value
                         + financials.talent_value)
        result.total_benefit = funding_benefit + tax_benefit + indirect_total

        # 2. 风险调整后收益
        result.risk_adjusted_benefit = result.total_benefit * success_probability

        # 3. 总投入成本
        compliance_total = financials.compliance_cost_annual * financials.compliance_years
        result.total_cost = financials.application_cost + compliance_total

        # 4. ROI 倍数
        if result.total_cost > 0:
            result.roi_ratio = result.risk_adjusted_benefit / result.total_cost
        else:
            result.roi_ratio = float('inf') if result.risk_adjusted_benefit > 0 else 0

        # 5. 回本周期（按政策类型区分）
        if result.risk_adjusted_benefit > 0 and financials.application_months > 0:
            if financials.policy_type in ("拨改投", "基金/投融资"):
                # 股权投资: 资金一次性注入，回本 = 申报周期 + 首笔资金到账时间
                result.payback_months = financials.application_months + 3  # +3个月首笔到账
            elif financials.policy_type in ("专项补贴", "资质认定", "项目审批"):
                # 一次性拨款: 回本 = 申报周期 + 资金到账
                result.payback_months = financials.application_months + 2  # +2个月拨付
            elif financials.policy_type == "税收优惠":
                # 税收优惠: 持续性收益，按年计算回本
                if financials.tax_benefit_annual > 0:
                    result.payback_months = max(
                        financials.application_months,
                        int(result.total_cost / (financials.tax_benefit_annual / 12))
                    )
                else:
                    result.payback_months = 999
            else:
                total_months = financials.compliance_years * 12
                monthly_return = result.risk_adjusted_benefit / total_months if total_months > 0 else 0
                if monthly_return > 0:
                    result.payback_months = min(int(result.total_cost / monthly_return), total_months)
                else:
                    result.payback_months = 999
        else:
            result.payback_months = 999

        # 6. 年化回报率
        if result.total_cost > 0 and financials.compliance_years > 0:
            result.annual_return = (
                (result.risk_adjusted_benefit - result.total_cost)
                / result.total_cost
                / financials.compliance_years
                * 100
            )
        else:
            result.annual_return = 0

        # 7. 风险等级
        if success_probability >= 0.7:
            result.risk_level = "低"
        elif success_probability >= 0.4:
            result.risk_level = "中"
        else:
            result.risk_level = "高"

        # 8. 行业基准对比
        result.benchmark_status, result.benchmark_percentile = self._compare_benchmark(
            result.roi_ratio
        )

        # 9. 一句话结论
        result.verdict = self._generate_verdict(result, financials)

        # 10. 关键影响因素
        result.key_factors = self._identify_key_factors(result, financials)

        return result

    def _get_scale(self, registered_capital: float) -> str:
        """根据注册资本判断企业规模"""
        if registered_capital < 1000:
            return "small"
        elif registered_capital < 5000:
            return "medium"
        elif registered_capital < 50000:
            return "large"
        else:
            return "xlarge"

    def _extract_funding_amount(self, text: str) -> float:
        """从政策文本中提取资金额度（万元）"""
        patterns = [
            r"最高.*?(\d+)\s*万元",
            r"不超过.*?(\d+)\s*万元",
            r"资助.*?(\d+)\s*万元",
            r"补贴.*?(\d+)\s*万元",
            r"奖励.*?(\d+)\s*万元",
            r"(\d+)\s*万元.*?以内",
            r"每家.*?(\d+)\s*万元",
            r"单个项目.*?(\d+)\s*万元",
        ]
        amounts = []
        for p in patterns:
            for m in re.finditer(p, text):
                amounts.append(float(m.group(1)))

        if amounts:
            return max(amounts)  # 取最大提取值
        return 0

    def _estimate_tax_benefit_by_revenue(self, basic: dict) -> float:
        """根据企业营收估算年税收优惠"""
        # 获取营收（尝试多个字段名）
        revenue = 0
        finance = basic.get("finance", basic)
        if isinstance(finance, dict):
            revenue = finance.get("annual_revenue", 0)
        if not revenue:
            revenue = basic.get("annual_revenue", 0)

        if revenue <= 0:
            return 0

        # 高企 15% 税率（标准 25%），假设利润率 10%
        taxable = revenue * 0.10
        saving = taxable * 0.10  # 10% 税率差
        return round(saving, 1)

    def _compare_benchmark(self, roi_ratio: float) -> tuple:
        """与行业基准对比（v3.0: 含资本密集度和政策密度修正）"""
        median = self.benchmark["median_roi"]
        top = self.benchmark["top_quartile"]
        invest = self.benchmark.get("investment_level", "medium")
        density = self.benchmark.get("subsidy_density", "medium")

        # 资本密集度修正: 高资本密度行业 ROI 普遍偏低，适当放宽基准
        invest_adjustment = {
            "very_high": 0.8,   # 资本密集型（核能/芯片），ROI 天花板低，基准打折
            "high": 0.9,
            "medium": 1.0,
            "low": 1.1,         # 轻资产行业 ROI 普遍高，基准适当收紧
        }
        adj = invest_adjustment.get(invest, 1.0)
        adjusted_median = median * adj
        adjusted_top = top * adj

        # 政策密度修正: 高密度行业可争取更多叠加收益，ROI 天花板更高
        density_bonus = {
            "very_high": 1.15,
            "high": 1.10,
            "medium": 1.0,
            "low": 0.9,
        }
        db = density_bonus.get(density, 1.0)

        if roi_ratio >= adjusted_top * db:
            return "优于行业（前25%）", 90
        elif roi_ratio >= adjusted_median:
            if adjusted_top > adjusted_median:
                percentile = 50 + (roi_ratio - adjusted_median) / (adjusted_top - adjusted_median) * 40
            else:
                percentile = 70
            return "优于行业中位数", min(percentile, 89)
        elif roi_ratio >= adjusted_median * 0.5:
            percentile = 20 + (roi_ratio - adjusted_median * 0.5) / (adjusted_median * 0.5) * 30
            return "接近行业中位数", min(percentile, 49)
        else:
            return "低于行业平均", max(5, roi_ratio / max(adjusted_median, 0.1) * 20)

    @staticmethod
    def auto_classify_industry(profile: dict, policy: dict = None) -> str:
        """根据企业画像 + 政策文本自动识别行业（返回 INDUSTRY_BENCHMARKS 的 key）

        匹配优先级:
          1. 企业 primary_sector 精确命中
          2. 企业 keywords_medium 模糊命中
          3. 政策关键词命中
          4. 兜底: 通用
        """
        basic = profile.get("basic_info", {})
        sector = basic.get("primary_sector", "").strip()

        # 1. 精确匹配企业 primary_sector
        if sector and sector in INDUSTRY_BENCHMARKS:
            return sector

        # 2. 模糊匹配（sector 包含 benchmark key，或 benchmark key 包含 sector）
        for key in INDUSTRY_BENCHMARKS:
            if key == "通用" or len(key) < 2:
                continue
            if key in sector or sector in key:
                return key

        # 3. 用 policy 文本关键词匹配
        if policy:
            text = f"{policy.get('title', '')} {policy.get('summary', '')}"
            best_key = "通用"
            best_score = 0
            for key, bench in INDUSTRY_BENCHMARKS.items():
                if key == "通用":
                    continue
                # 用 key 名本身作为关键词检测
                if key in text:
                    if len(key) > best_score:  # 优先匹配更具体的行业名
                        best_key = key
                        best_score = len(key)
            if best_score > 0:
                return best_key

        return "通用"

    def get_benchmark_summary(self) -> dict:
        """返回当前行业基准的完整摘要（供报告输出）"""
        return {
            "industry": self.industry,
            "median_roi": self.benchmark["median_roi"],
            "top_quartile": self.benchmark["top_quartile"],
            "typical_duration": self.benchmark["typical_duration"],
            "investment_level": self.benchmark.get("investment_level", "medium"),
            "investment_label": {
                "very_high": "极重资产", "high": "重资产",
                "medium": "中等", "low": "轻资产"
            }.get(self.benchmark.get("investment_level", "medium"), "中等"),
            "subsidy_density": self.benchmark.get("subsidy_density", "medium"),
            "subsidy_label": {
                "very_high": "政策密集", "high": "政策较多",
                "medium": "一般", "low": "政策较少"
            }.get(self.benchmark.get("subsidy_density", "medium"), "一般"),
            "risk_factor": self.benchmark.get("risk_factor", "combo"),
            "risk_label": {
                "tech": "技术风险为主", "market": "市场风险为主",
                "policy": "政策依赖度高", "combo": "综合风险"
            }.get(self.benchmark.get("risk_factor", "combo"), "综合风险"),
        }

    def _generate_verdict(self, result: ROIResult, financials: PolicyFinancials) -> str:
        """生成一句话结论"""
        policy_type = financials.policy_type

        # 按政策类型定制结论
        if result.roi_ratio >= 10:
            base = f"高回报项目（ROI {result.roi_ratio:.1f}x）"
        elif result.roi_ratio >= 5:
            base = f"良好回报（ROI {result.roi_ratio:.1f}x）"
        elif result.roi_ratio >= 3:
            base = f"合理回报（ROI {result.roi_ratio:.1f}x）"
        elif result.roi_ratio >= 1:
            base = f"微利项目（ROI {result.roi_ratio:.1f}x）"
        elif result.roi_ratio > 0:
            base = f"低回报（ROI {result.roi_ratio:.1f}x）"
        else:
            base = "无法量化收益"

        # 加上行业基准
        benchmark = result.benchmark_status

        if result.roi_ratio >= 10:
            return f"{base}，{benchmark}，强烈建议申报"
        elif result.roi_ratio >= 5:
            return f"{base}，{benchmark}，建议优先申报"
        elif result.roi_ratio >= 3:
            return f"{base}，{benchmark}，值得考虑"
        elif result.roi_ratio >= 1:
            return f"{base}，{benchmark}，需权衡机会成本"
        elif result.roi_ratio > 0:
            return f"{base}，{benchmark}，建议从战略价值角度评估"
        else:
            return "建议从战略价值角度评估"

    def _identify_key_factors(self, result: ROIResult, financials: PolicyFinancials) -> list:
        """识别关键影响因素"""
        factors = []

        # 收益因素
        if financials.max_funding > 0:
            factors.append(f"[收益] 资金支持: {financials.max_funding:.0f}万元（{financials.policy_type}）")
        if financials.tax_benefit_annual > 0:
            factors.append(f"[收益] 税收优惠: 年省{financials.tax_benefit_annual:.0f}万元")
        if financials.follow_up_value > 0:
            factors.append(f"[收益] 后续价值: 预估{financials.follow_up_value:.0f}万元（跟投/新政策）")
        if financials.brand_value > 0:
            factors.append(f"[收益] 品牌价值: 预估{financials.brand_value:.0f}万元")

        # 成本因素
        if financials.equity_dilution > 0:
            factors.append(f"[成本] 股权稀释: {financials.equity_dilution}%")
        if financials.application_months > 4:
            factors.append(f"[成本] 申报周期长: {financials.application_months}个月")
        if financials.self_fund_ratio > 0:
            factors.append(f"[成本] 自筹比例: {financials.self_fund_ratio:.0%}")

        # 概率因素
        if result.success_probability < 0.5:
            factors.append("[风险] 成功概率偏低，建议提升申报材料质量")
        if result.payback_months > 24:
            factors.append("[风险] 回本周期较长，需评估资金占用成本")

        # 基准因素
        if result.benchmark_status:
            factors.append(f"[基准] {result.benchmark_status}（行业中位数ROI: {self.benchmark['median_roi']}x）")

        return factors


def format_roi_report(result: ROIResult, financials: PolicyFinancials,
                      benchmark_summary: dict = None) -> str:
    """格式化 ROI 评估报告为 Markdown（v3.0: 含行业上下文）"""
    lines = [
        "## ROI 量化评估",
        "",
        f"**政策类型**: {financials.policy_type}",
    ]

    # 行业上下文（v3.0 新增）
    if benchmark_summary:
        lines.extend([
            "",
            "### 行业上下文",
            "",
            "| 维度 | 评估 |",
            "|:-----|:-----|",
            f"| 所属行业 | {benchmark_summary.get('industry', '通用')} |",
            f"| 资本密集度 | {benchmark_summary.get('investment_label', '中等')} |",
            f"| 政策密度 | {benchmark_summary.get('subsidy_label', '一般')} |",
            f"| 主要风险 | {benchmark_summary.get('risk_label', '综合风险')} |",
            f"| 典型周期 | {benchmark_summary.get('typical_duration', '2-3年')} |",
            f"| 行业中位数ROI | {benchmark_summary.get('median_roi', 3.0)}x |",
            f"| 行业Top25% ROI | {benchmark_summary.get('top_quartile', 8.0)}x |",
        ])

    lines.extend([
        "",
        "### 收益分析",
        "",
        "| 项目 | 金额（万元） | 说明 |",
        "|:-----|:----------:|:-----|",
        f"| 资金支持 | {financials.max_funding:.0f} | 最高额度 x {financials.funding_duration_years}年 |",
    ])

    if financials.tax_benefit_annual > 0:
        lines.append(f"| 税收优惠 | {financials.tax_benefit_annual:.0f}/年 | 年省税 x {financials.compliance_years}年 |")
    if financials.brand_value > 0:
        lines.append(f"| 品牌价值 | {financials.brand_value:.0f} | 资质/排名/背书 |")
    if financials.market_value > 0:
        lines.append(f"| 市场价值 | {financials.market_value:.0f} | 市场准入/渠道 |")
    if financials.follow_up_value > 0:
        lines.append(f"| 后续价值 | {financials.follow_up_value:.0f} | 跟投/后续政策 |")

    lines.extend([
        f"| **总预期收益** | **{result.total_benefit:.0f}** | |",
        f"| 风险调整后 | {result.risk_adjusted_benefit:.0f} | x 成功率 {result.success_probability:.0%} |",
        "",
        "### 成本分析",
        "",
        "| 项目 | 金额（万元） | 说明 |",
        "|:-----|:----------:|:-----|",
        f"| 申报成本 | {financials.application_cost:.0f} | 可研+审计+人工 |",
        f"| 年合规成本 | {financials.compliance_cost_annual:.0f} | x {financials.compliance_years}年 |",
        f"| **总投入成本** | **{result.total_cost:.0f}** | |",
        "",
        "### ROI 指标",
        "",
        "| 指标 | 结果 |",
        "|:-----|:-----|",
        f"| ROI 倍数 | **{result.roi_ratio:.1f}x** |",
        f"| 年化回报率 | {result.annual_return:.1f}% |",
        f"| 回本周期 | {result.payback_months}个月 |",
        f"| 成功概率 | {result.success_probability:.0%} |",
        f"| 风险等级 | {result.risk_level} |",
        f"| 行业对比 | {result.benchmark_status} |",
        "",
        f"> **{result.verdict}**",
        "",
    ])

    if result.key_factors:
        lines.append("### 关键因素")
        lines.append("")
        for f in result.key_factors:
            lines.append(f"- {f}")
        lines.append("")

    return "\n".join(lines)
