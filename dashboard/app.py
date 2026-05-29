"""
EcoPolicy-AI 数据看板
Streamlit + Plotly 交互式可视化
启动: streamlit run dashboard/app.py
"""

import sqlite3
import json
import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# 配置
# ============================================================

st.set_page_config(
    page_title="EcoPolicy-AI 数据看板",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 数据库路径（相对于项目根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "policy_data" / "policies.db"

# ============================================================
# 数据读取（缓存）
# ============================================================

@st.cache_data(ttl=60)
def load_data():
    """从 SQLite 加载全部数据"""
    if not DB_PATH.exists():
        return None, None, None

    conn = sqlite3.connect(str(DB_PATH))

    df_policies = pd.read_sql("SELECT * FROM policies ORDER BY date DESC", conn)
    df_matches = pd.read_sql(
        """
        SELECT m.*, p.title AS policy_title, p.source, p.date AS policy_date
        FROM enterprise_matches m
        LEFT JOIN policies p ON m.policy_url_hash = p.url_hash
        ORDER BY m.score_total DESC
        """,
        conn,
    )
    df_runs = pd.read_sql("SELECT * FROM agent_runs ORDER BY started_at DESC", conn)
    conn.close()

    return df_policies, df_matches, df_runs


# ============================================================
# 侧边栏
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.title("EcoPolicy-AI")
        st.caption("经济政策分析专家系统")
        st.divider()

        if st.button("刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.markdown("**数据来源**")
        st.caption(f"数据库: `policy_data/policies.db`")

        if DB_PATH.exists():
            size_kb = DB_PATH.stat().st_size / 1024
            st.caption(f"大小: {size_kb:.1f} KB")
        else:
            st.warning("数据库文件不存在")

        st.divider()
        st.markdown("**快速链接**")
        st.page_link(
            "https://github.com/BoussinesqJ/EcoPolicy-AI",
            label="GitHub 仓库",
            icon=":material/code:",
        )


# ============================================================
# Tab 1: 总览
# ============================================================

def tab_overview(df_policies, df_matches):
    st.header("总览")

    # ---- KPI 指标卡片 ----
    c1, c2, c3, c4 = st.columns(4)

    total_policies = len(df_policies)
    p0_count = len(df_policies[df_policies["priority"] == "P0"]) if len(df_policies) > 0 else 0
    total_matches = len(df_matches)
    avg_score = (
        df_matches["score_total"].mean() if len(df_matches) > 0 else 0
    )

    c1.metric("政策总数", total_policies)
    c2.metric("P0 告急", p0_count, delta=None, delta_color="inverse")
    c3.metric("已匹配", total_matches)
    c4.metric("平均匹配分", f"{avg_score:.1f}" if total_matches > 0 else "—")

    st.divider()

    # ---- 优先级分布 + 数据源分布 ----
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("优先级分布")
        if len(df_policies) > 0:
            priority_counts = df_policies["priority"].value_counts().reset_index()
            priority_counts.columns = ["优先级", "数量"]
            priority_colors = {"P0": "#ef4444", "P1": "#f97316", "P2": "#9ca3af"}
            fig_pie = px.pie(
                priority_counts,
                names="优先级",
                values="数量",
                color="优先级",
                color_discrete_map=priority_colors,
                hole=0.5,
            )
            fig_pie.update_layout(
                showlegend=True,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("暂无政策数据")

    with col_right:
        st.subheader("数据源分布")
        if len(df_policies) > 0:
            source_counts = df_policies["source"].value_counts().reset_index()
            source_counts.columns = ["数据源", "数量"]
            # 截断过长的源名
            source_counts["数据源"] = source_counts["数据源"].str[:12]
            fig_bar = px.bar(
                source_counts,
                x="数据源",
                y="数量",
                color="数量",
                color_continuous_scale="Blues",
            )
            fig_bar.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("暂无数据源数据")

    # ---- 抓取时间线 ----
    st.subheader("抓取时间线")
    if len(df_policies) > 0 and "fetched_at" in df_policies.columns:
        df_policies["fetch_date"] = pd.to_datetime(
            df_policies["fetched_at"], errors="coerce"
        ).dt.date
        timeline = (
            df_policies.groupby("fetch_date")
            .size()
            .reset_index(name="新增数量")
            .sort_values("fetch_date")
        )
        fig_line = px.line(
            timeline,
            x="fetch_date",
            y="新增数量",
            markers=True,
            labels={"fetch_date": "日期"},
        )
        fig_line.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=250,
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("暂无时间线数据")


# ============================================================
# Tab 2: 政策明细
# ============================================================

def tab_policies(df_policies):
    st.header("政策明细")

    if len(df_policies) == 0:
        st.info("数据库中暂无政策数据，请先运行政策抓取: `cd policy_monitor && python main.py run`")
        return

    # ---- 侧边栏筛选（在这个 tab 内渲染到 sidebar） ----
    with st.sidebar:
        st.subheader("筛选条件")
        selected_priorities = st.multiselect(
            "优先级",
            options=["P0", "P1", "P2"],
            default=["P0", "P1", "P2"],
        )
        selected_sources = st.multiselect(
            "数据源",
            options=sorted(df_policies["source"].dropna().unique().tolist()),
            default=sorted(df_policies["source"].dropna().unique().tolist()),
        )
        search_keyword = st.text_input("关键词搜索", placeholder="输入关键词...")
        max_rows = st.slider("显示行数", 5, 100, 20)

    # ---- 筛选逻辑 ----
    df = df_policies.copy()
    if selected_priorities:
        df = df[df["priority"].isin(selected_priorities)]
    if selected_sources:
        df = df[df["source"].isin(selected_sources)]
    if search_keyword:
        mask = df["title"].str.contains(search_keyword, case=False, na=False) | df[
            "summary"
        ].str.contains(search_keyword, case=False, na=False)
        df = df[mask]

    st.caption(f"共 {len(df)} 条政策（筛选后）")

    # ---- 表格 ----
    display_cols = ["title", "date", "source", "priority", "score", "summary"]
    available_cols = [c for c in display_cols if c in df.columns]
    df_display = df[available_cols].head(max_rows).copy()

    col_rename = {
        "title": "标题",
        "date": "日期",
        "source": "来源",
        "priority": "优先级",
        "score": "匹配分",
        "summary": "摘要",
    }
    df_display = df_display.rename(columns=col_rename)

    # 截断摘要
    if "摘要" in df_display.columns:
        df_display["摘要"] = df_display["摘要"].str[:80].fillna("—")

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=min(40 * len(df_display) + 40, 500),
    )

    # ---- 关键词云 ----
    st.subheader("高频匹配关键词")
    all_keywords = []
    for kw_str in df_policies["keywords_matched"].dropna():
        try:
            kw_list = json.loads(kw_str)
            if isinstance(kw_list, list):
                all_keywords.extend(kw_list)
        except (json.JSONDecodeError, TypeError):
            pass

    if all_keywords:
        kw_counts = pd.Series(all_keywords).value_counts().head(20).reset_index()
        kw_counts.columns = ["关键词", "命中次数"]
        fig_kw = px.bar(
            kw_counts,
            x="关键词",
            y="命中次数",
            color="命中次数",
            color_continuous_scale="Teal",
        )
        fig_kw.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig_kw, use_container_width=True)
    else:
        st.info("暂无匹配关键词数据")


# ============================================================
# Tab 3: 企业匹配
# ============================================================

def tab_matches(df_matches):
    st.header("企业匹配分析")

    if len(df_matches) == 0:
        st.info("暂无匹配数据，请先运行企业匹配: `python enterprise_matcher.py`")
        return

    # ---- 企业选择 ----
    enterprises = sorted(df_matches["enterprise_id"].unique().tolist())
    selected_ent = st.selectbox("选择企业", enterprises)
    df_ent = df_matches[df_matches["enterprise_id"] == selected_ent]

    # ---- 四维雷达图 ----
    st.subheader("四维匹配雷达图")
    tech_avg = df_ent["score_tech"].mean()
    prod_avg = df_ent["score_prod"].mean()
    mkt_avg = df_ent["score_mkt"].mean()
    cap_avg = df_ent["score_cap"].mean()

    categories = ["Tech (技术)", "Prod (生产)", "Mkt (市场)", "Cap (资本)"]
    values = [tech_avg, prod_avg, mkt_avg, cap_avg]
    # 闭合雷达图
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            name=selected_ent,
            line=dict(color="#6366f1"),
            fillcolor="rgba(99,102,241,0.2)",
        )
    )
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
        showlegend=False,
        margin=dict(t=30, b=30),
        height=400,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # ---- 推荐等级 + 匹配排行 ----
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("推荐等级分布")
        if "recommendation" in df_ent.columns:
            rec_counts = df_ent["recommendation"].value_counts().reset_index()
            rec_counts.columns = ["推荐等级", "数量"]
            fig_rec = px.bar(
                rec_counts,
                x="推荐等级",
                y="数量",
                color="推荐等级",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_rec.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
            )
            st.plotly_chart(fig_rec, use_container_width=True)

    with col_right:
        st.subheader("匹配排行")
        rank_cols = [
            "policy_title",
            "score_total",
            "score_tech",
            "score_prod",
            "score_mkt",
            "score_cap",
            "urgency",
            "policy_date",
        ]
        available = [c for c in rank_cols if c in df_ent.columns]
        df_rank = df_ent[available].copy()
        col_rename = {
            "policy_title": "政策",
            "score_total": "总分",
            "score_tech": "Tech",
            "score_prod": "Prod",
            "score_mkt": "Mkt",
            "score_cap": "Cap",
            "urgency": "紧急度",
            "policy_date": "日期",
        }
        df_rank = df_rank.rename(columns=col_rename)
        st.dataframe(df_rank, use_container_width=True, hide_index=True, height=350)

    # ---- 概率 vs ROI 散点图 ----
    if "success_probability" in df_ent.columns and "roi_ratio" in df_ent.columns:
        st.subheader("成功概率 vs ROI")
        df_scatter = df_ent[
            ["policy_title", "success_probability", "roi_ratio", "recommendation"]
        ].copy()
        df_scatter["success_probability"] = pd.to_numeric(
            df_scatter["success_probability"], errors="coerce"
        )
        df_scatter["roi_ratio"] = pd.to_numeric(
            df_scatter["roi_ratio"], errors="coerce"
        )
        df_scatter = df_scatter.dropna()

        if len(df_scatter) > 0:
            fig_scatter = px.scatter(
                df_scatter,
                x="success_probability",
                y="roi_ratio",
                color="recommendation",
                hover_name="policy_title",
                labels={
                    "success_probability": "成功概率",
                    "roi_ratio": "ROI 比率",
                },
                color_discrete_sequence=px.colors.qualitative.Set1,
            )
            fig_scatter.update_layout(
                margin=dict(t=20, b=20),
                height=350,
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("暂无有效概率/ROI 数据")


# ============================================================
# Tab 4: 系统运行
# ============================================================

def tab_system(df_runs):
    st.header("系统运行")

    # ---- Agent 运行历史 ----
    st.subheader("运行历史")
    if len(df_runs) > 0:
        display_cols = [
            "id",
            "run_type",
            "started_at",
            "finished_at",
            "status",
            "policies_scanned",
            "policies_new",
            "matches_found",
            "briefs_generated",
        ]
        available = [c for c in display_cols if c in df_runs.columns]
        df_runs_display = df_runs[available].copy()
        col_rename = {
            "id": "ID",
            "run_type": "类型",
            "started_at": "开始时间",
            "finished_at": "结束时间",
            "status": "状态",
            "policies_scanned": "扫描数",
            "policies_new": "新增数",
            "matches_found": "匹配数",
            "briefs_generated": "简报数",
        }
        df_runs_display = df_runs_display.rename(columns=col_rename)
        st.dataframe(df_runs_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无运行记录")

    st.divider()

    # ---- 数据库信息 ----
    st.subheader("数据库信息")
    if DB_PATH.exists():
        size_kb = DB_PATH.stat().st_size / 1024
        st.metric("数据库大小", f"{size_kb:.1f} KB")

        conn = sqlite3.connect(str(DB_PATH))
        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table'", conn
        )
        for _, row in tables.iterrows():
            table_name = row["name"]
            count = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table_name}", conn)[
                "cnt"
            ].iloc[0]
            st.text(f"  {table_name}: {count} 条记录")
        conn.close()
    else:
        st.warning("数据库文件不存在")

    # ---- 项目路径 ----
    st.divider()
    st.subheader("项目信息")
    st.code(f"项目根目录: {PROJECT_ROOT}", language="text")
    st.code(f"数据库路径: {DB_PATH}", language="text")


# ============================================================
# 主程序
# ============================================================

def main():
    render_sidebar()

    st.title("EcoPolicy-AI 数据看板")
    st.caption("经济政策分析专家系统 - 数据可视化")

    df_policies, df_matches, df_runs = load_data()

    if df_policies is None:
        st.error(
            "无法连接数据库，请确认 `policy_data/policies.db` 存在。\n\n"
            "首次使用请运行：\n"
            "```bash\n"
            "cd policy_monitor && python main.py run\n"
            "```"
        )
        return

    tab1, tab2, tab3, tab4 = st.tabs(["总览", "政策明细", "企业匹配", "系统运行"])

    with tab1:
        tab_overview(df_policies, df_matches)
    with tab2:
        tab_policies(df_policies)
    with tab3:
        tab_matches(df_matches)
    with tab4:
        tab_system(df_runs)


if __name__ == "__main__":
    main()
