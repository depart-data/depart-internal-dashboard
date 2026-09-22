"""
dashboard/pages/ad_performance.py

"광고 성과" 페이지 — ad_performance_daily 기준 광고 지표 추이.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from common import (
    get_selected_account_id,
    commas,
    apply_comma_ticks,
    add_value_labels,
    OBJECTIVE_LABELS,
    GENDER_LABELS,
)
from extract.db_connect import run_query

st.title("광고 성과")

account_id = get_selected_account_id()

if account_id is None:
    st.info("사이드바에서 브랜드를 선택하세요.")
    st.stop()

st.divider()

# ── 캠페인 선택 & 상세 ─────────────────────────────────────
st.subheader("캠페인 선택")

campaign_list_query = """
    SELECT id, name, objective, effective_status
    FROM campaigns
    WHERE ad_account_id = %(account_id)s
    ORDER BY fb_created_time DESC NULLS LAST
    LIMIT 200;
"""
campaigns_df = run_query(campaign_list_query, params={"account_id": account_id})

campaign_id = None

if campaigns_df.empty:
    st.info("이 브랜드에 캠페인이 없습니다.")
else:
    campaign_label_to_id = {
        f"{row['name']} ({OBJECTIVE_LABELS.get(row['objective'], row['objective'])})": row["id"]
        for _, row in campaigns_df.iterrows()
    }
    selected_campaign_label = st.selectbox(
        "캠페인", options=list(campaign_label_to_id.keys()), index=None, placeholder="선택하세요"
    )

    if selected_campaign_label is None:
        st.info("캠페인을 선택하세요.")
    else:
        campaign_id = int(campaign_label_to_id[selected_campaign_label])

if campaign_id is not None:
    campaign_row = campaigns_df.loc[campaigns_df["id"] == campaign_id].iloc[0]

    # 광고세트/광고 개수
    counts_query = """
        SELECT
            (SELECT COUNT(*) FROM ad_sets WHERE campaign_id = %(campaign_id)s) AS ad_set_count,
            (SELECT COUNT(*) FROM ads a JOIN ad_sets s ON s.id = a.ad_set_id
                WHERE s.campaign_id = %(campaign_id)s) AS ad_count;
    """
    counts = run_query(counts_query, params={"campaign_id": campaign_id}).iloc[0]

    st.markdown(f"### {campaign_row['name']}")
    objective_label = OBJECTIVE_LABELS.get(campaign_row["objective"], campaign_row["objective"])
    st.caption(f"{objective_label} · 광고세트 {int(counts['ad_set_count'])}개 · 광고 {int(counts['ad_count'])}개")

    # 이 캠페인에 속한 광고들의 실제 성과 데이터 존재 기간을 기본 날짜 범위로 사용
    if st.session_state.get("campaign_prev_id") != campaign_id:
        range_df = run_query(
            """
            SELECT MIN(apd.as_of_date) AS min_date, MAX(apd.as_of_date) AS max_date
            FROM ad_performance_daily apd
            JOIN ads a ON a.id = apd.ad_id
            JOIN ad_sets s ON s.id = a.ad_set_id
            WHERE s.campaign_id = %(campaign_id)s;
            """,
            params={"campaign_id": campaign_id},
        ).iloc[0]
        default_start = range_df["min_date"] if pd.notna(range_df["min_date"]) else date.today() - timedelta(days=7)
        default_end = range_df["max_date"] if pd.notna(range_df["max_date"]) else date.today()
        st.session_state["campaign_start"] = default_start
        st.session_state["campaign_end"] = default_end
        st.session_state["campaign_prev_id"] = campaign_id

    col_cstart, col_cend = st.columns(2)
    with col_cstart:
        campaign_start = st.date_input("시작일", key="campaign_start")
    with col_cend:
        campaign_end = st.date_input("종료일", key="campaign_end")

    # 광고 단위 집계 (평균 CTR, 성별·연령 TOP3, 상위 콘텐츠, 하단 표에서 공용으로 사용)
    per_ad_query = """
        SELECT
            a.id AS ad_id,
            a.ad_name,
            a.thumb_link,
            MIN(apd.as_of_date) AS first_date,
            SUM(apd.impressions) AS impressions,
            SUM(apd.reach) AS reach,
            SUM(apd.clicks) AS clicks,
            SUM(apd.spend) AS spend
        FROM ads a
        JOIN ad_sets s ON s.id = a.ad_set_id
        JOIN ad_performance_daily apd ON apd.ad_id = a.id
        WHERE s.campaign_id = %(campaign_id)s
          AND apd.as_of_date BETWEEN %(start)s AND %(end)s
        GROUP BY a.id, a.ad_name, a.thumb_link;
    """
    per_ad_df = run_query(
        per_ad_query,
        params={"campaign_id": campaign_id, "start": campaign_start, "end": campaign_end},
    )

    if per_ad_df.empty:
        st.info("해당 기간에 이 캠페인의 성과 데이터가 없습니다.")
    else:
        per_ad_df["ctr"] = per_ad_df["clicks"] / per_ad_df["impressions"].replace(0, pd.NA)

        total_spend = per_ad_df["spend"].sum()
        total_impressions = per_ad_df["impressions"].sum()
        total_clicks = per_ad_df["clicks"].sum()
        overall_ctr = (total_clicks / total_impressions) if total_impressions else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1.container(border=True):
            st.metric("광고비", f"{total_spend:,.0f}원")
        with k2.container(border=True):
            st.metric("노출", f"{total_impressions:,.0f}")
        with k3.container(border=True):
            st.metric("클릭", f"{total_clicks:,.0f}")
        with k4.container(border=True):
            st.metric("CTR", f"{overall_ctr:.2%}")

        card1, card2, card3 = st.columns(3)

        with card1:
            with st.container(border=True):
                st.markdown("**평균 CTR**")
                avg_ctr = per_ad_df["ctr"].mean()
                st.markdown(f"## {avg_ctr:.2%}")
                st.caption(f"콘텐츠 {len(per_ad_df)}개 평균")

        with card2:
            with st.container(border=True):
                st.markdown("**성별·연령 TOP3**")
                demo_query = """
                    SELECT apd.age_range, apd.gender,
                           SUM(apd.impressions) AS impressions,
                           SUM(apd.clicks) AS clicks
                    FROM ad_performance_daily apd
                    JOIN ads a ON a.id = apd.ad_id
                    JOIN ad_sets s ON s.id = a.ad_set_id
                    WHERE s.campaign_id = %(campaign_id)s
                      AND apd.as_of_date BETWEEN %(start)s AND %(end)s
                    GROUP BY apd.age_range, apd.gender;
                """
                demo_df = run_query(
                    demo_query, params={"campaign_id": campaign_id, "start": campaign_start, "end": campaign_end}
                ).dropna(subset=["age_range", "gender"])

                if demo_df.empty:
                    st.caption("데이터 없음")
                else:
                    demo_df["label"] = demo_df["gender"].map(GENDER_LABELS).fillna(demo_df["gender"]) + " " + demo_df["age_range"]

                    impr_total = demo_df["impressions"].sum()
                    top_impr = demo_df.nlargest(3, "impressions")
                    st.caption("노출 비중")
                    for _, row in top_impr.iterrows():
                        share = row["impressions"] / impr_total if impr_total else 0
                        st.write(f"{row['label']} — {share:.1%}")

                    click_total = demo_df["clicks"].sum()
                    top_click = demo_df.nlargest(3, "clicks")
                    st.caption("클릭 비중")
                    for _, row in top_click.iterrows():
                        share = row["clicks"] / click_total if click_total else 0
                        st.write(f"{row['label']} — {share:.1%}")

        with card3:
            with st.container(border=True):
                st.markdown("**상위 콘텐츠**")

                def short_name(name, n=16):
                    return name if len(name) <= n else name[:n] + "..."

                st.caption("CTR")
                for _, row in per_ad_df.nlargest(3, "ctr").iterrows():
                    st.write(f"{short_name(row['ad_name'])} — {row['ctr']:.2%}")

                st.caption("클릭")
                for _, row in per_ad_df.nlargest(3, "clicks").iterrows():
                    st.write(f"{short_name(row['ad_name'])} — {row['clicks']:,.0f}")

        st.markdown(f"**광고 {len(per_ad_df)}개**")
        per_ad_df["ctr"] = per_ad_df["ctr"] * 100  # 표에는 %.2f%% 포맷으로 표시하기 위해 스케일링
        table_df = per_ad_df.rename(
            columns={
                "first_date": "날짜",
                "thumb_link": "썸네일",
                "ad_name": "콘텐츠명",
                "impressions": "노출",
                "reach": "도달",
                "clicks": "클릭수",
                "spend": "광고비",
                "ctr": "CTR",
            }
        )[["날짜", "썸네일", "콘텐츠명", "노출", "도달", "클릭수", "광고비", "CTR"]]

        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "썸네일": st.column_config.ImageColumn("썸네일"),
                "노출": st.column_config.NumberColumn("노출", format="%,d"),
                "도달": st.column_config.NumberColumn("도달", format="%,d"),
                "클릭수": st.column_config.NumberColumn("클릭수", format="%,d"),
                "광고비": st.column_config.NumberColumn("광고비", format="%,d원"),
                "CTR": st.column_config.NumberColumn("CTR", format="%.2f%%"),
            },
        )

st.divider()

st.subheader("광고 성과 추이")

col_start, col_end = st.columns(2)
with col_start:
    perf_start = st.date_input("시작일", value=date.today() - timedelta(days=27), key="perf_start")
with col_end:
    perf_end = st.date_input("종료일", value=date.today(), key="perf_end")

perf_query = """
    SELECT
        apd.as_of_date,
        SUM(apd.impressions) AS impressions,
        SUM(apd.clicks) AS clicks,
        SUM(apd.spend) AS spend,
        SUM(apd.purchase_count) AS purchase_count,
        SUM(apd.purchase_value) AS purchase_value
    FROM ad_performance_daily apd
    JOIN ads a ON a.id = apd.ad_id
    WHERE a.account_id = %(account_id)s
      AND apd.as_of_date BETWEEN %(start)s AND %(end)s
    GROUP BY apd.as_of_date
    ORDER BY apd.as_of_date;
"""

perf_df = run_query(
    perf_query,
    params={"account_id": account_id, "start": perf_start, "end": perf_end},
)

if perf_df.empty:
    st.info("해당 기간에 데이터가 없습니다.")
else:
    # 비율은 항상 SUM/SUM으로 재계산 (일별 평균 사용 금지)
    perf_df["ctr"] = perf_df["clicks"] / perf_df["impressions"].replace(0, pd.NA)

    fig_spend = px.line(perf_df, x="as_of_date", y="spend", title="일별 지출(spend)", markers=True, labels={"as_of_date": "날짜"})
    fig_spend = add_value_labels(apply_comma_ticks(fig_spend), texttemplate="%{y:,.0f}")
    st.plotly_chart(fig_spend, use_container_width=True)

    fig_ctr = px.line(perf_df, x="as_of_date", y="ctr", title="일별 CTR (SUM(clicks)/SUM(impressions))", markers=True, labels={"as_of_date": "날짜"})
    fig_ctr = add_value_labels(apply_comma_ticks(fig_ctr), texttemplate="%{y:.2%}")
    st.plotly_chart(fig_ctr, use_container_width=True)

    st.dataframe(commas(perf_df), use_container_width=True)
