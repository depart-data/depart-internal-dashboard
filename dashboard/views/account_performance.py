"""
dashboard/pages/account_performance.py

"계정 성과" 페이지 — ig_insights_total 기준 팔로워 스냅샷/팔로우/언팔로우 추이.
날짜 필터는 이 페이지의 모든 차트에 공통으로 적용된다 (광고 성과 페이지와 동일한 방식).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from common import (
    get_selected_account_id, apply_comma_ticks, add_value_labels,
    force_integer_yaxis, GENDER_LABELS_SHORT,
)
from extract.db_connect import run_query

st.title("계정 성과")

account_id = get_selected_account_id()

if account_id is None:
    st.info("사이드바에서 브랜드를 선택하세요.")
    st.stop()

st.divider()

st.subheader("팔로워 추이")

col_start, col_end = st.columns(2)
with col_start:
    start = st.date_input("시작일", value=date.today() - timedelta(days=27), key="account_start")
with col_end:
    end = st.date_input("종료일", value=date.today(), key="account_end")

query = """
    SELECT
        ii.as_of_date,
        ii.followers_count,
        ii.follows,
        ii.unfollows
    FROM ig_insights_total ii
    JOIN ad_accounts aa ON aa.ig_account_id = ii.ig_id
    WHERE aa.id = %(account_id)s
      AND ii.as_of_date BETWEEN %(start)s AND %(end)s
    ORDER BY ii.as_of_date;
"""

df = run_query(query, params={"account_id": account_id, "start": start, "end": end})

if df.empty:
    st.info("해당 기간에 데이터가 없습니다.")
else:
    # 팔로우/언팔로우는 현재 DB에 값이 제대로 안 들어오고 있어 자리만 만들어둠
    # (섹션1, 섹션2에서도 동일 이슈 — 개발팀 전달 필요)
    fig = px.line(df, x="as_of_date", y="followers_count", title="팔로워 스냅샷", markers=True, labels={"as_of_date": "날짜"})
    fig = add_value_labels(apply_comma_ticks(fig))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 팔로우 / 언팔로우")
    st.caption("메타 API 이슈로 값에 10%내외의 오차가 발생할 수 있습니다")

    fig = px.line(
        df, x="as_of_date", y=["follows", "unfollows"],
        title="", markers=True, labels={"as_of_date": "날짜", "value": "", "variable": ""},
        color_discrete_map={"follows": "red", "unfollows": "blue"},
    )
    fig.update_layout(legend_title_text="")
    newnames = {"follows": "팔로우", "unfollows": "언팔로우"}
    fig.for_each_trace(lambda t: t.update(name=newnames.get(t.name, t.name)))
    fig = add_value_labels(apply_comma_ticks(fig))
    follow_max = df[["follows", "unfollows"]].max().max()
    fig = force_integer_yaxis(fig, follow_max)

    span_days = (end - start).days
    date_dtick = "D1" if span_days <= 31 else ("D2" if span_days <= 62 else "D7")
    fig.update_xaxes(dtick=date_dtick, tickformat="%m/%d", tickangle=-45)

    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("연령·성별 팔로워 추이")

combo_query = """
    SELECT DISTINCT d.age_range, d.gender
    FROM ig_insights_demographics d
    JOIN ad_accounts aa ON aa.ig_account_id = d.ig_id
    WHERE aa.id = %(account_id)s
    ORDER BY d.age_range, d.gender;
"""
combo_df = run_query(combo_query, params={"account_id": account_id})

if combo_df.empty:
    st.info("연령·성별 데이터가 없습니다.")
else:
    age_ranges = sorted(combo_df["age_range"].unique())
    genders = sorted(combo_df["gender"].unique())
    valid_pairs = set(zip(combo_df["age_range"], combo_df["gender"]))

    # 연령(행) x 성별(열) 매트릭스로 체크박스 배치 (칸마다 테두리로 구분)
    header_cols = st.columns(len(genders) + 1)
    for c, gender in zip(header_cols[1:], genders):
        with c.container(border=True):
            st.markdown(f"**{GENDER_LABELS_SHORT.get(gender, gender)}**")

    selected_pairs = []
    for age_range in age_ranges:
        row_cols = st.columns(len(genders) + 1)
        with row_cols[0].container(border=True):
            st.markdown(f"**{age_range}**")
        for c, gender in zip(row_cols[1:], genders):
            if (age_range, gender) not in valid_pairs:
                with c.container(border=True):
                    st.write("")
                continue
            with c.container(border=True):
                checked = st.checkbox(
                    "", key=f"seg_{age_range}_{gender}", label_visibility="collapsed"
                )
            if checked:
                selected_pairs.append((age_range, gender))

    if not selected_pairs:
        st.info("위에서 하나 이상의 연령·성별 그룹을 선택하세요.")
    else:
        where_clauses = []
        params = {"account_id": account_id, "start": start, "end": end}
        for i, (age_range, gender) in enumerate(selected_pairs):
            where_clauses.append(f"(d.age_range = %(age_{i})s AND d.gender = %(gender_{i})s)")
            params[f"age_{i}"] = age_range
            params[f"gender_{i}"] = gender

        segment_query = f"""
            SELECT d.as_of_date, SUM(d.followers) AS followers
            FROM ig_insights_demographics d
            JOIN ad_accounts aa ON aa.ig_account_id = d.ig_id
            WHERE aa.id = %(account_id)s
              AND ({' OR '.join(where_clauses)})
              AND d.as_of_date BETWEEN %(start)s AND %(end)s
            GROUP BY d.as_of_date
            ORDER BY d.as_of_date;
        """
        segment_df = run_query(segment_query, params=params)

        if segment_df.empty:
            st.info("해당 기간에 데이터가 없습니다.")
        else:
            selected_labels = ", ".join(
                f"{GENDER_LABELS_SHORT.get(g, g)} {a}" for a, g in selected_pairs
            )
            fig = px.line(
                segment_df, x="as_of_date", y="followers",
                title=f"선택 그룹 합산 팔로워 추이 ({selected_labels})", markers=True,
                labels={"as_of_date": "날짜"},
            )
            fig = add_value_labels(apply_comma_ticks(fig))
            st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("성장 지표")
st.caption("광고 없이 게시물로 자연스럽게 얻은 조회와 반응이에요")

GROWTH_METRICS = {
    "조회수": "total_views",
    "프로필 방문": "profile_views",
    "좋아요": "likes",
    "반응": "total_interactions",
}

selected_growth_label = st.pills(
    "지표 선택", options=list(GROWTH_METRICS.keys()), default="조회수", label_visibility="collapsed"
)
if not selected_growth_label:
    selected_growth_label = "조회수"
growth_col = GROWTH_METRICS[selected_growth_label]

growth_query = f"""
    SELECT ii.as_of_date, ii.{growth_col} AS value
    FROM ig_insights_total ii
    JOIN ad_accounts aa ON aa.ig_account_id = ii.ig_id
    WHERE aa.id = %(account_id)s
      AND ii.as_of_date BETWEEN %(start)s AND %(end)s
    ORDER BY ii.as_of_date;
"""
growth_df = run_query(growth_query, params={"account_id": account_id, "start": start, "end": end})

if growth_df.empty:
    st.info("해당 기간에 데이터가 없습니다.")
else:
    total_value = growth_df["value"].sum()
    first_value = growth_df["value"].iloc[0]
    last_value = growth_df["value"].iloc[-1]
    diff = last_value - first_value
    pct = (diff / first_value * 100) if first_value else 0
    arrow = "↑" if diff >= 0 else "↓"

    col_total, col_change = st.columns([3, 1])
    with col_total:
        st.markdown(f"총 {selected_growth_label} **{total_value:,.0f}**")
    with col_change:
        st.markdown(f"{arrow} {abs(diff):,.0f} ({pct:+.1f}%)")

    fig = px.area(growth_df, x="as_of_date", y="value", title=None, labels={"as_of_date": "날짜"})
    fig.update_traces(line_color="#2ecc71", fillcolor="rgba(46, 204, 113, 0.15)")
    fig = add_value_labels(apply_comma_ticks(fig))
    st.plotly_chart(fig, use_container_width=True)
