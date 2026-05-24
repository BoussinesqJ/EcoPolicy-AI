# -*- coding: utf-8 -*-
"""
政策组合叠加分析模块 v1.0

解决的核心问题:
  企业面对多条政策时，哪些可以叠加？哪些互斥？
  组合后的总价值是多少？

核心概念:
  - 互补政策(Complementary): 可以同时申报 (如: 拨改投 + 高企税收 + 专项补贴)
  - 互斥政策(Mutually Exclusive): 只能选其一 (如: 同一资金池的A/B专项)
  - 政策组合(Policy Bundle): 最优的政策搭配方案
  - 政策收入天花板(Policy Ceiling): 企业在当前条件下可争取的最大政策收入

评估维度:
  - 互补性检测: 基于政策类型 + 资金来源 + 政策条款
  - 互斥性检测: 同一资金池 / 同一申报窗口 / 排他性条款
  - 组合收益计算: 叠加收益 - 重复成本 - 机会成本
  - 天花板估算: 理论最大值 vs 可行最大值
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("agent.stacker")


# ============================================================
# 政策互斥规则矩阵
# ============================================================

# 定义哪些政策类型之间可以叠加、哪些互斥
# 叠加规则:
#   "complementary" = 可叠加 (收益累加)
#   "exclusive" = 互斥 (只能选其一)
#   "conditional" = 条件互斥 (某些条件下可叠加)
#   "partial" = 部分重叠 (收益有交叉，不能简单累加)

STACKING_RULES = {
    # 拨改投: 可与税收优惠/资质认定/专项补贴叠加，与基金/投融资互斥
    ("拨改投", "税收优惠"): "complementary",
    ("拨改投", "资质认定"): "complementary",
    ("拨改投", "专项补贴"): "complementary",
    ("拨改投", "项目审批"): "complementary",
    ("拨改投", "基金/投融资"): "exclusive",
    ("拨改投", "拨改投"): "exclusive",  # 同类互斥

    # 专项补贴: 可与大多数类型叠加
    ("专项补贴", "税收优惠"): "complementary",
    ("专项补贴", "资质认定"): "complementary",
    ("专项补贴", "项目审批"): "complementary",
    ("专项补贴", "基金/投融资"): "partial",
    ("专项补贴", "专项补贴"): "conditional",  # 同一资金池互斥，不同资金池可叠加

    # 税收优惠: 几乎可以与所有类型叠加
    ("税收优惠", "资质认定"): "complementary",
    ("税收优惠", "项目审批"): "complementary",
    ("税收优惠", "基金/投融资"): "complementary",
    ("税收优惠", "税收优惠"): "exclusive",  # 同类互斥

    # 资质认定: 可与大多数类型叠加
    ("资质认定", "项目审批"): "complementary",
    ("资质认定", "基金/投融资"): "complementary",
    ("资质认定", "资质认定"): "exclusive",  # 同类互斥

    # 项目审批: 可与融资叠加
    ("项目审批", "基金/投融资"): "complementary",
    ("项目审批", "项目审批"): "conditional",  # 不同项目可叠加

    # 基金/投融资: 同类互斥
    ("基金/投融资", "基金/投融资"): "exclusive",
}


def get_stacking_rule(type_a: str, type_b: str) -> str:
    """获取两个政策类型之间的叠加规则"""
    # 规范化类型名
    norm = {"基金/投融资": "基金/投融资"}
    type_a = norm.get(type_a, type_a)
    type_b = norm.get(type_b, type_b)

    key = (type_a, type_b)
    key_rev = (type_b, type_a)

    if key in STACKING_RULES:
        return STACKING_RULES[key]
    if key_rev in STACKING_RULES:
        return STACKING_RULES[key_rev]

    # 同类型默认互斥
    if type_a == type_b:
        return "exclusive"

    # 默认可叠加
    return "complementary"


# ============================================================
# 政策相似度检测 (用于互斥判断)
# ============================================================

def calculate_policy_similarity(policy_a: dict, policy_b: dict) -> float:
    """计算两条政策的相似度 (0-1)

    高相似度意味着可能是同一资金池或同一政策的不同条款
    """
    title_a = policy_a.get("title", "")
    title_b = policy_b.get("title", "")
    summary_a = policy_a.get("summary", "")
    summary_b = policy_b.get("summary", "")

    # 来源相同增加相似度
    source_same = policy_a.get("source", "") == policy_b.get("source", "")
    source_bonus = 0.15 if source_same else 0

    # 标题关键词重叠
    words_a = set(title_a)
    words_b = set(title_b)
    if words_a and words_b:
        title_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
    else:
        title_overlap = 0

    # 摘要关键词重叠 (取前100字)
    sum_a = set(summary_a[:100])
    sum_b = set(summary_b[:100])
    if sum_a and sum_b:
        summary_overlap = len(sum_a & sum_b) / max(len(sum_a | sum_b), 1)
    else:
        summary_overlap = 0

    # 同一金额/资金池检测
    amount_same = False
    import re
    amounts_a = re.findall(r"(\d+)\s*万元", f"{title_a} {summary_a}")
    amounts_b = re.findall(r"(\d+)\s*万元", f"{title_b} {summary_b}")
    if amounts_a and amounts_b:
        # 如果金额完全相同，很可能是同一资金池
        amount_same = set(amounts_a) == set(amounts_b)

    amount_bonus = 0.3 if amount_same else 0

    similarity = (
        title_overlap * 0.4
        + summary_overlap * 0.3
        + source_bonus
        + amount_bonus
    )

    return min(similarity, 1.0)


# ============================================================
# 政策组合数据结构
# ============================================================

@dataclass
class PolicyStackItem:
    """组合中的单条政策"""
    policy: dict
    policy_type: str
    individual_roi: float = 0.0
    individual_benefit: float = 0.0
    individual_cost: float = 0.0
    stacking_role: str = "primary"  # primary / supplementary / redundant
    overlap_note: str = ""


@dataclass
class PolicyBundle:
    """政策组合方案"""
    bundle_id: int = 0
    name: str = ""
    policies: list = field(default_factory=list)  # list of PolicyStackItem

    # 组合收益
    total_benefit: float = 0           # 组合总收益 (万元)
    total_cost: float = 0              # 组合总成本 (万元)
    combined_roi: float = 0            # 组合 ROI
    overlap_reduction: float = 0       # 因重叠而扣减的收益 (万元)

    # 约束条件
    exclusions: list = field(default_factory=list)  # 互斥说明
    time_spread_months: int = 0        # 需要分散的时间窗口

    # 推荐
    recommendation: str = ""
    priority: int = 0                  # 越高越优先

    # 风险
    concentration_risk: str = ""       # 政策集中度风险
    compliance_load: str = ""          # 合规负担


@dataclass
class PolicyCeiling:
    """政策收入天花板"""
    enterprise_id: str = ""
    enterprise_name: str = ""

    # 理论天花板 (所有政策都拿到)
    theoretical_max: float = 0         # 万元

    # 可行天花板 (考虑互斥和资源约束)
    feasible_max: float = 0            # 万元

    # 最优组合
    best_bundle: object = None         # PolicyBundle

    # 分解
    by_type: dict = field(default_factory=dict)  # {政策类型: (数量, 总收益)}

    # 已有政策收入 (已获批的)
    existing_income: float = 0

    # 增量空间
    incremental_space: float = 0       # feasible_max - existing_income


# ============================================================
# 政策组合叠加分析器
# ============================================================

class PolicyStacker:
    """政策组合叠加分析引擎"""

    def __init__(self):
        pass

    def analyze(self, policies_with_roi: list, enterprise_profile: dict = None) -> dict:
        """对一批已评分的政策进行组合叠加分析

        Args:
            policies_with_roi: 带 ROI 数据的政策列表
                每条: {"policy": dict, "roi_ratio": float, "benefit": float,
                       "cost": float, "policy_type": str, "recommendation": int}
            enterprise_profile: 企业画像 (可选，用于个性化分析)

        Returns:
            {
                "bundles": [PolicyBundle, ...],    # 候选组合方案
                "ceiling": PolicyCeiling,           # 政策收入天花板
                "pairwise": {(i,j): rule, ...},    # 两两互斥关系
                "summary": str,                     # 一句话总结
            }
        """
        if not policies_with_roi:
            return {
                "bundles": [],
                "ceiling": PolicyCeiling(),
                "pairwise": {},
                "summary": "No policies to analyze",
            }

        # Step 1: 两两检测互斥关系
        pairwise = self._detect_exclusions(policies_with_roi)

        # Step 2: 生成候选组合方案 (贪心算法)
        bundles = self._generate_bundles(policies_with_roi, pairwise)

        # Step 3: 计算政策收入天花板
        ceiling = self._calculate_ceiling(policies_with_roi, bundles, enterprise_profile)

        # Step 4: 生成总结
        summary = self._generate_summary(bundles, ceiling, pairwise)

        return {
            "bundles": bundles,
            "ceiling": ceiling,
            "pairwise": pairwise,
            "summary": summary,
        }

    # ------------------------------------------------------------
    # Step 1: 互斥检测
    # ------------------------------------------------------------

    def _detect_exclusions(self, policies: list) -> dict:
        """检测所有政策两两之间的互斥关系

        Returns:
            {(idx_a, idx_b): {
                "rule": "complementary" / "exclusive" / ...,
                "reason": str,
                "similarity": float,
            }}
        """
        pairwise = {}
        n = len(policies)

        for i in range(n):
            for j in range(i + 1, n):
                p_a = policies[i]
                p_b = policies[j]

                type_a = p_a.get("policy_type", "其他")
                type_b = p_b.get("policy_type", "其他")

                # 1. 类型叠加规则
                rule = get_stacking_rule(type_a, type_b)

                # 2. 政策相似度
                policy_a = p_a.get("policy", {})
                policy_b = p_b.get("policy", {})
                similarity = calculate_policy_similarity(policy_a, policy_b)

                # 3. 如果相似度很高，升级为互斥
                reason = ""
                if similarity > 0.7 and rule != "exclusive":
                    rule = "exclusive"
                    reason = f"High similarity ({similarity:.0%}), likely same funding pool"
                elif rule == "conditional" and similarity > 0.5:
                    rule = "exclusive"
                    reason = f"Conditional with high similarity ({similarity:.0%})"
                elif rule == "exclusive":
                    type_a_label = type_a
                    type_b_label = type_b
                    if type_a == type_b:
                        reason = f"Same policy type ({type_a_label}), mutually exclusive"
                    else:
                        reason = f"{type_a_label} and {type_b_label} are mutually exclusive"
                elif rule == "partial":
                    reason = f"Partial overlap between {type_a} and {type_b}"
                else:
                    reason = f"{type_a} and {type_b} are complementary"

                pairwise[(i, j)] = {
                    "rule": rule,
                    "reason": reason,
                    "similarity": round(similarity, 3),
                }

        return pairwise

    # ------------------------------------------------------------
    # Step 2: 生成候选组合
    # ------------------------------------------------------------

    def _generate_bundles(self, policies: list, pairwise: dict) -> list:
        """生成候选政策组合方案

        策略: 贪心算法
        1. 按 ROI 从高到低排序
        2. 逐个尝试加入当前组合
        3. 如果与组合内已有政策互斥，跳过
        4. 生成 top-3 组合方案
        """
        # 按 ROI * 推荐分 排序
        sorted_policies = sorted(
            enumerate(policies),
            key=lambda x: x[1].get("roi_ratio", 0) * max(x[1].get("recommendation", 1), 1),
            reverse=True,
        )

        bundles = []

        # 方案 A: 纯贪心 (最高 ROI 优先)
        bundle_a = self._greedy_bundle(sorted_policies, pairwise, "highest_roi")
        bundles.append(bundle_a)

        # 方案 B: 最大收益优先 (总额最大)
        sorted_by_benefit = sorted(
            enumerate(policies),
            key=lambda x: x[1].get("benefit", 0),
            reverse=True,
        )
        bundle_b = self._greedy_bundle(sorted_by_benefit, pairwise, "max_benefit")
        bundles.append(bundle_b)

        # 方案 C: 平衡方案 (ROI x 总收益 的几何平均)
        sorted_balanced = sorted(
            enumerate(policies),
            key=lambda x: (
                x[1].get("roi_ratio", 0) * x[1].get("benefit", 0)
            ) ** 0.5,
            reverse=True,
        )
        bundle_c = self._greedy_bundle(sorted_balanced, pairwise, "balanced")
        bundles.append(bundle_c)

        # 去重 (如果两个方案内容完全相同，只保留一个)
        seen = set()
        unique_bundles = []
        for b in bundles:
            key = tuple(sorted(p.policy.get("title", "") for p in b.policies))
            if key not in seen and len(b.policies) > 0:
                seen.add(key)
                unique_bundles.append(b)

        # 编号和排序
        for idx, b in enumerate(unique_bundles):
            b.bundle_id = idx + 1
            b.priority = len(unique_bundles) - idx  # 第一个方案优先级最高

        return unique_bundles

    def _greedy_bundle(self, sorted_policies: list, pairwise: dict,
                        strategy: str) -> PolicyBundle:
        """贪心算法生成一个组合方案"""
        selected_indices = set()
        items = []

        for idx, policy_data in sorted_policies:
            # 检查是否与已选政策互斥
            conflicts = False
            for sel_idx in selected_indices:
                key = (min(idx, sel_idx), max(idx, sel_idx))
                if key in pairwise and pairwise[key]["rule"] == "exclusive":
                    conflicts = True
                    break

            if conflicts:
                continue

            # 加入组合
            selected_indices.add(idx)
            item = PolicyStackItem(
                policy=policy_data.get("policy", {}),
                policy_type=policy_data.get("policy_type", "其他"),
                individual_roi=policy_data.get("roi_ratio", 0),
                individual_benefit=policy_data.get("benefit", 0),
                individual_cost=policy_data.get("cost", 0),
            )
            items.append(item)

        # 构建 PolicyBundle
        bundle = PolicyBundle(
            name=self._bundle_name(strategy),
            policies=items,
        )

        # 计算组合收益
        self._calculate_bundle_metrics(bundle, pairwise)

        return bundle

    def _bundle_name(self, strategy: str) -> str:
        """组合方案名称"""
        names = {
            "highest_roi": "ROI Priority",
            "max_benefit": "Max Value",
            "balanced": "Balanced",
        }
        return names.get(strategy, "Custom")

    def _calculate_bundle_metrics(self, bundle: PolicyBundle, pairwise: dict):
        """计算组合的综合指标"""
        if not bundle.policies:
            return

        # 基础: 简单加总
        raw_benefit = sum(p.individual_benefit for p in bundle.policies)
        raw_cost = sum(p.individual_cost for p in bundle.policies)

        # 扣减: 重复成本 (同一企业的申报成本不会因为多条政策而成倍增加)
        # 假设: 第二条及以后的政策，申报成本降低 30% (共享材料/团队)
        if len(bundle.policies) > 1:
            base_cost = bundle.policies[0].individual_cost
            additional_cost = sum(
                p.individual_cost * 0.7  # 第二条起打 7 折
                for p in bundle.policies[1:]
            )
            adjusted_cost = base_cost + additional_cost
        else:
            adjusted_cost = raw_cost

        # 扣减: 收益重叠 (部分政策的间接收益有交叉)
        # 估算: 每增加一条政策，间接收益重叠 10%
        overlap_rate = 0.10 * max(0, len(bundle.policies) - 1)
        overlap_reduction = raw_benefit * overlap_rate

        # 最终指标
        bundle.total_benefit = raw_benefit - overlap_reduction
        bundle.total_cost = adjusted_cost
        bundle.overlap_reduction = overlap_reduction

        if bundle.total_cost > 0:
            bundle.combined_roi = bundle.total_benefit / bundle.total_cost
        else:
            bundle.combined_roi = float('inf') if bundle.total_benefit > 0 else 0

        # 推荐文本
        if bundle.combined_roi >= 10:
            bundle.recommendation = f"High-Value Bundle: ROI {bundle.combined_roi:.1f}x, total benefit {bundle.total_benefit:.0f}wan"
        elif bundle.combined_roi >= 5:
            bundle.recommendation = f"Good Bundle: ROI {bundle.combined_roi:.1f}x, total benefit {bundle.total_benefit:.0f}wan"
        elif bundle.combined_roi >= 2:
            bundle.recommendation = f"Moderate Bundle: ROI {bundle.combined_roi:.1f}x, total benefit {bundle.total_benefit:.0f}wan"
        else:
            bundle.recommendation = f"Low-Value Bundle: ROI {bundle.combined_roi:.1f}x, consider strategic value"

        # 集中度风险
        if len(bundle.policies) >= 4:
            bundle.concentration_risk = "High: 4+ policies, compliance burden significant"
        elif len(bundle.policies) >= 2:
            bundle.concentration_risk = "Moderate: manageable with proper planning"
        else:
            bundle.concentration_risk = "Low: single policy focus"

        # 合规负担
        total_months = sum(
            p.policy.get("application_months",
                         {"拨改投": 6, "专项补贴": 3, "税收优惠": 1,
                          "资质认定": 4, "项目审批": 6, "基金/投融资": 4,
                          "其他": 3}.get(p.policy_type, 3))
            for p in bundle.policies
        )
        bundle.time_spread_months = total_months

        if total_months > 12:
            bundle.compliance_load = f"Heavy: ~{total_months} months total application time"
        elif total_months > 6:
            bundle.compliance_load = f"Moderate: ~{total_months} months total application time"
        else:
            bundle.compliance_load = f"Light: ~{total_months} months total application time"

    # ------------------------------------------------------------
    # Step 3: 政策收入天花板
    # ------------------------------------------------------------

    def _calculate_ceiling(self, policies: list, bundles: list,
                            enterprise_profile: dict = None) -> PolicyCeiling:
        """计算政策收入天花板"""
        ceiling = PolicyCeiling()

        if enterprise_profile:
            basic = enterprise_profile.get("basic_info", {})
            ceiling.enterprise_name = basic.get("short_name", "")
            ceiling.enterprise_id = basic.get("enterprise_id", "")

        # 理论天花板: 所有政策的收益之和 (不考虑互斥)
        ceiling.theoretical_max = sum(
            p.get("benefit", 0) for p in policies
        )

        # 可行天花板: 最优组合的收益
        if bundles:
            best = max(bundles, key=lambda b: b.total_benefit)
            ceiling.feasible_max = best.total_benefit
            ceiling.best_bundle = best
        else:
            ceiling.feasible_max = 0

        # 按类型统计
        by_type = {}
        for p in policies:
            ptype = p.get("policy_type", "其他")
            if ptype not in by_type:
                by_type[ptype] = {"count": 0, "total_benefit": 0}
            by_type[ptype]["count"] += 1
            by_type[ptype]["total_benefit"] += p.get("benefit", 0)
        ceiling.by_type = by_type

        # 增量空间
        ceiling.incremental_space = max(0, ceiling.feasible_max - ceiling.existing_income)

        return ceiling

    # ------------------------------------------------------------
    # Step 4: 摘要生成
    # ------------------------------------------------------------

    def _generate_summary(self, bundles: list, ceiling: PolicyCeiling,
                           pairwise: dict) -> str:
        """生成一句话总结"""
        if not bundles:
            return "No policies available for stacking analysis"

        best = max(bundles, key=lambda b: b.combined_roi)
        n_total = len(pairwise) + 1 if pairwise else 0
        n_exclusive = sum(
            1 for v in pairwise.values() if v["rule"] == "exclusive"
        )
        n_complementary = sum(
            1 for v in pairwise.values() if v["rule"] == "complementary"
        )

        return (
            f"Best bundle: {best.name} ({len(best.policies)} policies, "
            f"ROI {best.combined_roi:.1f}x, benefit {best.total_benefit:.0f}wan). "
            f"Ceiling: {ceiling.feasible_max:.0f}wan "
            f"(theoretical {ceiling.theoretical_max:.0f}wan). "
            f"Pairs: {n_complementary} complementary, {n_exclusive} exclusive."
        )


# ============================================================
# 格式化输出
# ============================================================

def format_stacking_report(analysis: dict) -> str:
    """格式化政策组合叠加分析报告为 Markdown"""
    lines = [
        "## Policy Stacking Analysis",
        "",
    ]

    ceiling = analysis.get("ceiling")
    bundles = analysis.get("bundles", [])
    pairwise = analysis.get("pairwise", {})
    summary = analysis.get("summary", "")

    # 政策收入天花板
    if ceiling:
        lines.extend([
            "### Policy Income Ceiling",
            "",
            "| Metric | Value |",
            "|:-------|:------|",
            f"| Theoretical Max | {ceiling.theoretical_max:.0f} wan |",
            f"| Feasible Max | {ceiling.feasible_max:.0f} wan |",
            f"| Ceiling Utilization | {ceiling.feasible_max/max(ceiling.theoretical_max,1)*100:.0f}% |",
            f"| Incremental Space | {ceiling.incremental_space:.0f} wan |",
            "",
        ])

        # 按类型分解
        if ceiling.by_type:
            lines.append("**By Policy Type:**")
            lines.append("")
            lines.append("| Type | Count | Total Benefit |")
            lines.append("|:-----|:-----:|:-------------:|")
            for ptype, data in ceiling.by_type.items():
                lines.append(
                    f"| {ptype} | {data['count']} | {data['total_benefit']:.0f} wan |"
                )
            lines.append("")

    # 互斥关系
    if pairwise:
        exclusive_pairs = [
            (k, v) for k, v in pairwise.items() if v["rule"] == "exclusive"
        ]
        complementary_pairs = [
            (k, v) for k, v in pairwise.items() if v["rule"] == "complementary"
        ]

        if exclusive_pairs:
            lines.extend([
                "### Mutually Exclusive Policies",
                "",
            ])
            for (i, j), info in exclusive_pairs[:10]:  # 最多显示 10 条
                lines.append(f"- Policy #{i+1} <-> #{j+1}: {info['reason']}")
            lines.append("")

        if complementary_pairs:
            lines.extend([
                "### Complementary Policies",
                "",
            ])
            for (i, j), info in complementary_pairs[:10]:
                lines.append(f"- Policy #{i+1} <-> #{j+1}: {info['reason']}")
            lines.append("")

    # 候选组合方案
    if bundles:
        lines.extend([
            "### Recommended Bundles",
            "",
        ])
        for bundle in bundles:
            lines.extend([
                f"#### Bundle {bundle.bundle_id}: {bundle.name}",
                "",
                f"- **Policies**: {len(bundle.policies)}",
                f"- **Combined ROI**: {bundle.combined_roi:.1f}x",
                f"- **Total Benefit**: {bundle.total_benefit:.0f} wan",
                f"- **Total Cost**: {bundle.total_cost:.0f} wan",
                f"- **Overlap Reduction**: {bundle.overlap_reduction:.0f} wan",
                f"- **Risk**: {bundle.concentration_risk}",
                f"- **Compliance**: {bundle.compliance_load}",
                f"- **Recommendation**: {bundle.recommendation}",
                "",
            ])

            # 组合内政策明细
            if bundle.policies:
                lines.append("| # | Policy | Type | Individual ROI | Role |")
                lines.append("|:-:|:-------|:-----|:--------------:|:-----|")
                for idx, item in enumerate(bundle.policies, 1):
                    title = item.policy.get("title", "Unknown")[:40]
                    lines.append(
                        f"| {idx} | {title} | {item.policy_type} | "
                        f"{item.individual_roi:.1f}x | {item.stacking_role} |"
                    )
                lines.append("")

    # 总结
    if summary:
        lines.extend([
            "---",
            "",
            f"> **{summary}**",
            "",
        ])

    return "\n".join(lines)


# ============================================================
# 快捷入口
# ============================================================

def quick_stack(policies_with_roi: list, enterprise_profile: dict = None) -> str:
    """一步到位: 分析 + 格式化输出

    Args:
        policies_with_roi: [{"policy": {}, "roi_ratio": float, "benefit": float,
                             "cost": float, "policy_type": str, "recommendation": int}]
        enterprise_profile: 企业画像 (可选)

    Returns:
        Markdown 格式的分析报告
    """
    stacker = PolicyStacker()
    analysis = stacker.analyze(policies_with_roi, enterprise_profile)
    return format_stacking_report(analysis)
