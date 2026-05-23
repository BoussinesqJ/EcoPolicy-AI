# -*- coding: utf-8 -*-
"""
报告生成器

生成两种类型的文档:
  1. 匹配简报 (自动) - 结构化的政策 x 企业匹配结果
  2. 深度分析请求 (手动) - 引导 AI 执行六步工作流
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("agent.reporter")


class ReportGenerator:
    """报告生成器"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.reports_dir = self.base_dir / "policy_data" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_brief(self, match) -> str:
        """生成匹配简报 (.md)

        Args:
            match: MatchResult 对象

        Returns:
            生成的文件路径
        """
        # 生成文件名
        slug = self._slugify(match.policy_title)[:40]
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{match.enterprise_id}_{slug}_{date_str}_brief.md"
        filepath = self.reports_dir / filename

        content = self._render_brief(match)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"简报已生成: {filepath.name}")
        return str(filepath)

    def generate_deep_analysis_request(self, match, brief_path: str = None) -> str:
        """生成深度分析请求文件

        用户将此文件发送给 AI 助手，AI 按六步工作流执行分析。

        Returns:
            生成的文件路径
        """
        slug = self._slugify(match.policy_title)[:40]
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{match.enterprise_id}_{slug}_{date_str}_deep_analysis.md"
        filepath = self.reports_dir / filename

        content = self._render_deep_analysis_request(match, brief_path)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"深度分析请求已生成: {filepath.name}")
        return str(filepath)

    def _render_brief(self, m) -> str:
        """渲染匹配简报 Markdown"""
        now = datetime.now().strftime("%Y-%m-%d")

        # 硬性条件明细
        hard_rows = []
        for cond, detail in m.hard_conditions_detail.items():
            status = "通过" if detail.get("通过") else "未通过"
            hard_rows.append(f"| {cond} | {detail.get('说明', '')} | {status} |")
        hard_table = "\n".join(hard_rows) if hard_rows else "| - | 无硬性条件要求 | - |"

        # 匹配关键词
        kw_text = ", ".join(m.matched_keywords[:10]) if m.matched_keywords else "无"

        # 机会/风险
        opp_text = "\n".join(f"- {o}" for o in m.opportunities) if m.opportunities else "- 暂无明确机会识别"
        risk_text = "\n".join(f"- {r}" for r in m.risks) if m.risks else "- 暂无明显风险"

        return f"""---
title: "政策匹配简报 - {m.enterprise_name} x {m.policy_title[:30]}"
date: "{now}"
author: "EcoPolicy Agent"
status: "自动生成"
type: "匹配简报"
enterprise: "{m.enterprise_id}"
recommendation: "{m.recommendation}"
---

# 政策匹配简报

> **一句话判断**: {m.enterprise_name} 与「{m.policy_title[:40]}」匹配度 {m.recommendation}。

---

## 一、政策速览

| 项目 | 内容 |
|:------|:------|
| **政策名称** | {m.policy_title} |
| **发文来源** | {m.policy_source} |
| **发布日期** | {m.policy_date} |
| **原文链接** | [{m.policy_url[:60]}...]({m.policy_url}) |
| **Agent 优先级** | {m.urgency} |
| **匹配总分** | {m.score_total}/20 |

---

## 二、企业画像概要

| 项目 | 内容 |
|:------|:------|
| **企业名称** | {m.enterprise_name} |
| **企业 ID** | {m.enterprise_id} |
| **所属行业** | {m.enterprise_id} |

---

## 三、硬性条件比对

| 条件项 | 说明 | 判定 |
|:------|:------|:--:|
{hard_table}

> {"全部硬性条件通过" if m.hard_conditions_pass else "部分硬性条件未通过，需人工确认是否影响申报"}

---

## 四、PolicyMatch Matrix 四维评分

| 维度 | 评分 | 分析 |
|:------|:--:|:------|
| **Tech (技术端)** | {m.score_tech}/5 | {"高度相关" if m.score_tech >= 4 else "部分相关" if m.score_tech >= 2 else "关联度低"} |
| **Prod (生产端)** | {m.score_prod}/5 | {"高度相关" if m.score_prod >= 4 else "部分相关" if m.score_prod >= 2 else "关联度低"} |
| **Mkt (市场端)** | {m.score_mkt}/5 | {"高度相关" if m.score_mkt >= 4 else "部分相关" if m.score_mkt >= 2 else "关联度低"} |
| **Cap (资本端)** | {m.score_cap}/5 | {"高度相关" if m.score_cap >= 4 else "部分相关" if m.score_cap >= 2 else "关联度低"} |
| **总计** | **{m.score_total}/20** | **{m.recommendation}** |

---

## 五、机会与风险

### 机会

{opp_text}

### 风险

{risk_text}

---

## 六、匹配关键词

{kw_text}

---

## 七、建议下一步

{"### 生成深度分析报告" if m.recommendation_score >= 3 else "### 暂不推荐深入分析"}

{f"该政策与 {m.enterprise_name} 匹配度达到 **{m.recommendation}**，建议执行深度分析：" if m.recommendation_score >= 3 else f"该政策匹配度较低（{m.recommendation}），暂不建议投入分析资源。"}

1. 运行 `python -m agent.agent deep {m.policy_url_hash}` 生成深度分析请求
2. 将请求文件发送给 AI 助手，执行六步标准分析工作流
3. 根据分析结果决定是否申报

---

*本简报由 EcoPolicy Agent 自动生成。深度分析需人工触发。*
"""

    def _render_deep_analysis_request(self, m, brief_path: str = None) -> str:
        """渲染深度分析请求"""
        now = datetime.now().strftime("%Y-%m-%d")

        return f"""---
title: "深度分析请求 - {m.policy_title[:30]}"
date: "{now}"
author: "EcoPolicy Agent"
type: "深度分析请求"
enterprise: "{m.enterprise_id}"
---

# 深度分析请求

> **请将以下内容发送给 AI 助手（Claude/Trae/WorkBuddy），AI 将执行六步标准分析工作流。**

---

## 任务说明

AI 助手，请读取以下文件，然后执行 `系统配置/analysis_workflow.md` 中定义的六步标准分析工作流：

**必读文件**:
1. `CLAUDE.md` - 了解系统配置
2. `enterprises/{m.enterprise_id}/profile.yaml` - 企业画像
3. `系统配置/analysis_workflow.md` - 六步工作流
4. `系统配置/policy_matrix_generator.md` - 行业分析框架
5. `系统配置/output_standards.md` - 输出规范

**可选文件**（如需深度报告）:
6. `系统配置/agent_system_prompt.md` - Agent 系统提示词

---

## 政策信息

| 项目 | 内容 |
|:------|:------|
| **政策名称** | {m.policy_title} |
| **发文来源** | {m.policy_source} |
| **发布日期** | {m.policy_date} |
| **原文链接** | [{m.policy_url[:60]}...]({m.policy_url}) |

**政策摘要**:
{m.policy_summary if m.policy_summary else "（请从原文链接获取完整政策文本）"}

---

## 匹配简报摘要

| 维度 | 评分 |
|:------|:--:|
| Tech | {m.score_tech}/5 |
| Prod | {m.score_prod}/5 |
| Mkt | {m.score_mkt}/5 |
| Cap | {m.score_cap}/5 |
| 总计 | {m.score_total}/20 |
| 推荐 | {m.recommendation} |

**匹配关键词**: {", ".join(m.matched_keywords[:10])}

---

## 分析输出要求

请生成以下文件，保存到 `enterprises/{m.enterprise_id}/workspace/` 目录：

1. **政策分析报告** (`policy_analysis_{now}_{m.enterprise_id}.md`)
   - 按六步工作流完整执行
   - 5/5 分制评分
   - P0/P1/P2 行动清单

2. **（如需要）申报指南** 或 **退出路径方案**
   - 仅当政策涉及资金申报或政府投资时生成

---

## 注意事项

- 所有输出文件保存到 `enterprises/{m.enterprise_id}/workspace/` 目录
- 格式遵循 `系统配置/output_standards.md` 规范
- 评分遵循 PolicyMatch Matrix 四维框架
- 标注"建议咨询专业顾问"的事项不要给出法律/财务断言
"""

    def _slugify(self, text: str) -> str:
        """将中文标题转为文件名安全的 slug"""
        # 移除特殊字符
        text = re.sub(r'[^\w一-鿿\s-]', '', text)
        # 替换空格为下划线
        text = re.sub(r'\s+', '_', text)
        return text[:50] if text else "unnamed"
