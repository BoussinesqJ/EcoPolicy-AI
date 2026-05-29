# EcoPolicy-AI 路线图 (Roadmap)

**开发者**: [BoussinesqJ](https://github.com/BoussinesqJ)
**最后更新**: 2026-05-29

---

## Phase 1：基础建设 ✅

- [x] 政策监控工具（抓取器 + 解析器 + 数据库）
- [x] 37 个国家数据源（国务院 API x 32 + 已验证 HTML x 5）
- [x] 31 个省级区域配置（全部大陆省级行政区/直辖市/自治区）
- [x] 产业分类体系（5 大类 / 43 个子行业）
- [x] 企业匹配引擎 + 报告生成器（可独立运行）
- [x] 企业画像模板（10 大维度 + 轻资产商业模式字段）
- [x] 7 个行业专属分析框架（每个 40+ 关键词）
- [x] 标准分析工作流（6 步）
- [x] 输出规范（5/5 分制评分、P0/P1/P2 优先级、排版标准）
- [x] 3 份脱敏示例案例
- [x] CLI 英文化（所有终端输出改为英文，避免 GBK 编码乱码）

## Phase 2：验证与优化 ✅

- [x] 多行业案例验证（5 个行业：制造业、数字经济、新能源、生物医药、新材料）
- [x] GitHub 仓库搭建与首次推送
- [x] 扩展政策数据源（+12 个：药监局/医保局/数据局/央行/证监会/知识产权局/国资委/人社部/市场监管总局/教育部/文旅部/民政部）
- [x] 行业深度分析（7 个行业维度专属关键词体系，每个 40+ 关键词）
- [x] 轻资产行业适配（business_model 模块 + 数字资产维度）
- [x] 反馈机制（采纳/拒绝/结果追踪 + 准确度/实用性评分）
- [x] 定时调度集成（Python scheduler + Windows Task Scheduler + Linux cron）
- [x] 安全审查自动化（`security_review.py` 推送前自动审查）
- [x] 多企业档案隔离验证（跨行业企业对比验证）
- [x] 匹配器 bug 修复（煤炭能源误判/种业单字符/地址截断/轻资产误判/关键词去重）

## Phase 2.5：架构精简 ✅

- [x] 删除 agent/ 整个模块（10 个文件），AI 对话引擎天然处理
- [x] 核心逻辑提升到根目录（enterprise_matcher.py + report_generator.py）
- [x] config/ 从 6 个文件精简为 3 个核心文件
- [x] 移除未使用的解析器（rss_parser + sitemap_parser）
- [x] 增强 CLAUDE.md（吸收 agent config + 使用指南 + 安全规则）

## Phase 3：分析引擎增强 ✅

- [x] 多轮对话支持（context.py + chat.py，已实现）
- [x] 申报草稿自动生成（模板化框架 + 脱敏示例）
- [x] 批量匹配（batch_matcher.py：多企业 x 全量政策排行榜 + 汇总报告）
- [x] 政策历史版本对比（policy_tracker.py：快照追踪 + 变更检测 + 对比报告）
- [x] 政策组合叠加分析（policy_stacker.py：互补/互斥检测 + 3 策略组合优化 + 收入天花板）
- [x] 六层评价体系（v4.0）
  - [x] Layer 1 维度评分 + ASCII 雷达图
  - [x] Layer 2 可调权重（行业默认 + 用户偏好覆盖）
  - [x] Layer 3 成功概率估算（8 项动态资质评估 + 政策级别竞争度 + 行业热度修正）
  - [x] Layer 4 ROI 量化评估（按政策类型真实约束计算，64 个行业基准，拨改投=一次性注入）
  - [x] Layer 5 提升路径自动生成（差距分析 + 难度 + 时间 + 具体建议）
  - [x] Layer 6 人工偏好过滤（必选/可选/排除/ROI阈值/风险偏好）
  - [x] 快速淘汰机制（四维全零跳过 L3-L6）
  - [x] 不推荐原因自动生成（行业不匹配/硬性条件/关键维度缺失）
  - [x] 煤炭能源行业关键词扩展（+10 生态修复相关关键词）
  - [x] 政策命中率优化（单关键词搜索 + jieba分词 + 同义词扩展 + 多字段匹配）
  - [x] 数据源成功率 34% → 100%，命中率 9.5% → 51.3%

## Phase 3.5：用户上传与调度 ✅

- [x] Phase A: 用户上传政策匹配
  - [x] URL 解析（自动抓取网页内容，适配政府网站）
  - [x] 文件解析（PDF/Word/纯文本，多编码支持）
  - [x] 文本解析（直接粘贴政策内容）
  - [x] CLI 入口（policy_matcher_cli.py match 命令）
- [x] Phase B: 手动触发抓取 + 匹配
  - [x] scan 命令（触发 policy_monitor 抓取 + 企业匹配）
  - [x] 支持 --region 和 --industry 参数筛选
  - [x] 数据库新增 get_recent_policies 方法
- [x] Phase C: 定时扫描
  - [x] scheduler.py（Python 调度器，基于 schedule 库）
  - [x] config.yaml 新增 scheduler 配置段
  - [x] Windows Task Scheduler XML 生成
  - [x] Linux crontab 条目生成
  - [x] schedule 命令（--show/--install/--remove）

## Phase 4：Skill + Agent 双态架构 ✅

- [x] **Skill 模式 — REST API**
  - [x] FastAPI 服务端（skills_api/server.py）
  - [x] 完整 RESTful 接口（/api/skills/match, /api/skills/roi, /api/skills/stack 等）
  - [x] 动态企业画像创建接口（/api/skills/save_profile）
  - [x] 文件上传接口（/api/skills/upload_file）
  - [x] OpenAPI 规范自动导出（skills_openapi.json）
  - [x] Dify / Coze 一键导入
- [x] **Skill 模式 — MCP 协议**
  - [x] 零依赖 MCP 服务端（skills_api/mcp_server.py）
  - [x] JSON-RPC 2.0 over stdin/stdout
  - [x] OpenAI 函数 → MCP 工具自动转换
  - [x] Trae / Cursor 原生接入
  - [x] Windows GBK 编码安全处理
- [x] **Skill 模式 — IDE 原生 Skill**
  - [x] .trae/skills/ecopolicy-analysis/SKILL.md（Trae IDE）
  - [x] .codebuddy/skills/ecopolicy-analysis/SKILL.md（CodeBuddy / WorkBuddy）
  - [x] YAML Frontmatter 元数据 + 终端动作引导 + 数字幻觉消除
- [x] **Agent 模式 — ReAct 推理引擎**
  - [x] 大模型协议客户端（ai_agent/llm.py，OpenAI 格式，默认 DeepSeek）
  - [x] ReAct 自主控制环（ai_agent/analyst.py，Thought→Action→Observation）
  - [x] 交互对话终端（ai_agent/chat.py）
  - [x] 统一工具层（ai_agent/tools.py，API/MCP/Agent 三端共享）
  - [x] CLI 入口（policy_matcher_cli.py chat / agent-scan）
- [x] **基础设施增强**
  - [x] Pydantic 配置校验（config_schema.py）
  - [x] 自定义异常层级（exceptions.py）
  - [x] 结构化日志（log_config.py，UTF-8 安全，文件轮转）
  - [x] 安全扫描器升级（.gitignore 感知）
- [x] **测试与验证**
  - [x] 51 项自动化测试全部通过
  - [x] 安全审查 0 issues
  - [x] GitHub 推送（master 分支）

## Phase 4.5：夯实基础 ✅

- [x] **Sprint 1：Bug 修复 + 字段对齐**
  - [x] 修复 `policy_matcher_cli.py` --verbose 崩溃（logging 未导入）
  - [x] 修复 `enterprise_matcher.py` 不推荐原因永远为空（not v 判断错误）
  - [x] 修复企业画像字段错位（patents/establishment_date/has_production_base）
  - [x] 补全 config_schema.py 5 个缺失校验模块
  - [x] 清理死代码和文档不一致
- [x] **Sprint 2：测试补全（51 → 232 项）**
  - [x] test_database.py — 28 项（CRUD/去重/匹配存储/Agent日志/导出）
  - [x] test_roi_calculator.py — 22 项（政策分类/ROI计算/基准对比/报告格式化）
  - [x] test_policy_stacker.py — 28 项（叠加规则/相似度/组合分析/互斥检测）
  - [x] test_matcher_v4.py — 22 项（六层评价体系 v4.0 扩展功能）
  - [x] test_batch_matcher.py — 12 项（批量匹配引擎/筛选/报告/错误处理）
  - [x] test_policy_tracker.py — 25 项（快照/变更检测/通知/历史/统计/报告）
  - [x] test_report_generator.py — 22 项（简报/深度分析/雷达图/概率条）
  - [x] test_fetcher.py — 18 项（mock fetch/重试/robots/超时/错误处理）
  - [x] 覆盖 11 个核心模块，0 失败
- [x] **数据看板**
  - [x] Streamlit 4-Tab 看板（总览/政策明细/企业匹配/系统运行）
  - [x] 直接读取 SQLite，零侵入现有代码
- [x] **数据源扩展（v5.0 → v5.1）**
  - [x] 国务院 API body 全文搜索（searchfield=title → body，效果提升 12x）
  - [x] 产业专项关键词扩展（+13 个：新能源汽车/动力电池/集成电路等）
  - [x] HTML 源修复（发改委/农业农村部 CSS 选择器修复）
  - [x] 中国人大网独立数据源（npc_parser.py 专用解析器，+113 条法律法规）
  - [x] 行业标签关联（15 个行业源自动打标签，去重时合并 industry_tags）
  - [x] policies 表新增 industry_tags 字段（JSON 数组）
  - [x] 政策库 415 → 743 条（+79%），50 个有效源

## Phase 5：Web UI 与通知 [计划中]

- [ ] Selenium Headless Browser（解锁工信部/国资委等 JS 渲染站）
- [ ] Web 管理界面（Vue / React 前端 + FastAPI 后端）
- [ ] 政策推送通知（邮件 / 微信 / 企业微信 / 钉钉）
- [ ] PDF 报告生成（兼容中文 CJK）
- [ ] 用户权限管理与多租户支持

## Phase 6：社区与规模化 [计划中]

- [ ] 更多行业分析模板（医疗健康、物流、金融等）
- [ ] 更多省级数据源（社区贡献）
- [ ] 多语言支持（英文政策摘要）
- [ ] 插件化架构，支持自定义分析器
- [ ] Docker 容器化部署

---

## 参与贡献

请参阅 [README.md](README.md) 获取搭建指南。如有问题或建议，请提交 [Issue](https://github.com/BoussinesqJ/EcoPolicy-AI/issues)。

## 许可证

MIT

---

*最后更新: 2026-05-29*
