# 经济政策智能分析系统 (EcoPolicy AI)

> 为任意企业/行业提供精准的政策匹配、机遇识别与行动建议的 AI 分析平台。

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 核心功能

- **政策监控**：自动抓取国家级/省级/市州级政策源，支持 25+ 数据源（API + RSS + HTML）
- **智能匹配**：PolicyMatch Matrix 四维引擎（技术/生产/市场/资本），将政策与企业画像精准匹配
- **AI 深度分析**：六步标准工作流，从政策解读到行动清单的完整决策支持
- **多行业覆盖**：内置 5 大产业分类（战略性新兴产业/未来产业/传统制造业/基础设施/三次产业），43 个子行业
- **区域扩展**：三级抓取模式（国家→省→市），配置即用，支持任意省市
- **安全合规**：robots.txt 遵守、限速抓取、无 JS 执行，零法律风险

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行政策监控

```bash
# 全国级别（25 个数据源）
python -m policy_monitor.main run

# 指定省市
python -m policy_monitor.main run --region 湖北

# 按产业分类筛选
python -m agent.agent run --industry strategic_emerging
```

### 3. 使用 Agent 分析

```bash
# 查看系统状态
python -m agent.agent status

# 查看已注册企业
python -m agent.agent enterprises

# 运行完整流程（扫描 → 匹配 → 简报 → 通知）
python -m agent.agent run

# 仅执行匹配
python -m agent.agent match
```

### 4. 新企业建档

复制 `enterprises/_template/profile.yaml`，填入企业数据，放入 `enterprises/` 目录即可。

---

## 项目结构

```
EcoPolicy-AI/
├── agent/                     Agent 编排系统
│   ├── agent.py                 主编排器 (CLI 入口)
│   ├── scanner.py               政策扫描器
│   ├── enterprise_matcher.py    企业匹配引擎
│   ├── report_generator.py      报告生成器
│   ├── agent_notifier.py        通知器
│   └── state.py                 状态管理
│
├── policy_monitor/            政策监控爬虫
│   ├── main.py                  CLI 入口
│   ├── database.py              SQLite 存储
│   ├── fetcher.py               安全 HTTP 客户端
│   ├── matcher.py               关键词匹配器
│   ├── parsers/                 4 种解析器（API/RSS/HTML/Sitemap）
│   ├── regions/                 省市级数据源配置
│   ├── config.yaml              数据源配置
│   └── industries.yaml          产业分类体系
│
├── config/                    系统框架配置
│   ├── company_profile_template.yaml  企业画像模板
│   ├── policy_matrix_generator.md     行业分析框架
│   ├── analysis_workflow.md           六步标准工作流
│   ├── output_standards.md            输出规范
│   ├── agent_system_prompt.md         Agent 系统提示词
│   └── policy_sources_catalog.md      政策源清单
│
├── enterprises/               企业画像库
│   └── _template/               空白模板
│
├── examples/                  示例产出（脱敏）
├── CLAUDE.md                  AI 助手指令文件
└── project.md                 项目计划文档
```

---

## 核心概念

### PolicyMatch Matrix（政策匹配矩阵）

四维分析框架，根据企业行业自动适配分析要素：

| 维度 | 含义 | 示例（种业） |
|:--|:--|:--|
| **Tech**（技术端） | 政策对技术创新的支持力度 | 生物育种、种质资源创新 |
| **Prod**（生产端） | 对生产运营条件的改善程度 | 制种基地土地/水利/保险 |
| **Mkt**（市场端） | 对市场准入和补贴的贡献 | 良种补贴、推广政策 |
| **Cap**（资本端） | 对融资和资本路径的影响 | IPO、产业基金、股权融资 |

### 产业分类体系

基于国家统计局《工业战略性新兴产业分类目录（2023）》，覆盖五大类：

1. **战略性新兴产业**（九大领域）：新一代信息技术、生物技术、新能源、新材料等
2. **六大新兴支柱产业**：集成电路、航空航天、生物医药、低空经济、新型储能、智能机器人
3. **未来产业**：量子科技、生物制造、绿色氢能、脑机接口、具身智能、6G
4. **传统制造业**：石化化工、钢铁、有色、建材、机械等
5. **基础设施产业**：水网、电网、算力网、新型通信网、城市地下管网、物流网

### 六步标准工作流

```
Step 1: 政策录入 → Step 2: 画像匹配 → Step 3: 多维拆解
→ Step 4: 赛道设计 → Step 5: 行动清单 → Step 6: 深度报告
```

---

## 配置指南

| 文件 | 用途 | 何时需要修改 |
|:--|:--|:--|
| `policy_monitor/config.yaml` | 数据源配置 | 添加/禁用数据源 |
| `policy_monitor/industries.yaml` | 产业分类关键词 | 添加新行业 |
| `policy_monitor/regions/*.yaml` | 省市级数据源 | 添加新省市 |
| `agent/config.yaml` | Agent 运行参数 | 调整匹配阈值/通知方式 |
| `config/company_profile_template.yaml` | 企业画像模板 | 自定义画像维度 |
| `config/output_standards.md` | 输出格式规范 | 调整报告样式 |

---

## 扩展指南

### 添加新省份

在 `policy_monitor/regions/` 下新建 YAML 文件，参考 `hubei.yaml` 格式：

```yaml
name: "四川省"
aliases: ["四川", "川", "蜀"]
sources:
  - name: "四川省发改委"
    type: "rss"
    url: "https://example.gov.cn/rss"
    enabled: true
```

### 添加新行业

编辑 `policy_monitor/industries.yaml`，在对应大类下新增子行业：

```yaml
strategic_emerging:
  sub_industries:
    - name: "my_new_industry"
      display_name: "新行业名称"
      keywords_high: ["关键词1", "关键词2"]
      keywords_medium: ["相关词1"]
      related_departments: ["相关部委"]
```

### 添加新数据源

编辑 `policy_monitor/config.yaml`，新增源配置：

```yaml
sources:
  - name: "新源名称"
    type: "api"  # api | rss | html | sitemap
    url: "https://..."
    search_keywords: ["关键词"]
    enabled: true
```

---

## 安全策略

| 措施 | 实现 |
|:--|:--|
| **robots.txt 遵守** | 自动检测并遵守，被禁止的源自动跳过 |
| **请求限速** | 源间 30-60 秒随机延迟 |
| **User-Agent** | 使用标准浏览器 UA，非爬虫特征 |
| **无 JS 执行** | 纯 HTTP 请求，不执行 JavaScript |
| **无登录** | 所有数据源均为公开信息 |
| **容错隔离** | 单源失败不影响其他源抓取 |

---

## 技术栈

- **Python 3.12+**
- **requests** — HTTP 客户端
- **beautifulsoup4** + **lxml** — HTML 解析
- **PyYAML** — 配置文件解析
- **SQLite** — 本地数据存储

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。
