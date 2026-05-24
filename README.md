# 经济政策分析专家系统 (EcoPolicy AI)

> AI Agent + 行业知识库 + 政策数据库 = 对话式专家系统。为任意企业/行业提供精准的政策匹配、机遇识别与行动建议。

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 核心功能

- **政策监控**：37 个国家数据源（国务院 API x 20 + 已验证 HTML x 5）+ 31 省级区域配置
- **智能匹配**：PolicyMatch Matrix 四维引擎（技术/生产/市场/资本），将政策与企业画像精准匹配
- **AI 深度分析**：六步标准工作流，从政策解读到行动清单的完整决策支持
- **多行业覆盖**：5 大产业分类（战略性新兴产业/未来产业/传统制造业/基础设施/三次产业），43 个子行业
- **7 大行业分析框架**：种业/制造业/数字经济/新能源/生物医药/新材料/煤炭能源/轻资产，每行业 40+ 专业关键词
- **轻资产适配**：支持平台型/SaaS/服务型企业，自动切换数字资产分析维度
- **区域扩展**：覆盖全国 31 个省级行政区（4 直辖市 + 22 省 + 5 自治区），三级链式抓取（国家/省/市）
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
cd policy_monitor && python main.py run

# 指定省市
python main.py run --region 湖北
python main.py run --region beijing

# 按产业分类筛选
python main.py run --industry strategic_emerging
```

### 3. 运行企业匹配

```bash
python enterprise_matcher.py --enterprise enterprises/{企业简称}/profile.yaml
```

### 4. 使用 AI 分析（对话驱动）

在任意支持文件对话的 AI 工具（牛马AI / Claude Code / Trae / WorkBuddy）中打开本项目文件夹，AI 会自动读取 `CLAUDE.md` 获得完整分析能力。

```
用户："帮我分析这个政策 [链接/PDF/文本]"
→ AI 自动执行六步工作流
→ 输出 .md 分析报告

用户："对 [具体业务] 有什么影响？"
→ 追问式深度分析
```

---

## 项目结构

```
EcoPolicy-AI/
├── CLAUDE.md                        AI 助手指令文件（核心）
│
├── config/                          框架配置
│   ├── company_profile_template.yaml    企业画像模板
│   ├── policy_matrix_generator.md       行业分析框架
│   └── output_standards.md              输出规范
│
├── policy_monitor/                  政策抓取工具
│   ├── main.py                          CLI 入口
│   ├── database.py                      SQLite 存储
│   ├── fetcher.py                       安全 HTTP 客户端
│   ├── matcher.py                       关键词匹配器
│   ├── config.yaml                      37 个数据源配置
│   ├── industries.yaml                  5 大产业分类 / 43 个子行业
│   ├── parsers/                         2 种解析器（API / HTML）
│   └── regions/                         31 省区域配置
│
├── enterprises/                     企业画像库
│   └── _template/                       空白模板
│
├── enterprise_matcher.py            企业匹配引擎（8 个行业维度）
├── report_generator.py              报告生成器（简报 + 深度分析模板）
├── batch_matcher.py                 批量匹配引擎（多企业 x 全量政策排行榜）
├── policy_tracker.py                政策历史版本追踪（变更检测 + 对比报告）
├── policy_stacker.py                政策组合叠加分析（互补/互斥检测 + 组合优化 + 收入天花板）
├── examples/                        示例产出（脱敏）
├── security_review.py               安全审查脚本
├── README.md / ROADMAP.md / project.md
└── requirements.txt / .gitignore
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

## 扩展指南

### 添加新省份

参考现有文件格式（如 `regions/beijing.yaml`）：

```yaml
name: "New Province"
aliases: ["alias1", "alias2", "pinyin"]
parent_province: null
sources:
  - name: "StateCouncil-ProvinceName"
    url: "https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_gwyzcwjk&q=ProvinceName&..."
    type: api
    enabled: true
```

### 添加新行业

编辑 `policy_monitor/industries.yaml`，在对应大类下新增子行业。

### 添加新数据源

编辑 `policy_monitor/config.yaml`，新增源配置。

---

## 安全策略

| 措施 | 实现 |
|:--|:--|
| **robots.txt 遵守** | 自动检测并遵守，被禁止的源自动跳过 |
| **请求限速** | 源间 30-60 秒随机延迟 |
| **无 JS 执行** | 纯 HTTP 请求，不执行 JavaScript |
| **无登录** | 所有数据源均为公开信息 |
| **容错隔离** | 单源失败不影响其他源抓取 |

---

## 技术栈

- **Python 3.12+**
- **requests** -- HTTP 客户端
- **beautifulsoup4** + **lxml** -- HTML 解析
- **PyYAML** -- 配置文件解析
- **SQLite** -- 本地数据存储

---

## 许可证

MIT License

---

## 路线图 (Roadmap)

### Phase 1：基础建设 [已完成]

- [x] 政策监控工具（抓取器 + 解析器 + 数据库）
- [x] 37 个国家数据源 + 31 省级区域配置
- [x] 产业分类体系（5 大类 / 43 个子行业）
- [x] 企业画像模板（10 大维度 + 轻资产适配）
- [x] 7 个行业专属分析框架（每个 40+ 关键词）
- [x] 标准分析工作流（6 步）
- [x] 输出规范（5/5 分制评分、P0/P1/P2 优先级）
- [x] CLI 英文化

### Phase 2：验证与优化 [已完成]

- [x] 多行业案例验证（5 个行业）
- [x] GitHub 仓库搭建并推送
- [x] +12 个政策数据源（药监局/医保局/数据局等）
- [x] 行业深度深挖 + 轻资产适配
- [x] 反馈机制 + 定时调度 + 安全审查脚本
- [x] 31 省数据源全覆盖
- [x] 多企业档案隔离验证（跨行业企业对比验证）
- [x] 匹配器 bug 修复（煤炭能源误判/种业单字符/地址截断/轻资产误判/关键词去重）

### Phase 2.5：架构精简 [已完成]

- [x] 删除 agent/ 整个模块（10 个文件），AI 对话引擎天然处理
- [x] 核心逻辑提升到根目录（enterprise_matcher.py + report_generator.py）
- [x] config/ 从 6 个文件精简为 3 个核心文件
- [x] 移除未使用的解析器（rss_parser + sitemap_parser）
- [x] 增强 CLAUDE.md（吸收 agent config + 使用指南 + 安全规则）

### Phase 3：Agent 增强 [已完成]

- [x] 多轮对话支持（context.py + chat.py，已实现）
- [x] 申报草稿自动生成（模板化框架 + 脱敏示例）
- [x] 批量匹配（batch_matcher.py：多企业 x 全量政策排行榜 + 汇总报告）
- [x] 政策历史版本对比（policy_tracker.py：快照追踪 + 变更检测 + 对比报告）
- [x] 政策组合叠加分析（policy_stacker.py：互补/互斥检测 + 3 策略组合优化 + 收入天花板）
- [x] 六层评价体系（v4.0）
  - [x] 维度评分 + ASCII 雷达图 + 可调权重
  - [x] 成功概率动态估算（8项资质 + 政策级别竞争度 + 行业热度修正）
  - [x] ROI 量化评估（按政策类型真实约束计算，64 行业基准）
  - [x] 提升路径自动生成 + 人工偏好过滤
  - [x] 快速淘汰机制（四维全零跳过深层分析）
  - [x] 不推荐原因自动生成
  - [x] 煤炭能源行业关键词扩展（+10 生态修复）

### Phase 4：界面与 API [计划中]

- [ ] Web UI
- [ ] REST API
- [ ] 邮件/微信通知

### Phase 5：社区与扩展 [计划中]

- [ ] 更多行业模板
- [ ] 多语言支持
- [ ] 插件架构
