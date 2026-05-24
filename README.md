# 经济政策分析专家系统 (EcoPolicy AI)

> AI Agent + 行业知识库 + 政策数据库 = 对话式专家系统。为任意企业/行业提供精准的政策匹配、机遇识别与行动建议。

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 核心功能

- **政策监控**：自动抓取国家级政策源，支持 37+ 国家数据源（国务院 API × 32 + 已验证 HTML × 5）+ 31 省级区域数据源
- **智能匹配**：PolicyMatch Matrix 四维引擎（技术/生产/市场/资本），将政策与企业画像精准匹配
- **AI 深度分析**：六步标准工作流，从政策解读到行动清单的完整决策支持
- **多行业覆盖**：内置 5 大产业分类（战略性新兴产业/未来产业/传统制造业/基础设施/三次产业），43 个子行业
- **7 大行业分析框架**：种业/制造业/数字经济/新能源/生物医药/新材料/轻资产，每行业 40+ 专业关键词
- **轻资产适配**：支持平台型/SaaS/服务型企业，自动切换数字资产分析维度
- **区域扩展**：覆盖全国 31 个省级行政区（4 直辖市 + 22 省 + 5 自治区），三级链式抓取（国家→省→市）
- **反馈闭环**：简报审阅 → 采纳/拒绝 → 申报追踪 → 结果评分 → 持续优化
- **定时调度**：支持 Python 内置调度 / Windows Task Scheduler / Linux cron
- **安全合规**：robots.txt 遵守、限速抓取、无 JS 执行，零法律风险

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行政策监控

```bash
# 全国级别（37 个数据源）
python -m policy_monitor.main run

# 指定省市（覆盖全国 31 个省级行政区）
python -m policy_monitor.main run --region 湖北
python -m policy_monitor.main run --region beijing
python -m policy_monitor.main run --region 四川

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

### 4. 反馈管理

```bash
# 提交简报审阅反馈（采纳/拒绝）
python -m agent.agent feedback --policy-hash <hash> --enterprise <id> --action accepted

# 更新申报结果
python -m agent.agent outcome --policy-hash <hash> --enterprise <id> --result approved

# 事后评分（AI 准确性 + 分析有用性）
python -m agent.agent score --policy-hash <hash> --enterprise <id> --accuracy 4 --usefulness 5

# 查看反馈统计
python -m agent.agent feedback-stats
```

### 5. 定时调度

```bash
# Python 调度器（前台运行，每 6 小时）
python -m agent.agent schedule

# 每 12 小时运行一次
python -m agent.agent schedule --interval 12

# 查看调度状态
python -m agent.agent schedule-status

# 生成 Windows 计划任务命令
python -m agent.scheduler setup-windows

# 生成 Linux cron 命令
python -m agent.scheduler setup-cron
```

### 6. 新企业建档

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
│   ├── feedback.py              反馈管理器
│   ├── scheduler.py             定时调度器
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

已预配置 31 个省级行政区。如需添加，参考现有文件格式（如 `beijing.yaml`）：

```yaml
name: "New Province"
aliases: ["alias1", "alias2", "pinyin"]
parent_province: null
sources:
  - name: "StateCouncil-ProvinceName"
    url: "https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_gwyzcwjk&q=ProvinceName&..."
    type: api
    enabled: true
  - name: "Province Government"
    url: "https://www.province.gov.cn/"
    type: html
    selectors:
      list: ".list_content li a"
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

---

## 路线图 (Roadmap)

### Phase 1：基础建设 [已完成]

- [x] 政策监控工具（抓取器 + 解析器 + 数据库）
- [x] 37 个国家数据源（国务院 API x 32 + 已验证 HTML x 5）
- [x] 31 个省级区域配置（全部大陆省级行政区/直辖市/自治区）
- [x] 产业分类体系（5 大类 / 43 个子行业）
- [x] Agent 编排系统（扫描器 + 匹配器 + 简报生成器 + 通知器）
- [x] 企业画像模板（10 大维度 + 轻资产商业模式字段）
- [x] 7 个行业专属分析框架（每个 40+ 关键词）
- [x] 标准分析工作流（6 步）
- [x] 输出规范（5/5 分制评分、P0/P1/P2 优先级、商务简报排版）
- [x] 3 份脱敏示例报告
- [x] CLI 英文化（终端输出全部为英文，避免 GBK 编码乱码）

### Phase 2：验证与优化 [已完成]

- [x] 多行业案例验证（5 个行业：制造业、数字经济、新能源、生物医药、新材料）
- [x] GitHub 仓库搭建并首次推送
- [x] 扩展政策数据源（+12 个：药监局/医保局/数据局/央行/证监会/知识产权局/国资委/人社部/市场监管总局/教育部/文旅部/民政部）
- [x] 行业深度深挖（7 个行业维度专属关键词体系，每个 40+ 关键词）
- [x] 轻资产行业适配（business_model 模块 + 轻资产维度）
- [x] 反馈机制（采纳/拒绝追踪 + 结果记录 + 准确率评分）
- [x] 定时调度功能（Python scheduler + Windows Task Scheduler + Linux cron）
- [x] 安全审查自动化（`security_review.py`，推送前自动检查）
- [ ] 多企业档案隔离验证（第二家企业建档测试）

### Phase 3：Agent 增强 [计划中]

- [ ] 多轮对话支持（实现追问式深度分析）
- [ ] 申报草稿自动生成（可研报告大纲等）
- [ ] 批量匹配（一个企业同时匹配多条政策，按优先级排序）
- [ ] 政策历史版本对比与变化追踪
- [ ] 跨区域政策对比分析

### Phase 4：界面与 API [计划中]

- [ ] Web 仪表盘（Flask/FastAPI）
- [ ] REST API 供第三方系统接入
- [ ] 邮件 / 微信通知集成
- [ ] PDF 报告生成（支持中文渲染）

### Phase 5：社区与扩展 [计划中]

- [ ] 更多行业分析模板（医疗健康、物流、金融等）
- [ ] 更多省级数据源（社区贡献）
- [ ] 多语言支持（英文政策摘要）
- [ ] 插件架构（支持自定义分析器）
