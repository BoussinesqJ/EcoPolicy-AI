# 企业画像库

本目录存放企业的结构化画像文件，供 Agent 匹配引擎使用。

## 使用方法

1. 复制 `_template/profile.yaml` 为 `{企业简称}_profile.yaml`
2. 按照模板填入企业数据（标注 `[必填]` 的必须填写）
3. 将文件放入 `enterprises/` 目录下，Agent 系统会自动加载

## 文件格式

使用 YAML 格式，包含 10 大维度：

| 维度 | 字段 | 必填 |
|:--|:--|:--:|
| 基本信息 | name, unified_code, registered_capital, employees,成立_year | 是 |
| 行业分类 | industry_tags, sub_industry | 是 |
| 资质资产 | certifications, honors | 否 |
| 技术创新 | patents, r_and_d, platforms | 否 |
| 生产运营 | production_base, production_capacity | 否 |
| 财务状况 | revenue_trend, profit_margin, tax_amount | 否 |
| 区域布局 | headquarters, markets, key_regions | 是 |
| 社会价值 | employment, social_impact, tax_contribution | 否 |
| 战略规划 | vision, strategy_focus | 否 |
| 资本状态 | listing_status, financing_history | 否 |
