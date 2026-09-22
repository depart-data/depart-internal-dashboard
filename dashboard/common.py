"""
dashboard/common.py

각 페이지(광고 성과 / 계정 성과 / AI 평가)에서 공통으로 쓰는
브랜드 필터, DB 조회, 숫자 포맷 유틸.
"""

import sys
from pathlib import Path

# extract/, config/ 모듈을 import하기 위해 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd
import streamlit as st

from extract.db_connect import run_query
from config.accounts import get_active_ad_account_ids


@st.cache_data(ttl=300)
def load_brand_options() -> pd.DataFrame:
    """활성 브랜드 목록을 (id, name)으로 가져온다."""
    ids = get_active_ad_account_ids()
    return run_query(
        "SELECT id, name FROM ad_accounts WHERE id = ANY(%(ids)s) ORDER BY name;",
        params={"ids": ids},
    )


def render_brand_filter():
    """
    앱 진입점(app.py)에서 `with st.sidebar:` 블록 안, 페이지 링크보다 먼저 호출한다.
    브랜드 필터를 그리고, 선택된 account_id를 session_state에 저장해서
    각 페이지에서 get_selected_account_id()로 읽게 한다.
    처음 켰을 때는 아무것도 선택 안 된 상태("선택하세요")로 시작한다.
    """
    brand_df = load_brand_options()
    brand_label_to_id = dict(zip(brand_df["name"], brand_df["id"]))

    selected_label = st.selectbox(
        "브랜드",
        options=list(brand_label_to_id.keys()),
        index=None,
        placeholder="선택하세요",
        key="brand_selector",
    )

    if selected_label is None:
        st.session_state["selected_account_id"] = None
        return None

    account_id = int(brand_label_to_id[selected_label])
    st.caption(f"선택된 계정: {selected_label} (ad_account_id={account_id})")

    st.session_state["selected_account_id"] = account_id
    return account_id


def get_selected_account_id():
    """각 페이지 스크립트에서 현재 선택된 브랜드의 ad_account_id를 읽어온다. 선택 전이면 None."""
    return st.session_state.get("selected_account_id")


def commas(df: pd.DataFrame):
    """
    숫자 컬럼에 천단위 콤마를 적용한 표시용 Styler를 반환한다.
    값의 크기에 따라 소수 자릿수를 다르게 준다 (비율형 컬럼은 소수점 유지).
    """
    fmt = {}
    for col in df.select_dtypes(include="number").columns:
        col_max = df[col].abs().max()
        if pd.isna(col_max):
            continue
        if col_max < 1:
            fmt[col] = "{:,.4f}"
        elif col_max < 100:
            fmt[col] = "{:,.2f}"
        else:
            fmt[col] = "{:,.0f}"
    return df.style.format(fmt)


def apply_comma_ticks(fig):
    """Plotly figure의 y축에 천단위 콤마 포맷을 적용하고, 전반적인 글씨 크기를 기존의 150%로 키운다."""
    fig.update_yaxes(tickformat=",")
    fig.update_layout(
        font_size=15,
        title_font_size=24,
        legend_font_size=15,
    )
    fig.update_xaxes(tickfont_size=15, title_font_size=18)
    fig.update_yaxes(tickfont_size=15, title_font_size=18)
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.12)", griddash="dot")
    return fig


def force_integer_yaxis(fig, max_value: float, target_ticks: int = 6):
    """
    y축 눈금 간격(dtick)을 정수 단위로 강제한다.
    값이 작을 때(예: 0~1 근처) Plotly가 눈금을 소수 단위로 자동 분할해서
    정수 포맷과 합쳐지면 "0,0,0,1,1,1"처럼 같은 숫자가 반복 표시되는 문제를 막는다.
    데이터 최댓값에 맞춰 1 / 2 / 5 / 10의 배수 중 적당한 간격을 골라 적용한다.
    """
    if max_value is None or max_value <= target_ticks:
        dtick = 1
    else:
        raw_step = max_value / target_ticks
        magnitude = 10 ** math.floor(math.log10(raw_step))
        for m in (1, 2, 5, 10):
            step = m * magnitude
            if raw_step <= step:
                dtick = step
                break
        else:
            dtick = 10 * magnitude
        dtick = max(1, int(round(dtick)))

    fig.update_yaxes(dtick=dtick, tickformat=",d")
    return fig


OBJECTIVE_LABELS = {
    "REACH": "도달",
    "OUTCOME_TRAFFIC": "트래픽",
    "LINK_CLICKS": "트래픽",
    "CONVERSIONS": "구매전환",
    "OUTCOME_SALES": "구매전환",
    "POST_ENGAGEMENT": "참여",
    "OUTCOME_ENGAGEMENT": "참여",
    "LEAD_GENERATION": "잠재고객",
    "OUTCOME_LEADS": "잠재고객",
    "OUTCOME_AWARENESS": "브랜드 인지도",
    "BRAND_AWARENESS": "브랜드 인지도",
    "OUTCOME_APP_PROMOTION": "앱 홍보",
}

GENDER_LABELS = {"male": "남성", "female": "여성", "unknown": "미상"}

# ig_insights_demographics 등 일부 테이블은 성별을 M/F/U로 표기함 (ad_performance_daily와 다름)
GENDER_LABELS_SHORT = {"M": "남성", "F": "여성", "U": "미상"}


def add_value_labels(fig, texttemplate: str = "%{y:,.0f}", size: int = 14):
    """각 점 위에 작은 글씨로 값을 표시한다."""
    fig.update_traces(
        mode="lines+markers+text",
        texttemplate=texttemplate,
        textposition="top center",
        textfont_size=size,
    )
    return fig
