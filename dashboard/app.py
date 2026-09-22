"""
dashboard/app.py

브랜드 데이터를 시계열/다차원으로 들여다보기 위한 탐색형 Streamlit 대시보드.
(주간 코멘트 자동화와는 별개 — 회의에서 직접 화면공유로 보기 위한 내부용 도구)

실행:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from common import render_brand_filter

st.set_page_config(page_title="위클리 데이터 인사이트", layout="wide")

pages = [
    st.Page("views/ad_performance.py", title="광고 성과", icon="📈"),
    st.Page("views/account_performance.py", title="계정 성과", icon="👥"),
    st.Page("views/campaign_flow.py", title="캠페인 성과 흐름", icon="🗓️"),
    st.Page("views/ad_search.py", title="광고 검색", icon="🔍"),
    st.Page("views/ad_comparison.py", title="광고 비교", icon="⚖️"),
    st.Page("views/ai_evaluation.py", title="AI 평가", icon="🤖"),
]

# 자동 내비 UI는 숨기고, 브랜드 필터 → 구분선 → 페이지 링크 순으로 직접 그려서
# 브랜드 필터가 사이드바 가장 위에 오도록 함
with st.sidebar:
    render_brand_filter()
    st.divider()
    for page in pages:
        st.page_link(page)

nav = st.navigation(pages, position="hidden")
nav.run()
