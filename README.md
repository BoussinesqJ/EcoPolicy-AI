# 经济政策分析专家系统 (EcoPolicy-AI)

> AI Agent + Skill 双态架构 | 行业知识库 + 政策数据库 = 对话式政策分析专家系统。
> 为任意企业/行业提供精准的政策匹配、机遇识别与行动建议。

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-51%20passed-brightgreen.svg)]()

**开发者**: [BoussinesqJ](https://github.com/BoussinesqJ)
**最后更新**: 2026-05-26

---

## 核心功能

- **政策监控**：47 个国家数据源（国务院 API x 32 + 部委 API x 10 + 已验证 HTML x 5）+ 31 省级区域配置
- **智能匹配**：PolicyMatch Matrix 四维引擎（技术/生产/市场/资本），将政策与企业画像精准匹配
- **AI 深度分析**：六步标准工作流，从政策解读到行动清单的完整决策支持
- **多行业覆盖**：5 大产业分类，43 个子行业，7 大行业分析框架（每行业 40+ 专业关键词）
- **双态架构**：Skill 模式（REST API + MCP）与 Agent 模式（ReAct 自主推理）双形态运行
- **IDE 原生集成**：支持 Trae / CodeBuddy / WorkBuddy 等国产 IDE 的原生 Skill 手册
- **区域扩展**：覆盖全国 31 个省级行政区（4 直辖市 + 22 省 + 5 自治区），三级链式抓取（国家/省/市）
- **安全合规**：robots.txt 遵守、限速抓取、无 JS 执行，零法律风险

---

## 双态架构

EcoPolicy-AI 同时支持两种运行形态：

### 🔧 Skill 模式（被调用）

作为工具被外部系统（Dify / Coze / Trae / WorkBuddy）调用：

| 集成方式 | 适用场景 | 启动命令 |
|----------|----------|----------|
| **REST API** | Dify / Coze 等 Agent 平台 | `python policy_matcher_cli.py server` |
| **MCP 协议** | Trae / Cursor 等 IDE | `python policy_matcher_cli.py mcp` |
| **IDE Skill 手册** | Trae / CodeBuddy 本地开发 | 自动识别 `.trae/skills/` 目录 |

### 🤖 Agent 模式（自主推理）

内置 ReAct 推理引擎，自主完成政策分析全流程：

```bash
# 交互式对话
python policy_matcher_cli.py chat -e jyuh

# 自动驾驶扫描（无需人工干预）
python policy_matcher_cli.py agent-scan -e jyuh -d 30
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 政策监控（抓取 + 匹配）

```bash
# 全国级别（47 个数据源）
cd policy_monitor && python main.py run

# 指定省市
python main.py run --region 湖北

# 按产业分类筛选
python main.py run --industry strategic_emerging
```

### 3. 企业匹配

```bash
python enterprise_matcher.py --enterprise enterprises/{企业简称}/profile.yaml
```

### 4. Skill 模式

```bash
# 启动 REST API 服务（Dify/Coze 集成）
python policy_matcher_cli.py server

# 启动 MCP 服务（Trae/Cursor 集成）
python policy_matcher_cli.py mcp

# 导出 OpenAPI 规范
python skills_api/export_openapi.py
```

### 5. Agent 模式（对话驱动）

```bash
# 设置 LLM API Key
set OPENAI_API_KEY=your-api-key       # Windows
export OPENAI_API_KEY=your-api-key    # Linux/Mac

# 交互式对话
python policy_matcher_cli.py chat -e jyuh

# 自动扫描报告
python policy_matcher_cli.py agent-scan -e jyuh
```

### 6. 用户上传政策匹配

```bash
# URL 解析
python policy_matcher_cli.py match -e jyuh --url https://example.gov.cn/policy/001

# 文件解析
python policy_matcher_cli.py match -e jyuh --file policy.txt

# 文本解析
python policy_matcher_cli.py match -e jyuh --text "关于加快推进人工智能..."
```

---

## 项目结构

```
EcoPolicy-AI/
├── policy_matcher_cli.py            CLI 统一入口（所有模式）
├── enterprise_matcher.py            企业匹配引擎（8 个行业维度）
├── security_review.py               安全审查脚本（.gitignore 感知）
│
├── ai_agent/                        智能体模块（Agent 模式）
│   ├── llm.py                          大模型协议客户端（OpenAI 格式）
│   ├── tools.py                        统一工具层（API/MCP/Agent 共享）
│   ├── analyst.py                      ReAct 自主控制环
│   └── chat.py                         交互对话终端
│
├── skills_api/                      技能服务模块（Skill 模式）
│   ├── server.py                       FastAPI REST 服务端
│   ├── mcp_server.py                   MCP JSON-RPC 2.0 服务端
│   └── export_openapi.py              OpenAPI 导出工具
│
├── policy_monitor/                  政策抓取工具
│   ├── main.py                         CLI 入口
│   ├── database.py                     SQLite 存储
│   ├── fetcher.py                      安全 HTTP 客户端
│   ├── matcher.py                      关键词匹配器（jieba 分词 + 同义词）
│   ├── config.yaml                     47 个数据源配置
│   ├── industries.yaml                 5 大产业分类 / 43 个子行业
│   ├── parsers/                        3 种解析器（API / HTML / 用户上传）
│   └── regions/                        31 省区域配置
│
├── config/                          框架配置
│   ├── company_profile_template.yaml   企业画像模板
│   ├── policy_matrix_generator.md      行业分析框架
│   └── output_standards.md             输出规范
│
├── enterprises/                     企业画像库（gitignored）
│   └── _template/                      空白模板
│
├── .trae/skills/                    Trae IDE 原生技能手册
├── .codebuddy/skills/               CodeBuddy/WorkBuddy 原生技能手册
│
├── tests/                           测试套件（51 用例）
│   ├── conftest.py                     公共 fixtures
│   ├── test_enterprise_matcher.py      匹配引擎测试
│   ├── test_parsers.py                 解析器测试
│   └── test_skills_api.py             REST/MCP API 测试
│
├── config_schema.py                 Pydantic 配置校验
├── exceptions.py                    自定义异常层级
├── log_config.py                    结构化日志（UTF-8 安全）
├── scheduler.py                     后台调度器
├── skills_openapi.json              OpenAPI 规范定义
├── report_generator.py              报告生成器
├── batch_matcher.py                 批量匹配引擎
├── policy_tracker.py                政策版本追踪
├── policy_stacker.py                政策组合叠加分析
├── CLAUDE.md                        AI 助手指令文件
├── requirements.txt                 依赖清单
├── ROADMAP.md                       路线图
└── .gitignore                       安全排除规则
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

1. **战略性新兴产业**（九大领域）+ 六大新兴支柱产业
2. **未来产业**：量子科技、生物制造、绿色氢能、脑机接口、具身智能、6G
3. **传统制造业**：石化化工、钢铁、有色、建材、机械等
4. **基础设施产业**：水网、电网、算力网、新型通信网、城市地下管网、物流网
5. **三次产业**（宏观统计分类）

### 六步标准工作流

```
Step 1: 政策录入 -> Step 2: 画像匹配 -> Step 3: 多维拆解
-> Step 4: 赛道设计 -> Step 5: 行动清单 -> Step 6: 深度报告
```

---

## 配置指南

| 文件 | 用途 | 何时修改 |
|:--|:--|:--|
| `policy_monitor/config.yaml` | 数据源配置 | 添加/禁用数据源 |
| `policy_monitor/industries.yaml` | 产业分类关键词 | 添加新行业 |
| `policy_monitor/regions/*.yaml` | 省市级数据源 | 添加新省市 |
| `config/company_profile_template.yaml` | 企业画像模板 | 自定义画像维度 |
| `config/output_standards.md` | 输出格式规范 | 调整报告样式 |

---

## 安全策略

| 措施 | 实现 |
|:--|:--|
| **robots.txt 遵守** | 自动检测并遵守，被禁止的源自动跳过 |
| **请求限速** | 源间 30-60 秒随机延迟 |
| **无 JS 执行** | 纯 HTTP 请求，不执行 JavaScript |
| **无登录** | 所有数据源均为公开信息 |
| **容错隔离** | 单源失败不影响其他源抓取 |
| **推送前审查** | `security_review.py` 自动扫描（.gitignore 感知） |

---

## 技术栈

- **Python 3.12+**
- **FastAPI** + **Uvicorn** — REST API 服务
- **Pydantic** — 配置校验与数据模型
- **requests** — HTTP 客户端
- **beautifulsoup4** + **lxml** — HTML 解析
- **jieba** — 中文分词
- **PyYAML** — 配置文件解析
- **SQLite** — 本地数据存储
- **pytest** — 测试框架

---

## 许可证

MIT License

---

## 开发者

- **BoussinesqJ** — [GitHub](https://github.com/BoussinesqJ)

如有问题或建议，请提交 [Issue](https://github.com/BoussinesqJ/EcoPolicy-AI/issues)。

---

*最后更新: 2026-05-26*
