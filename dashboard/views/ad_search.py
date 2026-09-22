"""
dashboard/views/ad_search.py

"광고 검색" 페이지 — 광고명으로 광고를 검색하고, 클릭하면 해당 광고의
성과 추이(ad_performance_daily)를 보여준다.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import get_selected_account_id
from extract.db_connect import run_query
from config.accounts import is_name_filter_exempt

st.title("광고 검색")

account_id = get_selected_account_id()

if account_id is None:
    st.info("사이드바에서 브랜드를 선택하세요.")
    st.stop()

st.divider()

st.subheader("광고명으로 검색")

def _run_search():
    kw = st.session_state.get("ad_search_keyword_input", "").strip()
    if kw != "":
        st.session_state["ad_search_keyword"] = kw
        st.session_state["ad_search_did_search"] = True


col_kw, col_btn = st.columns([4, 1])
with col_kw:
    st.text_input(
        "광고명 검색어",
        placeholder="예: 쿠폰, 여름세일 ... (Enter로도 검색)",
        label_visibility="collapsed",
        key="ad_search_keyword_input",
        on_change=_run_search,
    )
with col_btn:
    search_clicked = st.button("검색", use_container_width=True)

if search_clicked:
    if st.session_state.get("ad_search_keyword_input", "").strip() == "":
        st.warning("검색어를 입력하세요.")
    else:
        _run_search()

if not st.session_state.get("ad_search_did_search"):
    st.info("검색어를 입력하고 검색 버튼을 누르면 결과가 표시됩니다.")
    st.stop()

keyword = st.session_state["ad_search_keyword"]

# 디파트 자체 운영 계정은 캠페인명에 depart/디파트가 안 붙으므로 이 필터를 예외 처리
name_filter_exempt = is_name_filter_exempt(account_id)

ad_list_query = """
    SELECT
        a.id,
        a.ad_name,
        MIN(apd.as_of_date) AS 시작일,
        MAX(apd.as_of_date) AS 종료일
    FROM ads a
    JOIN ad_sets s ON s.id = a.ad_set_id
    JOIN campaigns c ON c.id = s.campaign_id
    LEFT JOIN ad_performance_daily apd ON apd.ad_id = a.id
    WHERE a.account_id = %(account_id)s
      AND a.ad_name ILIKE %(pattern)s
      AND (%(exempt)s OR c.name ILIKE %(depart_kr)s OR c.name ILIKE %(depart_en)s)
    GROUP BY a.id, a.ad_name, a.fb_created_time
    ORDER BY a.fb_created_time DESC NULLS LAST;
"""

ads_df = run_query(
    ad_list_query,
    params={
        "account_id": account_id,
        "pattern": f"%{keyword}%",
        "exempt": name_filter_exempt,
        "depart_kr": "%디파트%",
        "depart_en": "%depart%",
    },
)

if ads_df.empty:
    st.info("조건에 맞는 광고가 없습니다.")
    st.stop()

st.caption(f"'{keyword}' 검색 결과 {len(ads_df)}개 광고")

selection = st.dataframe(
    ads_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="multi-row",
    column_order=["ad_name", "시작일", "종료일"],
)

selected_rows = selection.selection.rows
if not selected_rows:
    st.info("표에서 광고를 클릭하면(여러 개 선택 가능) 아래에 성과가 표시됩니다.")
    st.stop()

selected_ads = ads_df.iloc[selected_rows]
ad_ids = [int(x) for x in selected_ads["id"].tolist()]

st.divider()
st.subheader(f"광고 성과 — {len(ad_ids)}개 선택")

# 선택된 광고 조합이 바뀌면 시작일을 그 중 가장 이른 광고의 시작일로, 종료일은 항상 어제로 자동 설정
# (선택 광고들의 운영 기간이 서로 다를 수 있어, 종료일을 개별 광고 기준으로 맞추지 않고 고정함)
if st.session_state.get("ad_search_prev_ad_ids") != ad_ids:
    range_df = run_query(
        "SELECT MIN(as_of_date) AS min_date FROM ad_performance_daily WHERE ad_id = ANY(%(ad_ids)s);",
        params={"ad_ids": ad_ids},
    )
    min_date = range_df.iloc[0]["min_date"]
    default_start = min_date if pd.notna(min_date) else date.today() - timedelta(days=7)
    st.session_state["ad_search_start"] = default_start
    st.session_state["ad_search_end"] = date.today() - timedelta(days=1)
    st.session_state["ad_search_prev_ad_ids"] = ad_ids

col_start, col_end = st.columns(2)
with col_start:
    perf_start = st.date_input("시작일", key="ad_search_start")
with col_end:
    perf_end = st.date_input("종료일", key="ad_search_end")

agg_query = """
    SELECT
        a.id AS ad_id,
        a.ad_name,
        SUM(apd.impressions) AS 노출,
        SUM(apd.reach) AS 도달,
        SUM(apd.clicks) AS 클릭수,
        SUM(apd.spend) AS 광고비
    FROM ad_performance_daily apd
    JOIN ads a ON a.id = apd.ad_id
    WHERE apd.ad_id = ANY(%(ad_ids)s)
      AND apd.as_of_date BETWEEN %(start)s AND %(end)s
    GROUP BY a.id, a.ad_name;
"""

agg_df = run_query(agg_query, params={"ad_ids": ad_ids, "start": perf_start, "end": perf_end})

if agg_df.empty:
    st.info("해당 기간에 성과 데이터가 없습니다.")
else:
    agg_df["CTR"] = (agg_df["클릭수"] / agg_df["노출"].replace(0, pd.NA)) * 100
    agg_df = agg_df.rename(columns={"ad_name": "콘텐츠명"})[
        ["콘텐츠명", "노출", "도달", "클릭수", "광고비", "CTR"]
    ]
    st.dataframe(
        agg_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "노출": st.column_config.NumberColumn("노출", format="%,d"),
            "도달": st.column_config.NumberColumn("도달", format="%,d"),
            "클릭수": st.column_config.NumberColumn("클릭수", format="%,d"),
            "광고비": st.column_config.NumberColumn("광고비", format="%,d원"),
            "CTR": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        },
    )
