---
name: "EcoPolicy-AI 经济政策分析技能"
description: "为企业执行政策四维匹配、ROI 财务测算、多政策互斥与堆叠优化分析，自动在企业工作区保存 Markdown 分析报告。"
tags: ["政策分析", "企业匹配", "ROI测算", "堆叠优化", "自动驾驶"]
version: "1.0.0"
---

# EcoPolicy-AI 经济政策分析技能手册

本技能指导 AI 助手使用本地 Python 计算引擎与数据库，为指定企业执行政策的四维匹配打分、财务 ROI 量化测算以及多政策叠加分析。

---

## 1. 适用场景 (When to Use)

当用户提出以下需求时，请启动本技能：
* “帮我看看这篇新政策，我们公司 [企业ID] 适合报吗？”
* “估算一下申报这项政策对我们公司的 ROI 和申报成本。”
* “如果我们要同时申报这几项政策，有冲突吗？最优的申报组合是什么？”
* “帮我批量扫描最近数据库里的最新匹配政策。”

---

## 2. 核心依赖与文件结构

* **核心执行器**: `policy_matcher_cli.py` (统一命令行工具)
* **企业画像目录**: `enterprises/{enterprise_id}/profile.yaml` (用于匹配与 ROI 测算的输入)
* **报告工作区**: `enterprises/{enterprise_id}/workspace/` (分析报告生成并保存的目录)

---

## 3. 工具使用说明 (CLI Skills)

你应当自动通过在终端执行以下 shell 命令来配合本技能的逻辑推理：

### 3.1 查询可用企业画像
在开始分析前，若不确定可用的企业 ID，请执行：
```bash
python policy_matcher_cli.py list
```

### 3.2 匹配单条政策并测算 ROI
传入企业 ID 与政策输入源进行四维匹配评分与 ROI 计算：
* **从网页链接匹配**：
  ```bash
  python policy_matcher_cli.py match --enterprise <企业ID> --url "<政策网页URL>" --report
  ```
* **解析本地文件匹配**：
  ```bash
  python policy_matcher_cli.py match --enterprise <企业ID> --file "<本地文件路径>" --report
  ```
* **直接比对粘贴文本**：
  ```bash
  python policy_matcher_cli.py match --enterprise <企业ID> --text "<政策正文>" --report
  ```
* **注意**：增加 `--report` 选项会触发系统在 `policy_data/reports/` 目录下自动生成匹配简报。

### 3.3 自动驾驶扫描模式 (Autopilot Scan)
如果想快速对本地数据库最近抓取的高分政策进行 AI 自动分析流，请执行：
```bash
python policy_matcher_cli.py agent-scan --enterprise <企业ID> --days 7
```
这会自动筛选评分大于等于 3 的政策，调用 AI 自动生成深度分析报告存入企业工作区。

---

## 4. AI 助手执行工作流 (Workflow Steps)

当你被要求执行经济政策分析时，请严格遵守以下步骤：

1. **确定企业 ID**：确认分析的企业 ID（如 `jyuh`）。若没有，使用 `list` 命令查询或引导用户新建画像。
2. **执行计算硬筛选**：根据政策输入方式，运行 `python policy_matcher_cli.py match` 命令。
3. **获取量化结果**：从命令输出（或 `policy_data/reports/` 生成的简报）中读取关键指标：
   * **四维评分**：Tech、Prod、Mkt、Cap 各自得分（0-5分）。
   * **成功概率**：硬性条件是否通过，成功概率百分比。
   * **量化 ROI**：预估收益（万）、申报成本、合规成本、回本周期、ROI 倍数。
4. **堆叠组合优化**：如果有 2 条或以上政策，运行 Stacking 计算，获取推荐的 Bundles（组合方案）与收入天花板上限。
5. **严禁数字幻觉**：报告中的匹配分数、ROI倍数、回本时间等所有数值**必须**来自 CLI 工具的输出，严禁自行胡乱编造。
6. **按照输出规范生成报告**：
   * 将报告保存至 `enterprises/{enterprise_id}/workspace/policy_analysis_YYYY-MM-DD_{政策名简写}.md`。
   * 必须包含标准的 YAML Frontmatter 元数据及 `> **一句话判断**`。
   * 禁用任何 emoji 图标，禁用 arrow 指示符 `->`（改用 `➔` 或文字描述），保持商务风格。
