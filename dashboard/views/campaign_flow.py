"""
dashboard/views/campaign_flow.py

"캠페인 성과 흐름" 페이지 — 여러 캠페인을 선택해서, 캠페인(=주차) 단위로
노출/클릭/CTR/연령·성별 변화를 시계열처럼 비교한다.

캠페인 하나를 그래프의 점 하나로 압축할 때, x축 날짜는 그 캠페인에 속한 광고들의
ad_performance_daily 최초 데이터 날짜(MIN(as_of_date))를 쓴다.
(캠페인명의 날짜 접두어는 계정마다 표기가 다를 수 있어 신뢰하지 않음 — 실제 성과 데이터 기준이 더 안정적)
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from common import (
    get_selected_account_id,
    apply_comma_ticks,
    add_value_labels,
    OBJECTIVE_LABELS,
    GENDER_LABELS_SHORT,
)
from extract.db_connect import run_query


def _line_chart(df, y_col, title, texttemplate, hover_name="campaign_name"):
    fig = px.line(df, x="campaign_date", y=y_col, hover_name=hover_name, title=title, markers=True)
    return add_value_labels(apply_comma_ticks(fig), texttemplate=texttemplate)


st.title("캠페인 성과 흐름")

account_id = get_selected_account_id()

if account_id is None:
    st.info("사이드바에서 브랜드를 선택하세요.")
    st.stop()

st.divider()

st.subheader("캠페인 선택 (여러 개 가능)")

campaign_list_query = """
    SELECT id, name, objective
    FROM campaigns
    WHERE ad_account_id = %(account_id)s
    ORDER BY fb_created_time DESC NULLS LAST
    LIMIT 200;
"""
campaigns_df = run_query(campaign_list_query, params={"account_id": account_id})

if campaigns_df.empty:
    st.info("이 브랜드에 캠페인이 없습니다.")
    st.stop()

campaign_label_to_id = {
    f"{row['name']} ({OBJECTIVE_LABELS.get(row['objective'], row['objective'])})": row["id"]
    for _, row in campaigns_df.iterrows()
}
selected_labels = st.multiselect("캠페인", options=list(campaign_label_to_id.keys()))

if not selected_labels:
    st.info("캠페인을 하나 이상 선택하세요.")
    st.stop()

campaign_ids = [int(campaign_label_to_id[label]) for label in selected_labels]

# 종료일은 캠페인마다 다른 MAX(as_of_date) 대신, 페이지를 실행하는 날짜 기준 "어제"로 고정.
# (아직 도는 중인 캠페인은 조회할 때마다 종료일이 계속 밀리는 걸 막기 위함)
end_cutoff = date.today() - timedelta(days=1)

st.divider()
st.subheader("노출 / 클릭 / CTR 흐름")
st.caption(f"캠페인 하나 = 그 캠페인 광고가 처음 시작된 날짜 기준 점 하나 (집계 종료일: {end_cutoff})")

flow_query = """
    SELECT
        c.id AS campaign_id,
        c.name AS campaign_name,
        MIN(apd.as_of_date) AS campaign_date,
        COUNT(DISTINCT a.id) AS ad_count,
        SUM(apd.impressions) AS impressions,
        SUM(apd.clicks) AS clicks,
        SUM(apd.instagram_profile_visits) AS profile_visits,
        SUM(apd.instagram_profile_follows) AS profile_follows,
        SUM(apd.spend) AS spend,
        SUM(apd.purchase_value) AS purchase_value
    FROM campaigns c
    JOIN ad_sets s ON s.campaign_id = c.id
    JOIN ads a ON a.ad_set_id = s.id
    JOIN ad_performance_daily apd ON apd.ad_id = a.id
    WHERE c.id = ANY(%(campaign_ids)s)
      AND apd.as_of_date <= %(end)s
    GROUP BY c.id, c.name
    ORDER BY campaign_date;
"""
flow_df = run_query(flow_query, params={"campaign_ids": campaign_ids, "end": end_cutoff})

if flow_df.empty:
    st.info("선택한 캠페인의 성과 데이터가 없습니다.")
else:
    flow_df["ctr"] = flow_df["clicks"] / flow_df["impressions"].replace(0, None)
    flow_df["roas"] = flow_df["purchase_value"] / flow_df["spend"].replace(0, None)
    flow_df["cpm"] = flow_df["spend"] / flow_df["impressions"].replace(0, None) * 1000
    flow_df["cpc"] = flow_df["spend"] / flow_df["clicks"].replace(0, None)

    per_spend_avg = st.checkbox("광고비 1만원당 평균 (노출/클릭/프로필 방문/팔로우에 적용)")

    if per_spend_avg:
        spend_10k_safe = (flow_df["spend"] / 10000).replace(0, None)
        flow_df["impressions_display"] = flow_df["impressions"] / spend_10k_safe
        flow_df["clicks_display"] = flow_df["clicks"] / spend_10k_safe
        flow_df["profile_visits_display"] = flow_df["profile_visits"] / spend_10k_safe
        flow_df["profile_follows_display"] = flow_df["profile_follows"] / spend_10k_safe
        suffix = " (1만원당 평균)"
        count_template = "%{y:,.1f}"
    else:
        flow_df["impressions_display"] = flow_df["impressions"]
        flow_df["clicks_display"] = flow_df["clicks"]
        flow_df["profile_visits_display"] = flow_df["profile_visits"]
        flow_df["profile_follows_display"] = flow_df["profile_follows"]
        suffix = ""
        count_template = "%{y:,.0f}"

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.plotly_chart(
            _line_chart(flow_df, "impressions_display", f"노출 흐름{suffix}", count_template),
            use_container_width=True,
        )
    with row1_col2:
        st.plotly_chart(
            _line_chart(flow_df, "cpm", "CPM 흐름 (SUM(spend)/SUM(impressions)×1000)", "%{y:,.0f}"),
            use_container_width=True,
        )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.plotly_chart(
            _line_chart(flow_df, "clicks_display", f"클릭 흐름{suffix}", count_template),
            use_container_width=True,
        )
    with row2_col2:
        st.plotly_chart(
            _line_chart(flow_df, "cpc", "CPC 흐름 (SUM(spend)/SUM(clicks))", "%{y:,.0f}"),
            use_container_width=True,
        )

    row3_col1, row3_col2 = st.columns(2)
    with row3_col1:
        st.plotly_chart(
            _line_chart(flow_df, "ctr", "CTR 흐름 (SUM(clicks)/SUM(impressions))", "%{y:.2%}"),
            use_container_width=True,
        )
    with row3_col2:
        st.plotly_chart(
            _line_chart(flow_df, "roas", "ROAS 흐름 (SUM(purchase_value)/SUM(spend))", "%{y:.2f}"),
            use_container_width=True,
        )

    row4_col1, row4_col2 = st.columns(2)
    with row4_col1:
        # 프로필 방문은 현재 DB에 값이 제대로 안 들어오고 있어 0/공백일 수 있음 (추후 적재 예정)
        st.plotly_chart(
            _line_chart(flow_df, "profile_visits_display", f"프로필 방문 흐름{suffix}", count_template),
            use_container_width=True,
        )
    with row4_col2:
        st.plotly_chart(
            _line_chart(flow_df, "profile_follows_display", f"광고 발생 팔로우 흐름{suffix}", count_template),
            use_container_width=True,
        )

st.divider()
st.subheader("연령·성별 흐름")
st.caption("체크한 그룹을 합산해서, 캠페인별 CTR 변화를 봅니다")

combo_query = """
    SELECT DISTINCT apd.age_range, apd.gender
    FROM ad_performance_daily apd
    JOIN ads a ON a.id = apd.ad_id
    JOIN ad_sets s ON s.id = a.ad_set_id
    WHERE s.campaign_id = ANY(%(campaign_ids)s)
    ORDER BY apd.age_range, apd.gender;
"""
combo_df = run_query(combo_query, params={"campaign_ids": campaign_ids})

if combo_df.empty:
    st.info("연령·성별 데이터가 없습니다.")
else:
    age_ranges = sorted(combo_df["age_range"].dropna().unique())
    genders = sorted(combo_df["gender"].dropna().unique())
    valid_pairs = set(zip(combo_df["age_range"], combo_df["gender"]))

    header_cols = st.columns(len(genders) + 1)
    for c, gender in zip(header_cols[1:], genders):
        with c.container(border=True):
            st.markdown(f"**{gender}**")

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
                    "", key=f"flow_seg_{age_range}_{gender}", label_visibility="collapsed"
                )
            if checked:
                selected_pairs.append((age_range, gender))

    if not selected_pairs:
        st.info("위에서 하나 이상의 연령·성별 그룹을 선택하세요.")
    else:
        where_clauses = []
        params = {"campaign_ids": campaign_ids, "end": end_cutoff}
        for i, (age_range, gender) in enumerate(selected_pairs):
            where_clauses.append(f"(apd.age_range = %(age_{i})s AND apd.gender = %(gender_{i})s)")
            params[f"age_{i}"] = age_range
            params[f"gender_{i}"] = gender

        segment_flow_query = f"""
            SELECT
                c.id AS campaign_id,
                c.name AS campaign_name,
                MIN(apd.as_of_date) AS campaign_date,
                SUM(apd.impressions) AS impressions,
                SUM(apd.clicks) AS clicks
            FROM campaigns c
            JOIN ad_sets s ON s.campaign_id = c.id
            JOIN ads a ON a.ad_set_id = s.id
            JOIN ad_performance_daily apd ON apd.ad_id = a.id
            WHERE c.id = ANY(%(campaign_ids)s)
              AND apd.as_of_date <= %(end)s
              AND ({' OR '.join(where_clauses)})
            GROUP BY c.id, c.name
            ORDER BY campaign_date;
        """
        segment_flow_df = run_query(segment_flow_query, params=params)

        if segment_flow_df.empty:
            st.info("선택한 그룹의 성과 데이터가 없습니다.")
        else:
            segment_flow_df["ctr"] = segment_flow_df["clicks"] / segment_flow_df["impressions"].replace(0, None)
            selected_seg_labels = ", ".join(
                f"{GENDER_LABELS_SHORT.get(g, g)} {a}" for a, g in selected_pairs
            )

            seg_col1, seg_col2 = st.columns(2)
            with seg_col1:
                st.plotly_chart(
                    _line_chart(segment_flow_df, "impressions", f"노출 흐름 ({selected_seg_labels})", "%{y:,.0f}"),
                    use_container_width=True,
                )
            with seg_col2:
                st.plotly_chart(
                    _line_chart(segment_flow_df, "clicks", f"클릭 흐름 ({selected_seg_labels})", "%{y:,.0f}"),
                    use_container_width=True,
                )

            seg_col3, seg_col4 = st.columns(2)
            with seg_col3:
                st.plotly_chart(
                    _line_chart(segment_flow_df, "ctr", f"CTR 흐름 ({selected_seg_labels})", "%{y:.2%}"),
                    use_container_width=True,
                )
